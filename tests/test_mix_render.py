"""Tests for the bar-aligned mix renderer.

Hand-rolled assertions, matching tests/test_regions.py. No ffmpeg is invoked --
every function under test is pure, and the argv is checked as data.
Run: .venv/bin/python tests/test_mix_render.py
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Scripts"))

from mix_render import (  # noqa: E402
    bar_time, layer_args, stretch_for, transition_args,
)

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


def grid(n=32, bar_s=2.0, t0=0.0):
    return [t0 + i * bar_s for i in range(n)]


def near(a, b, tol=1e-6):
    return abs(a - b) < tol


def main() -> None:
    bars = grid()

    # --- bar_time -----------------------------------------------------------
    check(near(bar_time(bars, 0), 0.0), "bar 0 is the first downbeat")
    check(near(bar_time(bars, 4), 8.0), "bar 4 on a 2s grid is 8s")
    check(near(bar_time(bars, 4.5), 9.0), "fractional bars interpolate")
    check(near(bar_time(bars, 33), 66.0), "past the last bar extrapolates, not clamps")
    check(near(bar_time([5.0], 3), 5.0), "a one-bar grid degrades to that bar")

    # A drifting grid: bars get longer, as Apple's tracking reports for Ivy.
    drift = [0.0, 2.0, 4.2, 6.6, 9.2, 12.0]
    check(near(bar_time(drift, 3), 6.6), "reads a drifting grid directly")
    check(bar_time(drift, 4) - bar_time(drift, 3) > bar_time(drift, 1) - bar_time(drift, 0),
          "a later bar is longer when the tempo drifts")

    # --- stretch_for --------------------------------------------------------
    count, ratio, a_dur, b_dur = stretch_for(bars, 0, grid(bar_s=2.0), 0, 4)
    check(count == 4 and near(ratio, 1.0), "same tempo needs no stretch")
    check(near(a_dur, 8.0) and near(b_dur, 8.0), "durations come off the grid")

    # B at double tempo: take twice the bars rather than slow it to half speed.
    count, ratio, a_dur, b_dur = stretch_for(bars, 0, grid(bar_s=1.0), 0, 4)
    check(count == 8, "against a double-tempo track it takes 8 bars, not 4")
    check(near(ratio, 1.0), "and so needs no stretch")

    # B at half tempo: take half the bars.
    count, ratio, _, _ = stretch_for(bars, 0, grid(bar_s=4.0), 0, 4)
    check(count == 2, "against a half-tempo track it takes 2 bars")
    check(near(ratio, 1.0), "again no stretch")

    # A genuine mismatch does get stretched, and stays inside atempo's range.
    count, ratio, a_dur, b_dur = stretch_for(bars, 0, grid(bar_s=2.3), 0, 4)
    check(0.5 <= ratio <= 2.0, "the rate stays inside atempo's accepted range")
    check(near(b_dur / ratio, a_dur), "stretching B's cut makes it fill A's window")

    # The measured path beats a BPM ratio: on a drifting grid the right stretch
    # depends on which bars you took, which a single BPM number cannot express.
    slow_end = [0.0, 2.0, 4.0, 6.0, 8.0, 11.0, 14.0, 17.0, 20.0]
    _, r_early, _, _ = stretch_for(bars, 0, slow_end, 0, 4)
    _, r_late, _, _ = stretch_for(bars, 0, slow_end, 4, 4)
    check(not near(r_early, r_late),
          "the same tracks need different rates at different points in the song")

    # --- layer_args ---------------------------------------------------------
    args = layer_args([pathlib.Path("a1.wav"), pathlib.Path("a2.wav")],
                      [pathlib.Path("b1.wav")],
                      10.0, 8.0, 20.0, 8.0, 1.0, pathlib.Path("out.wav"))
    fc = args[args.index("-filter_complex") + 1]
    check(args.count("-i") == 3, "one -i per source, both sides")
    check("amix=inputs=3" in fc, "every source reaches the mix")
    check(fc.count("atempo") == 1, "only B is stretched")
    check("[b0]" in fc and "atempo" in fc.split("[b0]")[0],
          "the atempo sits on B's chain, not A's")
    check("normalize=0" in fc, "levels are kept rather than halved per input")
    check("alimiter" in fc, "the sum is limited, so two masters cannot clip")
    check("-vn" in args, "cover-art video streams are dropped")
    check(args[-1] == "out.wav", "the output path lands last")

    # Both sides are cut at their own downbeats, with their own durations.
    durs = [args[i + 1] for i, v in enumerate(args) if v == "-t"]
    check(durs == ["8", "8", "8"], "each source carries its side's duration")
    starts = [args[i + 1] for i, v in enumerate(args) if v == "-ss"]
    check(starts == ["10", "10", "20"], "each source carries its own side's start")

    # --- transition_args ----------------------------------------------------
    t = transition_args(pathlib.Path("a.m4a"), pathlib.Path("b.m4a"),
                        10.0, 16.0, 4.0, 16.0, 1.25, 4.0, pathlib.Path("t.wav"))
    tfc = t[t.index("-filter_complex") + 1]
    check("acrossfade=d=4" in tfc, "the fade length reaches ffmpeg")
    check("atempo=1.250000" in tfc, "B is stretched onto A's grid")
    check("amix" not in tfc, "a transition is sequential, not layered")

    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
