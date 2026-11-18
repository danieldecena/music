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

    # Re-run after a first merge: the input is (mix), never the merged chart.
    guitar.write_text(GUITAR)
    mixfile = t / "10 WALKING AWAY chords (mix).txt"
    song.write_text(MIX)
    mixfile.unlink()
    subprocess.run([sys.executable, script, str(guitar), str(song)], capture_output=True, text=True)
    guitar2 = GUITAR.replace("1\tD#\n1.3\tF\n2\t-\n3\t-\n4\tD#\n", "1\t-\n2\t-\n3\t-\n4\tF\n")
    guitar.write_text(guitar2)
    r = subprocess.run([sys.executable, script, str(guitar), str(song)], capture_output=True, text=True)
    check(r.returncode == 0, f"a re-run with a changed guitar chart succeeds ({r.stdout.strip()!r})")
    check(song.read_text() == cc.combine(guitar2, MIX), "a re-run merges against (mix), not the merged chart")
    check(mixfile.read_text() == MIX, "and leaves (mix) as it was")

    # A new full-mix chart dropped over a merged one refreshes (mix).
    guitar.write_text(GUITAR)
    mix2 = MIX.replace("Gm7", "Cm7")
    song.write_text(mix2)
    r = subprocess.run([sys.executable, script, str(guitar), str(song)], capture_output=True, text=True)
    check(r.returncode == 0, "a fresh full-mix chart over a merged one is merged")
    check(mixfile.read_text() == mix2, "and replaces (mix) with the new full-mix chart")
    check(song.read_text() == cc.combine(GUITAR, mix2), "and merges against the new chart")

    # A merged chart with no (mix) backup is refused.
    mixfile.unlink()
    before = song.read_text()
    r = subprocess.run([sys.executable, script, str(guitar), str(song)], capture_output=True, text=True)
    check(r.returncode == 1 and song.read_text() == before, "a merged chart with no (mix) is refused, unchanged")
    check("missing" in r.stdout + r.stderr, "and says (mix) is missing")

    # A song chart not named "* chords.txt" is refused before anything is written.
    odd = t / "10 WALKING AWAY chart.txt"
    odd.write_text(MIX)
    r = subprocess.run([sys.executable, script, str(guitar), str(odd)], capture_output=True, text=True)
    check(r.returncode == 1, "a song chart not named '* chords.txt' is refused")
    check(odd.read_text() == MIX, "and is left unchanged")
    check("chords.txt" in r.stdout + r.stderr, "and the reason names the expected file name")

print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
