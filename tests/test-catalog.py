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

# pick_source: two files sharing a filename stem are one track name, and the
# name keys the stem/sample folders on disk -- so the fix is choosing which file
# the name points at, deterministically, not renaming the track.
one = {"path": "Apple Music/A/Alb/03 Exchange.m4a", "size": 100, "album": "Alb"}
# A lone candidate must never cost an ffprobe -- a probe here would be a bug.
assert catalog.pick_source([one], probe=lambda p: 1 / 0) == (one, [])

# The real collision, with the real sizes: the CORRUPT copy is the BIGGER one.
# A size rule picks exactly wrong here, which is why decodability decides.
good = {
    "path": "Apple Music/A/Deluxe/03 Exchange.m4a",
    "size": 6735500,
    "album": "Deluxe",
}
corrupt = {
    "path": "Apple Music/A/Plain/03 Exchange.m4a",
    "size": 12018200,
    "album": "Plain",
}
plays = lambda p: p == good["path"]  # noqa: E731
win, shadowed = catalog.pick_source([corrupt, good], probe=plays)
assert win is good and shadowed == [corrupt], (win, shadowed)
win, shadowed = catalog.pick_source([good, corrupt], probe=plays)
assert win is good and shadowed == [corrupt], (win, shadowed)

# Both playable (a genuine duplicate): path decides, so a rescan is stable.
a = {"path": "Apple Music/A/AA/01 Intro.m4a", "size": 500, "album": "AA"}
b = {"path": "Apple Music/B/BB/01 Intro.m4a", "size": 900, "album": "BB"}
assert catalog.pick_source([a, b], probe=lambda p: True) == (a, [b])
assert catalog.pick_source([b, a], probe=lambda p: True) == (a, [b])

# Neither playable: still deterministic rather than filesystem order.
assert catalog.pick_source([b, a], probe=lambda p: False) == (a, [b])

# The winner's own metadata travels with it -- never a blend of both rows.
win, _ = catalog.pick_source([corrupt, good], probe=plays)
assert win["album"] == "Deluxe", win

print("ok: catalog pick_source")

# scan() must apply that choice end-to-end: the shadowed file is reported, and
# the surviving row carries the winning file's album, not the loser's. Neither
# fixture decodes, so this exercises the path tie-break through the real probe.
import tempfile as _tempfile  # noqa: E402

with _tempfile.TemporaryDirectory() as tmp:
    root = catalog.Path(tmp)
    (root / "Apple Music" / "Bryson" / "Deluxe").mkdir(parents=True)
    (root / "Apple Music" / "Bryson" / "Plain").mkdir(parents=True)
    (root / "Apple Music" / "Bryson" / "Deluxe" / "03 Exchange.m4a").write_bytes(
        b"x" * 900
    )
    (root / "Apple Music" / "Bryson" / "Plain" / "03 Exchange.m4a").write_bytes(
        b"x" * 100
    )

    prev_root = catalog.ROOT
    catalog.ROOT = root
    try:
        scon = sqlite3.connect(":memory:")
        scon.row_factory = sqlite3.Row
        conflicts = catalog.scan(scon)
        rows = scon.execute("SELECT name, source_path, album FROM tracks").fetchall()
    finally:
        catalog.ROOT = prev_root

    assert len(rows) == 1, rows
    assert rows[0]["album"] == "Deluxe", dict(rows[0])
    assert rows[0]["source_path"].endswith("Deluxe/03 Exchange.m4a"), dict(rows[0])
    # Silently dropping a file is what made the corrupt copy hard to find.
    assert len(conflicts) == 1, conflicts
    assert conflicts[0]["name"] == "03 Exchange", conflicts[0]
    assert "Plain" in conflicts[0]["shadowed"][0], conflicts[0]

print("ok: catalog scan collision")
