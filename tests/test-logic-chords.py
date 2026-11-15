#!/usr/bin/env python3
"""
Tests for Scripts/logic_chords.py's pure half: reading Logic's Chord Track items and turning
them into a chords.txt on the existing chart's grid. Driving Logic itself is checked by
running the script on a real song. Hand-rolled assertions, stdlib only:

    /opt/homebrew/bin/python3 tests/test-logic-chords.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import logic_chords as lc

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


def raises(fn, label: str) -> None:
    try:
        fn()
    except ValueError:
        check(True, label)
    else:
        check(False, label)


def main() -> int:
    # Positions as Logic's accessibility tree words them, at 120 BPM (a bar is 2 s).
    check(lc.item_seconds("1 bar", 120) == 0.0, "bar 1 starts at 0 s")
    check(
        lc.item_seconds("2 bars 3 beats 7 ticks", 120) == 2.0 + 1.0 + 7 / 960 * 0.5,
        "bar, beat and ticks, division left out",
    )
    check(
        abs(
            lc.item_seconds("3 bars 4 beats 4 divisions 211 ticks", 120)
            - (4.0 + 1.5 + 0.375 + 211 / 960 * 0.5)
        )
        < 1e-9,
        "every field",
    )
    check(
        lc.item_seconds("1 bar", 60) == 0.0 and lc.item_seconds("2 bars", 60) == 4.0,
        "the tempo sets the bar length",
    )
    raises(
        lambda: lc.item_seconds("somewhere", 120), "an unreadable position is an error"
    )

    # Item descriptions: the chord's spoken name, then its position.
    check(
        lc.split_item("a flat major 1 bar ") == ("a flat major", "1 bar"),
        "name and position",
    )
    check(
        lc.split_item("No Chord 152 bars 3 beats 3 divisions 153 ticks ")
        == ("No Chord", "152 bars 3 beats 3 divisions 153 ticks"),
        "No Chord item",
    )
    raises(
        lambda: lc.split_item("chord group a flat major, b flat major"),
        "a chord group is not a chord item",
    )

    # Spoken names to the chart's spelling (sharps, as ChordChart normalises).
    names = {
        "a flat major": "G#",
        "b flat major": "A#",
        "c minor": "Cm",
        "c minor 7": "Cm7",
        "e flat major major 7": "D#maj7",
        "c sharp major 7": "C#7",
        "b flat major 6": "A#6",
        "g minor 7/d": "Gm7/D",
        "g minor/f": "Gm/F",
        "b flat major/d": "A#/D",
        "f sharp major": "F#",
        "e major major 7": "Emaj7",
        "No Chord": "-",
    }
    for spoken, want in names.items():
        got = lc.chord_name(spoken)
        check(got == want, f"{spoken!r} -> {want!r} (got {got!r})")
    raises(
        lambda: lc.chord_name("c half diminished 7"),
        "a quality this script does not know is an error, not a guess",
    )

    # One label per bar: the chord that sounds longest in it.
    changes = [(0.0, "C"), (2.5, "G"), (4.5, "-")]
    check(
        lc.bar_labels(changes, 120, 3) == ["C", "G", "-"],
        "longest overlap wins each bar",
    )
    check(
        lc.bar_labels([(0.0, "C"), (1.0, "G")], 120, 1) == ["C"],
        "a tie keeps the earlier chord",
    )
    check(
        lc.bar_labels([(0.0, "C")], 120, 4) == ["C"] * 4,
        "the last chord runs to the end",
    )
    check(
        lc.bar_labels([(3.0, "D")], 120, 2) == ["-", "D"],
        "before the first chord is silent",
    )

    # The existing chart supplies the grid; the output keeps its header shape.
    old = (
        "# Chords -- 09 Nights.m4a\n# key A#  80.2 BPM  3 bars\n1\tG#\n2\tA#\n3\tCm7\n"
    )
    grid = lc.read_grid(old)
    check(
        grid == ("# Chords -- 09 Nights.m4a", "A#", 80.2, 3), f"grid read (got {grid})"
    )
    raises(
        lambda: lc.read_grid("# Chords -- x\n1\tC\n"),
        "a chart with no tempo line is an error",
    )
    text = lc.chart_text(grid, ["G#", "A#", "Cm7"])
    check(
        text.splitlines()[:3]
        == [
            "# Chords -- 09 Nights.m4a",
            "# key A#  80.2 BPM  3 bars",
            "# chords from Logic Pro Chord ID",
        ],
        "header kept, source noted",
    )
    check(text.splitlines()[3:] == ["1\tG#", "2\tA#", "3\tCm7"], "one row per bar")

    # Logic's dialogs: a known one gets its answer, anything else is left for the wait to name.
    pressed: list[str] = []
    real_ax = lc.ax
    lc.ax = lambda *args: pressed.append(args[1]) or "pressed"
    try:
        tempo = "AXDialog\t\tThe added audio file contains tempo information. [Don’t Import][Import]"
        check(
            lc.answer_dialog(tempo) and pressed == ["Don’t Import"],
            "tempo question: Don't Import",
        )
        pressed.clear()
        rate = "AXDialog\t\tChange Project Sample Rate? [Change Project][Convert File][Cancel]"
        check(
            lc.answer_dialog(rate) and pressed == ["Change Project"],
            "sample rate: Change Project",
        )
        pressed.clear()
        save = "AXDialog\t\tDo you want to save? [Save][Don’t Save][Cancel]"
        check(
            not lc.answer_dialog(save) and pressed == [],
            "save question left alone while opening",
        )
        check(
            lc.answer_dialog(save, quitting=True) and pressed == ["Don’t Save"],
            "save question: Don't Save on quit",
        )
        pressed.clear()
        odd = "AXDialog\t\tSomething new happened. [OK]"
        check(
            not lc.answer_dialog(odd) and pressed == [],
            "an unknown dialog is not answered",
        )
        window = "AXStandardWindow\tUntitled - Tracks\t[Save]"
        check(not lc.answer_dialog(window) and pressed == [], "no dialog, no press")
    finally:
        lc.ax = real_ax

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
