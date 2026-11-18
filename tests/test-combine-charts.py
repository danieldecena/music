#!/usr/bin/env python3
"""
Tests for Scripts/combine_charts.py: a guitar-only chart merged into the song's full-mix chart.
Hand-rolled assertions, stdlib only:

    /opt/homebrew/bin/python3 tests/test-combine-charts.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import combine_charts as cc

_passed = 0
_failed = 0


def check(cond: bool, what: str) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"ok: {what}")
    else:
        _failed += 1
        print(f"FAIL: {what}")


MIX = """# Chords -- 10 WALKING AWAY.m4a
# key F  87.99 BPM  4 bars  start 0.313 s
# chords from Logic Pro Chord ID
1\tD#maj7
2\tF
2.3\tD#maj7
3\tGm7
4\tD#maj7
"""

GUITAR = """# Chords -- 10 WALKING AWAY.m4a
# key F  88.04 BPM  4 bars  start 0.114 s
# chords from Logic Pro Chord ID
1\tD#
1.3\tF
2\t-
3\t-
4\tD#
"""

out = cc.combine(GUITAR, MIX).splitlines()

check(
    out[0] == "# Chords -- 10 WALKING AWAY.m4a", "title line comes from the mix chart"
)
check(
    out[1] == "# key F  87.99 BPM  4 bars  start 0.313 s",
    "tempo line comes from the mix chart",
)
check(out[2] == cc.GUITAR_NOTE, "source line says guitar first, mix where it rests")
check(
    out[2].startswith("# chords from Logic Pro Chord ID"),
    "source line still marks a Logic chart",
)
check(
    out[3:5] == ["1\tD#", "1.3\tF"],
    "a guitar bar keeps its chord and its beat-3 change",
)
check(
    out[5:7] == ["2\tF", "2.3\tD#"],
    "a rest bar takes the mix chord; D#maj7 becomes the guitar's D#",
)
check(out[7] == "3\tGm7", "a root the guitar never plays keeps the mix chord")
check(out[8] == "4\tD#", "the guitar chord wins over the mix chord")
check(len(out) == 9, "no extra lines")

check(cc.root("D#maj7") == "D#", "root of D#maj7")
check(cc.root("Gm7/D") == "G", "root of a slash chord")
check(cc.root("-") == "", "no-chord has no root")

# The CLI keeps the old chart once and refuses charts of different lengths.
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp)
    song = t / "10 WALKING AWAY chords.txt"
    guitar = t / "10 WALKING AWAY guitar chords.txt"
    song.write_text(MIX)
    guitar.write_text(GUITAR)
    script = str(REPO / "Scripts/combine_charts.py")
    r = subprocess.run(
        [sys.executable, script, str(guitar), str(song)], capture_output=True, text=True
    )
    check(
        r.returncode == 0, f"CLI writes the merged chart (stderr {r.stderr.strip()!r})"
    )
    check(
        (t / "10 WALKING AWAY chords (mix).txt").read_text() == MIX,
        "CLI keeps the old chart as (mix)",
    )
    check(song.read_text() == cc.combine(GUITAR, MIX), "CLI writes combine()'s result")
    r = subprocess.run(
        [sys.executable, script, str(guitar), str(song)], capture_output=True, text=True
    )
    check(
        (t / "10 WALKING AWAY chords (mix).txt").read_text() == MIX,
        "a second run does not overwrite (mix)",
    )
    guitar.write_text(GUITAR.replace("4 bars", "5 bars") + "5\tF\n")
    r = subprocess.run(
        [sys.executable, script, str(guitar), str(song)], capture_output=True, text=True
    )
    check(r.returncode == 1, "CLI refuses charts with different bar counts")
    check("bars" in r.stdout + r.stderr, "and says it is the bar count")

print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
