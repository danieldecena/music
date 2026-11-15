#!/usr/bin/env python3
"""
Tests for Scripts/align_chart.py: finding a record's beat (tempo and where the first beat falls)
and its first downbeat (the beat Logic's chord changes fall on). Hand-rolled assertions:

    .venv/bin/python tests/test-align-chart.py
"""

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import align_chart as al

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


def pulses(bpm: float, first: float, seconds: float, fps: float) -> np.ndarray:
    """An onset envelope with a spike on every beat, the first `first` seconds in."""
    env = np.zeros(int(seconds * fps))
    t = first
    while t < seconds:
        env[round(t * fps)] = 1.0
        t += 60 / bpm
    return env


def main() -> int:
    fps = 43.07
    env = pulses(110.2, 0.32, 120, fps)
    bpm, first = al.beat_grid(env, fps, 108, 112)
    check(abs(bpm - 110.2) < 0.06, f"tempo found (got {bpm})")
    check(abs(first - 0.32) < 0.03, f"first beat found (got {first})")
    # Known-bad control: a search range that excludes the real tempo does not land on it.
    bpm2, _ = al.beat_grid(env, fps, 100, 104)
    check(
        abs(bpm2 - 110.2) > 5, f"control found a tempo outside its range (got {bpm2})"
    )

    # Chord changes on beat 3 of every bar of a 120 BPM grid whose first beat is 0.5 s in: bar 1
    # starts two beats after the first beat.
    beat = 0.5
    changes = [0.5 + beat * (2 + 4 * n) for n in range(12)]
    start = al.downbeat(changes, first_beat=0.5, bpm=120)
    check(abs(start - (0.5 + 2 * beat)) < 1e-9, f"downbeat on beat 3 (got {start})")
    # Control: changes on beat 1 keep the first beat as the downbeat.
    start1 = al.downbeat(
        [0.5 + beat * 4 * n for n in range(12)], first_beat=0.5, bpm=120
    )
    check(abs(start1 - 0.5) < 1e-9, f"downbeat on beat 1 (got {start1})")
    # No changes to go by: the first beat stands.
    check(
        al.downbeat([], first_beat=0.5, bpm=120) == 0.5,
        "no changes keep the first beat",
    )

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
