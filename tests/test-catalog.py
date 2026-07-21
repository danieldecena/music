#!/usr/bin/env python3
import sqlite3, sys, os

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
