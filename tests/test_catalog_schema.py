"""Schema-migration tests for catalog.py init.

Hand-rolled assertions, matching tests/test-analysis.py. Runs catalog.py in a
throwaway root via LOGIC_STUDIO_MUSIC_ROOT so the live catalog is untouched.

Run: .venv/bin/python tests/test_catalog_schema.py
"""
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOG = ROOT / "Scripts" / "catalog.py"

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


def run_init(root: pathlib.Path) -> int:
    env = dict(os.environ, LOGIC_STUDIO_MUSIC_ROOT=str(root))
    r = subprocess.run(
        [sys.executable, str(CATALOG), "init"], env=env, capture_output=True, text=True
    )
    if r.returncode != 0:
        print(r.stderr.strip()[:400])
    return r.returncode


def cols(db: pathlib.Path, table: str) -> set[str]:
    con = sqlite3.connect(db)
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        db = root / "catalog.sqlite"

        check(run_init(root) == 0, "init exits 0")

        want_regions = {
            "track", "kind", "start_s", "end_s",
            "start_bar", "n_bars", "score", "meta_json",
        }
        check(want_regions <= cols(db, "regions"), "regions has the product columns")

        for t, c in [
            ("beats", {"track", "idx", "t", "bar", "beat_in_bar"}),
            ("bars", {"track", "idx", "t"}),
            ("sections", {"track", "idx", "label", "start_s", "end_s"}),
            ("key_ranges", {"track", "idx", "tonic", "mode", "start_s", "end_s"}),
            ("loudness", {"track", "t", "momentary", "short_term"}),
            ("instrument_activity", {"track", "instrument", "start_s", "end_s", "level"}),
            ("lyrics", {"track", "start_s", "end_s", "text"}),
            ("pairs", {"a", "b", "tempo_ok", "tempo_ratio", "key_relation", "score"}),
        ]:
            check(c <= cols(db, t), f"{t} has its columns")

        # The existing tables must survive untouched.
        check({"name", "source_path", "bpm", "key"} <= cols(db, "tracks"),
              "tracks keeps its original columns")
        check({"track", "kind", "path"} <= cols(db, "assets"), "assets unchanged")

        # New per-track analysis columns, added by ALTER since SQLite has no
        # ADD COLUMN IF NOT EXISTS.
        check({"duration_s", "apple_bpm", "apple_key", "pace", "lufs_integrated",
               "true_peak", "analyzed_at", "analysis_version"} <= cols(db, "tracks"),
              "tracks gains the analysis columns")

        # Idempotent: a second init must not fail or duplicate a column.
        before = cols(db, "tracks")
        check(run_init(root) == 0, "second init exits 0")
        check(cols(db, "tracks") == before, "second init leaves tracks unchanged")

    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
