"""Tests for the loop region scorer.

Hand-rolled assertions, matching tests/test-analysis.py.
Run: .venv/bin/python tests/test_regions.py
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Scripts"))

from regions import score_loops  # noqa: E402

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


def grid(n_bars: int = 16, bar_s: float = 2.0):
    """A synthetic 4/4 grid: n_bars bars of bar_s seconds, four beats each."""
    bars = [{"idx": i, "t": i * bar_s} for i in range(n_bars)]
    beats = [
        {"idx": i, "t": i * (bar_s / 4), "bar": i // 4} for i in range(n_bars * 4)
    ]
    return beats, bars


def main() -> None:
    beats, bars = grid()

    # Vocals loud over the first half, silent over the second.
    activity = [
        {"instrument": "vocal", "start_s": 0.0, "end_s": 16.0, "level": 0.9},
        {"instrument": "vocal", "start_s": 16.0, "end_s": 32.0, "level": 0.0},
    ]
    loops = score_loops(beats, bars, [], activity, n_bars=4)
    check(bool(loops), "returns candidates")
    best = max(loops, key=lambda r: r["score"])
    check(best["start_s"] >= 16.0,
          f"the vocal-free half wins (best starts at {best['start_s']})")

    # Every candidate must begin on a bar line, or the chop lands off-grid.
    starts = {r["start_s"] for r in loops}
    check(starts <= {b["t"] for b in bars}, "every candidate starts on a bar")
    check(all(r["n_bars"] == 4 for r in loops), "every candidate is n_bars long")
    check(all(r["end_s"] > r["start_s"] for r in loops), "spans are non-empty")

    # A window inside one section should beat an identical window straddling
    # two, because a loop crossing a boundary usually changes underneath.
    sections = [
        {"label": "section", "start_s": 0.0, "end_s": 16.0},
        {"label": "section", "start_s": 16.0, "end_s": 32.0},
    ]
    flat = [{"instrument": "vocal", "start_s": 0.0, "end_s": 32.0, "level": 0.0}]
    withsec = {r["start_s"]: r["score"] for r in
               score_loops(beats, bars, sections, flat, n_bars=4)}
    check(withsec.get(0.0, 0) > withsec.get(12.0, 0),
          "a contained window outranks one straddling a section boundary")

    # Degenerate inputs must not raise.
    check(score_loops([], [], [], [], n_bars=4) == [], "empty input returns []")
    check(score_loops(beats, bars[:2], [], [], n_bars=4) == [],
          "fewer bars than the window returns []")

    # The instruments present are reported, so the UI can say what is in there.
    mixed = [
        {"instrument": "vocal", "start_s": 0.0, "end_s": 32.0, "level": 0.0},
        {"instrument": "drum", "start_s": 0.0, "end_s": 32.0, "level": 0.8},
    ]
    r = score_loops(beats, bars, [], mixed, n_bars=4)[0]
    check("drum" in r["instruments"] and r["instruments"]["drum"] > 0.5,
          "reports per-instrument levels")

    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
