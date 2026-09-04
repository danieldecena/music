"""Tests for the timed .lrc parser.

Hand-rolled assertions, matching tests/test_regions.py.
Run: .venv/bin/python tests/test_lyrics_timed.py
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Scripts"))

from lyrics import strip_lrc, timed_lrc  # noqa: E402

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


SAMPLE = """[ar:Frank Ocean]
[ti:Ivy]
[00:00.77]I thought that I was dreamin'
[00:03.15]When you said you loved me
[00:07.51]The start of nothing
"""


def main() -> None:
    rows = timed_lrc(SAMPLE)
    check(len(rows) == 3, f"metadata tags are dropped, lyric lines kept ({len(rows)})")
    check(abs(rows[0][0] - 0.77) < 1e-6, "mm:ss.cc parses to seconds")
    check(rows[0][2] == "I thought that I was dreamin'",
          "the timestamp is stripped from the text")

    # A line runs until the next one starts, so a gap belongs to the line before.
    check(abs(rows[0][1] - 3.15) < 1e-6, "a line ends where the next begins")
    check(rows[-1][1] is None,
          "the last line has no end -- the parser cannot know the duration")

    # Minutes must actually multiply, not concatenate.
    r = timed_lrc("[02:05.50]late line")
    check(abs(r[0][0] - 125.5) < 1e-6, "minutes carry (2:05.50 -> 125.5s)")

    # Two decimal places and three both occur in the wild.
    r = timed_lrc("[00:01.5]a\n[00:02.250]b")
    check(len(r) == 2 and abs(r[1][0] - 2.25) < 1e-6, "1 and 3 decimal places parse")

    # A repeated chorus line carries several stamps on one line.
    r = timed_lrc("[00:10.00][01:20.00]same words")
    check(len(r) == 2 and r[0][0] == 10.0 and r[1][0] == 80.0,
          "one line with two timestamps yields two rows")

    # Out-of-order input must not produce a negative-length line.
    r = timed_lrc("[00:09.00]second\n[00:01.00]first")
    check([x[2] for x in r] == ["first", "second"], "rows come back in time order")
    check(all(e is None or e > s for s, e, _ in r), "no line ends before it starts")

    # Degenerate inputs must not raise.
    check(timed_lrc("") == [], "empty input returns []")
    check(timed_lrc("[ar:Nobody]\n") == [], "metadata only returns []")
    check(timed_lrc("no timestamp here") == [], "untimed text is not a lyric line")
    check(timed_lrc("[00:04.00]   ") == [], "a stamp with no words is dropped")

    # The existing parser is untouched -- the mix report depends on it.
    check(strip_lrc(SAMPLE).splitlines()[0] == "I thought that I was dreamin'",
          "strip_lrc still returns plain text")
    check("[00:00.77]" not in strip_lrc(SAMPLE), "strip_lrc still removes timestamps")

    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
