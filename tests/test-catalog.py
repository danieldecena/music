#!/usr/bin/env python3
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Scripts"))
import catalog

con = sqlite3.connect(":memory:")
con.row_factory = sqlite3.Row
catalog.init(con)
con.execute(
    "INSERT INTO tracks(name,source_path,artist,album,bpm,key,model,deconstructed_at,first_seen) "
    "VALUES(?,?,?,?,?,?,?,?,?)",
    (
        "One More Time",
        "Apple Music/One More Time.m4a",
        "Daft Punk",
        "Discovery",
        123,
        "F#m",
        "htdemucs",
        "2026-07-12T00:00:00",
        "2026-07-11T00:00:00",
    ),
)
con.execute(
    "INSERT INTO tracks(name,source_path,first_seen) VALUES(?,?,?)",
    ("Random Track", "Downloads/Random Track.mp3", "2026-07-11T00:00:00"),
)
con.execute(
    "INSERT INTO assets(track,kind,subtype,path,mtime) "
    "VALUES('One More Time','stem','vocals','x/vocals.wav',0)"
)
con.commit()

hit = catalog._search_rows(con, "daft")
assert len(hit) == 1 and hit[0]["name"] == "One More Time", hit
assert hit[0]["stems"] == 1, hit[0]

nohit = catalog._search_rows(con, "zzz")
assert nohit == [], nohit

allrows = catalog._search_rows(con, "")
assert len(allrows) == 2, allrows
assert allrows[0]["model"] is not None, "deconstructed must sort first"

label = catalog._label(hit[0])
assert "Daft Punk" in label and "123 BPM" in label and "F#m" in label, label
assert "deconstructed" in label, label

print("ok: catalog search")

# song_title: strip the leading track-number prefix and any file extension, so
# display reads "Pink + White", not "03 Pink + White.m4a".
assert catalog.song_title("03 Pink + White") == "Pink + White"
assert catalog.song_title("1-01 SPEED DEMON") == "SPEED DEMON"
assert catalog.song_title("09 Nights.m4a") == "Nights"
assert (
    catalog.song_title("Apple Music/Frank Ocean/Blonde/16 Godspeed.m4a") == "Godspeed"
)
# No prefix, nothing to strip.
assert catalog.song_title("One More Time") == "One More Time"
assert catalog.song_title("YUKON") == "YUKON"
# Only ONE prefix is stripped, so a title that itself starts with a number keeps it.
assert catalog.song_title("10 502 Come Up") == "502 Come Up"
assert catalog.song_title("1979") == "1979"
# Degenerate input must never yield an empty label.
assert catalog.song_title("07") == "07"
assert catalog.song_title("") == ""
assert catalog.song_title(None) == ""

assert "One More Time" in catalog._label(hit[0])
assert (
    catalog._mix_track_label(
        {"artist": "Justin Bieber", "name": "1-01 SPEED DEMON", "key": "Dm", "bpm": 93}
    )
    == "Justin Bieber — SPEED DEMON (Dm/93)"
)

print("ok: catalog song_title")

con.execute(
    "INSERT INTO tracks(name,source_path,artist,bpm,key,first_seen) VALUES(?,?,?,?,?,?)",
    (
        "03 YUKON",
        "Apple Music/JB/SWAG/03 YUKON.m4a",
        "Justin Bieber",
        128,
        "Dm",
        "2026-07-11T00:00:00",
    ),
)
con.execute(
    "INSERT INTO tracks(name,source_path,artist,bpm,key,first_seen) VALUES(?,?,?,?,?,?)",
    (
        "06 Skyline To",
        "Apple Music/FO/Blonde/06 Skyline To.m4a",
        "Frank Ocean",
        129,
        "F",
        "2026-07-11T00:00:00",
    ),
)
con.commit()

seed, status = catalog.resolve_seed(con, "YUKON")
assert status == "ok" and seed["name"] == "03 YUKON", (status, seed)

# Case-insensitive and tolerant of the track number the user won't type.
seed, status = catalog.resolve_seed(con, "yukon")
assert status == "ok", (status, seed)

# An unanalyzed track cannot seed a mix -- it has no bpm/key to match on.
seed, status = catalog.resolve_seed(con, "Random Track")
assert status == "nomatch", (status, seed)

seed, status = catalog.resolve_seed(con, "zzzznope")
assert status == "nomatch" and seed is None, (status, seed)

# Substring hitting two analyzed tracks must refuse to guess.
seed, status = catalog.resolve_seed(con, "o")
assert status == "ambiguous" and seed is None, (status, seed)

print("ok: catalog resolve_seed")
