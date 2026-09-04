#!/usr/bin/env python3
"""Generate the Flip Stem Map artifact from the catalog.

The page inlines its data, so it must be regenerated whenever the crate grows.
`Artifacts/stem-map/template.html` is the hand-edited source; the generated
`stem_map.html` beside it is what gets published and hashed, and is never
hand-edited.

Activity is decimated to every 8th sample -- 20 Hz down to 2.5 Hz. At the page's
width that is roughly one sample per two pixels, so the drawn lane is unchanged
while the payload stays small enough that fourteen tracks ship in one file.

Usage: build_stem_map.py [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "catalog.sqlite"
HERE = ROOT / "Artifacts" / "stem-map"
INSTRUMENTS = ("bass", "drum", "other", "vocal")
DECIMATE = 8
N_LOOPS = 8


def collect(con: sqlite3.Connection) -> dict:
    con.row_factory = sqlite3.Row

    def rows(q, *a):
        return [dict(r) for r in con.execute(q, a)]

    out = {}
    for name in (r["track"] for r in rows("SELECT DISTINCT track FROM bars ORDER BY track")):
        tr = rows(
            "SELECT artist, album, apple_bpm, apple_key, duration_s "
            "FROM tracks WHERE name=?", name)
        if not tr or tr[0]["apple_bpm"] is None or not tr[0]["duration_s"]:
            continue
        tr = tr[0]
        activity = {}
        for inst in INSTRUMENTS:
            pts = rows(
                "SELECT start_s, level FROM instrument_activity "
                "WHERE track=? AND instrument=? ORDER BY start_s", name, inst)
            activity[inst] = [
                [round(p["start_s"], 2), round(p["level"], 3)]
                for i, p in enumerate(pts) if i % DECIMATE == 0
            ]
        out[name] = {
            "artist": tr["artist"] or "",
            "album": tr["album"] or "",
            "bpm": tr["apple_bpm"],
            "key": tr["apple_key"],
            "duration": tr["duration_s"],
            "bars": rows("SELECT idx, t FROM bars WHERE track=? ORDER BY idx", name),
            "sections": rows(
                "SELECT start_s, end_s FROM sections "
                "WHERE track=? AND label='section' ORDER BY start_s", name),
            "activity": activity,
            "loops": rows(
                "SELECT start_s, end_s, start_bar, score FROM regions "
                "WHERE track=? AND kind='loop' ORDER BY score DESC LIMIT ?",
                name, N_LOOPS),
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(HERE / "stem_map.html"))
    a = ap.parse_args(argv)

    if not DB.exists():
        raise SystemExit(f"no catalog at {DB} -- run: catalog.py scan")
    tracks = collect(sqlite3.connect(DB))
    if not tracks:
        raise SystemExit(
            "no track carries a bar grid -- run apple_analyze on at least one, "
            "or deconstruct a track, which now does it for you")

    template = (HERE / "template.html").read_text(encoding="utf-8")
    if "__DATA__" not in template:
        raise SystemExit("template.html has no __DATA__ placeholder")
    out = pathlib.Path(a.out)
    out.write_text(
        template.replace("__DATA__", json.dumps(tracks, separators=(",", ":"))),
        encoding="utf-8")

    print(f"{len(tracks)} tracks -> {out} ({out.stat().st_size / 1024:.0f} KB)")
    for name, t in tracks.items():
        print(f"  {name[:32]:32} {t['bpm']:6.1f} {str(t['key']):>4}  "
              f"{len(t['bars']):3} bars  {len(t['sections']):2} sections  "
              f"{len(t['loops'])} loops")
    return 0


if __name__ == "__main__":
    sys.exit(main())
