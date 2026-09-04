"""Tests for score_apple. Hand-rolled assertions, matching tests/test-analysis.py.

Run: .venv/bin/python tests/test_score_apple.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import score_apple as sa  # noqa: E402

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


def main() -> None:
    # A second implementation of "is this an octave error" that disagreed with
    # tests/test-analysis.py would make the comparison meaningless, so these
    # assert reuse rather than logic.
    check(sa.bpm_class(116.0, 116.0) == "exact", "116 vs 116 is exact")
    check(sa.bpm_class(232.0, 116.0) == "double", "232 vs 116 is double")
    check(sa.bpm_class(58.0, 116.0) == "half", "58 vs 116 is half")
    # Observed 113.007 against a published 116: inside the 4.5% band.
    check(sa.bpm_class(113.007, 116.0) == "exact", "Ivy 113.007 vs 116 is exact")
    # Observed Nikes 69.0 against a labelled 137.
    check(sa.bpm_class(69.0, 137.0) == "half", "Nikes 69 vs 137 is half")

    # mu-analyze encodes non-finite loudness as a string.
    check(sa.as_float("-inf") == float("-inf"), "as_float parses '-inf'")
    check(sa.as_float("inf") == float("inf"), "as_float parses 'inf'")
    check(sa.as_float(-7.25) == -7.25, "as_float passes numbers through")

    check(sa.apple_key({"tonic": "c", "mode": "major"}) == "C", "apple_key c major")
    check(sa.apple_key({"tonic": "aflat", "mode": "major"}) == "Ab", "apple_key aflat")
    check(sa.apple_key({"tonic": "csharp", "mode": "minor"}) == "C#m", "apple_key csharp minor")
    check(sa.apple_key({"tonic": "eflat", "mode": "minor"}) == "Ebm", "apple_key eflat minor")

    # Self Control is labelled G#; Apple returns Ab. Same pitch -- the eyeballed
    # table wrongly read these as misses.
    check(sa.key_class("Ab", "G#") == "exact", "Ab vs G# is exact (enharmonic)")
    check(sa.key_class("Bb", "A#") == "exact", "Bb vs A# is exact (enharmonic)")
    # Ivy: Apple says C major, the label says Am.
    check(sa.key_class("C", "Am") == "relative", "C vs Am is relative")

    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
