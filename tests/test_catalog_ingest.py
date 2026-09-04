"""Ingest tests for catalog.py ingest, against a real mu-analyze JSON file.

Run: .venv/bin/python tests/test_catalog_ingest.py
"""
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOG = ROOT / "Scripts" / "catalog.py"
SAMPLE = ROOT / "Samples" / "Analysis" / "02 Ivy.json"

_passed = 0
_failed = 0


def check(cond: bool, label: str) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"ok: {label}")
    else:
        _failed += 1
        print(f"FAIL: {label}")


def run(root, *args) -> subprocess.CompletedProcess:
    env = dict(os.environ, LOGIC_STUDIO_MUSIC_ROOT=str(root))
    r = subprocess.run([sys.executable, str(CATALOG), *args],
                       env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print("   " + (r.stderr.strip().splitlines() or [""])[-1][:300])
    return r


def one(db, sql):
    con = sqlite3.connect(db)
    try:
        row = con.execute(sql).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def main() -> None:
    if not SAMPLE.exists():
        print(f"FAIL: missing {SAMPLE} -- run Tools/mu-analyze first")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        db = root / "catalog.sqlite"
        run(root, "init")

        check(run(root, "ingest", "Ivy", str(SAMPLE)).returncode == 0, "ingest exits 0")

        n_beats = one(db, "SELECT count(*) FROM beats")
        check(n_beats == 469, f"469 beats ingested (got {n_beats})")
        check(one(db, "SELECT count(*) FROM bars") == 118, "118 bars ingested")
        check(one(db, "SELECT count(*) FROM sections WHERE label='section'") == 14,
              "14 sections ingested")
        check(one(db, "SELECT count(*) FROM sections WHERE label='phrase'") == 64,
              "64 phrases ingested")
        check(one(db, "SELECT count(*) FROM key_ranges") == 1, "1 key range ingested")
        check(one(db, "SELECT count(DISTINCT instrument) FROM instrument_activity") == 4,
              "4 instruments (bass, drum, other, vocal)")

        # CMTime is {timescale, value}; seconds must be value/timescale, not raw.
        first_beat = one(db, "SELECT min(t) FROM beats")
        check(first_beat is not None and 0.0 <= first_beat < 1.0,
              f"beat times are seconds, not raw CMTime values (got {first_beat})")
        last_beat = one(db, "SELECT max(t) FROM beats")
        check(last_beat is not None and 240.0 < last_beat < 250.0,
              f"last beat lands inside the 249s track (got {last_beat})")

        # Non-finite loudness must land as NULL, never as a bogus number.
        check(one(db, "SELECT count(*) FROM loudness") > 1000, "loudness frames ingested")
        check(one(db, "SELECT count(*) FROM loudness WHERE momentary IS NOT NULL") > 0,
              "finite loudness values survive")

        # tracks row gets the summary columns.
        check(one(db, "SELECT apple_bpm FROM tracks WHERE name='Ivy'") is not None,
              "tracks.apple_bpm populated")
        check(one(db, "SELECT apple_key FROM tracks WHERE name='Ivy'") == "C",
              "tracks.apple_key normalized to repo spelling")

        # Idempotent: re-ingest replaces, never appends.
        run(root, "ingest", "Ivy", str(SAMPLE))
        check(one(db, "SELECT count(*) FROM beats") == n_beats,
              "re-ingest leaves the beat count unchanged")

    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
