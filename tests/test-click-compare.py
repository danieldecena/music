#!/usr/bin/env python3
"""
Tests for Scripts/click_compare.py. Hand-rolled assertions in the style of
tests/test-chords.py. Run with the venv python (numpy required):

    .venv/bin/python tests/test-click-compare.py [all|unit|render]
"""

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import click_compare as cc  # noqa: E402

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


def unit() -> None:
    # candidate_bpms: estimate + half/double/1.5x/0.667x, sorted, deduped.
    c = cc.candidate_bpms(120.0)
    check(120.0 in c, "candidates include the base")
    check(60.0 in c, "candidates include the half octave")
    check(180.0 in c and 80.0 in c, "candidates include 3:2 partners")
    mid = cc.candidate_bpms(90.0)  # both octaves in range: 45 and 180
    check(180.0 in mid and 45.0 in mid, "candidates include octaves for a mid base")
    check(c == sorted(c), "candidates sorted ascending")
    check(len(c) == len(set(c)), "candidates deduped")

    # Out-of-range octaves are dropped (240 stays, 30 drops below BPM_MIN).
    lo = cc.candidate_bpms(60.0)
    check(all(cc.BPM_MIN <= x <= cc.BPM_MAX for x in lo), "candidates in range")
    check(30.0 not in lo, "sub-range octave dropped")

    # A label BPM is folded in and deduped against generated ones.
    withlabel = cc.candidate_bpms(100.0, [137.0])
    check(137.0 in withlabel, "label BPM included")
    dupe = cc.candidate_bpms(100.0, [200.0])  # 200 == 100*2 already present
    check(dupe.count(200.0) == 1, "label duplicate collapsed")

    # beat_times: right count and spacing.
    bt = cc.beat_times(120.0, 4.0)  # 2 beats/sec over 4s -> 8 beats (t=0..3.5)
    check(len(bt) == 8, "beat count at 120 BPM over 4s")
    check(abs((bt[1] - bt[0]) - 0.5) < 1e-6, "beat spacing = 60/bpm")
    check(cc.beat_times(0.0, 4.0) == [], "zero BPM -> no beats")

    # render_click: peaks land at beats, silence between.
    sr = 22050
    click = cc.render_click(120.0, 2.0, sr)
    check(click.shape[0] == int(2.0 * sr), "click length matches duration")
    onset0 = float(np.max(np.abs(click[: int(0.04 * sr)])))
    mid = float(np.max(np.abs(click[int(0.20 * sr) : int(0.45 * sr)])))
    check(onset0 > 0.3, "click energy at the downbeat")
    check(mid < 1e-4, "silence between beats")

    # mix_click never clips and keeps the excerpt length.
    exc = (np.random.default_rng(0).standard_normal(sr) * 0.1).astype(np.float32)
    mixed = cc.mix_click(exc, 128.0, sr)
    check(mixed.shape[0] == exc.shape[0], "mix keeps excerpt length")
    check(float(np.max(np.abs(mixed))) <= 1.0, "mix does not clip")

    # excerpt_of clamps to the audio bounds.
    a = np.arange(sr * 3, dtype=np.float32)
    e = cc.excerpt_of(a, sr, start=2.0, dur=5.0)  # only 1s remains
    check(e.shape[0] == sr, "excerpt clamps to remaining audio")


def _sine_wav(path: Path, sr: int, secs: float, hz: float) -> None:
    t = np.arange(int(sr * secs)) / sr
    pcm = (np.sin(2 * np.pi * hz * t) * 0.5 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def render() -> None:
    # End-to-end non-interactive: --render-only writes one WAV per candidate.
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        src = tdp / "tone.wav"
        _sine_wav(src, 22050, 6.0, 220.0)
        out = tdp / "mixes"
        r = subprocess.run(
            [
                sys.executable,
                str(REPO / "Scripts" / "click_compare.py"),
                str(src),
                "--bpm",
                "120",
                "--dur",
                "3",
                "--start",
                "0",
                "--render-only",
                str(out),
            ],
            capture_output=True,
            text=True,
        )
        check(r.returncode == 0, "render-only exits 0")
        wavs = sorted(out.glob("*.wav"))
        check(len(wavs) == len(cc.candidate_bpms(120.0)), "one mix per candidate")
        check(all(w.stat().st_size > 1000 for w in wavs), "mixes are non-empty")

    # A non-stem directory is refused cleanly (non-zero, no traceback).
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(
            [sys.executable, str(REPO / "Scripts" / "click_compare.py"), td],
            capture_output=True,
            text=True,
        )
        check(r.returncode == 1, "non-stem dir exits 1")
        check("Traceback" not in r.stderr, "non-stem dir: clean error, no traceback")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("all", "unit"):
        unit()
    if mode in ("all", "render"):
        render()
    if mode not in ("all", "unit", "render"):
        print(f"unknown mode: {mode}")
        sys.exit(2)
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
