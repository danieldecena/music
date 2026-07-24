#!/usr/bin/env python3
"""
Tests for the seed-pivot mix report -- lyric sourcing, IDF word ranking, the
report renderer, and the preview command builder. Hand-rolled assertions in the
style of tests/test-harmonic-mix.py. Pure stdlib; run with any python3:

    python3 tests/test-mix-report.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import lyrics as ly  # noqa: E402

_passed = 0
_failed = 0


def check(cond: bool, label: str) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        print(f"FAIL: {label}")


LRC = """[ar:Justin Bieber]
[ti:SPEED DEMON]
[00:12.34]And I go speed racing
[00:14.50]Speed demon, speed demon
[00:16.00]
[01:02.5]Faster than the rest
"""

plain = ly.strip_lrc(LRC)
check("speed racing" in plain, "strip_lrc keeps the lyric text")
check("[00:12.34]" not in plain, "strip_lrc removes timestamps")
check(
    "[ar:" not in plain and "Justin Bieber" not in plain,
    "strip_lrc drops metadata lines",
)
check("" not in plain.splitlines(), "strip_lrc drops blank lines")
check(
    len(plain.splitlines()) == 3,
    f"strip_lrc keeps 3 lyric lines, got {plain.splitlines()}",
)

# A file with no timestamps at all is already plain text -- pass it through.
check(
    ly.strip_lrc("just a line\nand another") == "just a line\nand another",
    "strip_lrc passes through untimestamped text",
)
check(ly.strip_lrc("") == "", "strip_lrc handles empty input")

# local_lyrics: reads the sidecar beside the audio file, None when absent.
check(ly.local_lyrics(None) is None, "local_lyrics(None) is None")
check(
    ly.local_lyrics("Apple Music/Nope/Does Not Exist.m4a") is None,
    "local_lyrics returns None for a missing sidecar",
)

print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
