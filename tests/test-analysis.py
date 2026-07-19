#!/usr/bin/env python3
"""
Tests for Scripts/analyze_track.py.

Two modes:

    replay  (default)  Re-run the analyzer over the corpus and diff against
                       tests/baseline-analysis.tsv. The analyzer is
                       deterministic, so a pure refactor must reproduce the
                       baseline exactly; an algorithm change must move only the
                       rows it claims to move. Requires the local audio corpus,
                       so it is skipped when the TSV is missing.

Run with the venv python — numpy is required:
    .venv/bin/python tests/test-analysis.py [replay]
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))
sys.path.insert(0, str(REPO / "tests"))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "record_baseline", REPO / "tests" / "record-baseline.py"
)
record_baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(record_baseline)

BASELINE = REPO / "tests" / "baseline-analysis.tsv"

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


def load_baseline() -> dict[str, tuple[str, ...]]:
    rows = BASELINE.read_text().splitlines()
    return {r.split("\t")[0]: tuple(r.split("\t")) for r in rows[1:] if r.strip()}


def replay() -> None:
    """Diff a fresh run against the recorded baseline, row by row."""
    if not BASELINE.is_file():
        print(f"skip: {BASELINE.name} not recorded — run tests/record-baseline.py")
        return
    base = load_baseline()
    files = record_baseline.corpus()
    if not files:
        print("skip: no local audio corpus on this machine")
        return

    seen, drifted = set(), []
    for f in files:
        rel = f.relative_to(REPO).as_posix()
        seen.add(rel)
        if rel not in base:
            continue  # new audio added since the baseline; not a regression
        got = record_baseline.row(f)
        if got != base[rel]:
            drifted.append((rel, base[rel], got))

    missing = sorted(set(base) - seen)
    for rel in missing:
        print(f"  note: baseline row no longer in corpus — {rel}")

    for rel, was, now in drifted:
        print(f"  drift: {rel}\n    was: {was[1:]}\n    now: {now[1:]}")
    check(
        not drifted, f"replay matches baseline ({len(seen & set(base))} rows compared)"
    )


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "replay"
    if mode == "replay":
        replay()
    else:
        print(f"unknown mode: {mode}")
        sys.exit(2)
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
