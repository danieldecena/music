#!/usr/bin/env python3
"""
Tests for Scripts/find_track.py. Hand-rolled assertions in the style of
tests/test-chords.py. stdlib only:

    .venv/bin/python tests/test-find-track.py [all|unit|find|cli]
"""

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import find_track as ft  # noqa: E402

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


def _mkroot(tmp: Path) -> Path:
    """A miniature music root: two stem models + a nested source library."""
    for model, tracks in (
        ("htdemucs", ("03 Exchange", "09 Rambo", "02 Let Em' Know")),
        ("htdemucs_6s", ("02 Let Em' Know",)),  # dup of a htdemucs track
    ):
        for t in tracks:
            (tmp / "Stems" / model / t).mkdir(parents=True)
    src = tmp / "Apple Music" / "Bryson Tiller" / "TRAPSOUL"
    src.mkdir(parents=True)
    for f in ("09 Rambo.m4a", "05 Sorry.m4a"):
        (src / f).write_bytes(b"x")
    return tmp


def unit() -> None:
    # normalization strips punctuation/case, collapses space.
    check(ft._norm("02 Let Em' Know") == "02 let em know", "norm strips apostrophe")
    check(ft._norm("  A  B ") == "a b", "norm collapses whitespace")

    # scoring: exact > substring > typo > unrelated.
    check(ft.score("exchange", "03 Exchange") > 0.9, "substring token scores high")
    check(ft.score("ramba", "09 Rambo") > 0.6, "single typo still scores")
    check(
        ft.score("ramba", "09 Rambo") > ft.score("ramba", "05 Sorry"),
        "typo target beats unrelated",
    )
    check(ft.score("", "anything") == 0.0, "empty query scores 0")
    check(ft.score("xyz", "") == 0.0, "empty label scores 0")


def find() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = _mkroot(Path(d))

        rows = ft.find("exchange", root, limit=10, min_score=0.34)
        check(len(rows) == 1, "clear match trims to one row")
        check(
            rows[0][3].endswith("Stems/htdemucs/03 Exchange"),
            "returns the stem folder path",
        )

        # 'Let Em' Know' exists in both models + would as source: collapse to one,
        # keeping a stems row (kind=stems), not duplicated per model.
        rows = ft.find("let em", root, limit=10, min_score=0.34)
        labels = [r[2] for r in rows]
        check(
            labels.count("02 Let Em' Know") == 1, "cross-model dup collapses to one row"
        )
        check(rows[0][1] == "stems", "collapsed row keeps the stem kind")

        # 'Rambo' is both a stem folder and a source file -> one row, stems wins.
        rows = ft.find("rambo", root, limit=10, min_score=0.34)
        rambo = [r for r in rows if r[2] == "09 Rambo"]
        check(
            len(rambo) == 1 and rambo[0][1] == "stems", "stems outranks source on tie"
        )

        # garbage clears nothing.
        check(
            ft.find("zzzq", root, limit=10, min_score=0.34) == [], "no match -> empty"
        )

        # gap trims the weak tail: a strong top hit hides distant partials.
        rows = ft.find("exchange", root, limit=10, min_score=0.05, gap=0.25)
        check(all(r[0] >= rows[0][0] - 0.25 for r in rows), "gap floor drops the tail")


def cli() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = _mkroot(Path(d))
        script = str(REPO / "Scripts" / "find_track.py")

        r = subprocess.run(
            [sys.executable, script, "exchange", "--root", str(root)],
            capture_output=True,
            text=True,
        )
        check(r.returncode == 0, "cli exit 0 on a match")
        check(r.stdout.strip().endswith("03 Exchange"), "cli default prints the path")

        r = subprocess.run(
            [sys.executable, script, "zzzq", "--root", str(root)],
            capture_output=True,
            text=True,
        )
        check(
            r.returncode == 1 and r.stdout.strip() == "",
            "cli exit 1 + empty on no match",
        )

        r = subprocess.run(
            [sys.executable, script, "rambo", "--root", str(root), "--tsv"],
            capture_output=True,
            text=True,
        )
        check(
            "\t" in r.stdout and "stems" in r.stdout,
            "tsv output carries score/kind columns",
        )


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("all", "unit"):
        unit()
    if mode in ("all", "find"):
        find()
    if mode in ("all", "cli"):
        cli()
    if mode not in ("all", "unit", "find", "cli"):
        print(f"unknown mode: {mode}")
        sys.exit(2)
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
