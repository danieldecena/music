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

    grid_checks()

    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


def stub_analyzer(root, payload: str) -> None:
    """Stand in for Tools/mu-analyze so the grid loop can be tested without
    decoding audio. Writes `payload` to the path after -o, like the real one."""
    tools = root / "Tools"
    tools.mkdir(parents=True, exist_ok=True)
    binary = tools / "mu-analyze"
    binary.write_text(
        "#!/bin/sh\n"
        f"cat {payload!r} > \"$3\"\n"
    )
    binary.chmod(0o755)


def seed_track(db, root, name: str) -> None:
    src = root / "Apple Music" / f"{name}.m4a"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"not really audio; the stub analyzer never reads it")
    con = sqlite3.connect(db)
    try:
        con.execute("INSERT INTO tracks(name, source_path) VALUES (?,?)",
                    (name, str(src.relative_to(root))))
        con.commit()
    finally:
        con.close()


def grid_checks() -> None:
    """backfill-grid: the two branches that would otherwise fail silently.

    A missing binary must be an error, not a quiet 'nothing needed a grid', and
    an analysis that ingests but carries no rhythm must not read as filled.
    """
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        db = root / "catalog.sqlite"
        run(root, "init")
        seed_track(db, root, "Stub")

        # No binary at all. A fresh checkout's normal state.
        r = run(root, "backfill-grid")
        check(r.returncode == 1, "backfill-grid fails when mu-analyze is absent")
        check("swiftc" in r.stdout, "and names the build command")
        check(one(db, "SELECT count(*) FROM bars") == 0, "and ingests nothing")

        # An analysis with no rhythm block. Ingest succeeds; the grid does not.
        empty = root / "empty.json"
        empty.write_text('{"result": {}}')
        stub_analyzer(root, str(empty))
        r = run(root, "backfill-grid")
        check(r.returncode == 1, "backfill-grid fails on an analysis with no bars")
        check("no bars" in r.stdout, "and says so rather than counting it done")
        check(one(db, "SELECT count(*) FROM bars") == 0, "and leaves the grid empty")

    # The known-GOOD input, so the two checks above are not all this can do.
    # Its own root: the failing run above leaves a cached Samples/Analysis JSON,
    # and the default pass reuses a cached file rather than re-analyzing.
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        db = root / "catalog.sqlite"
        run(root, "init")
        seed_track(db, root, "Stub")
        stub_analyzer(root, str(SAMPLE))

        r = run(root, "backfill-grid")
        check(r.returncode == 0, "backfill-grid exits 0 on a real analysis")
        check(one(db, "SELECT count(*) FROM bars") == 118, "and fills the bar grid")

        # Already gridded: the default pass has nothing left to do.
        r = run(root, "backfill-grid")
        check("gridded 0/0" in r.stdout, "a gridded track is not re-analyzed")
        check("gridded 1/1" in run(root, "backfill-grid", "--refresh").stdout,
              "--refresh re-analyzes it anyway")


if __name__ == "__main__":
    main()
