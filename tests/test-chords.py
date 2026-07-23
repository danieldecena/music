#!/usr/bin/env python3
"""
Tests for Scripts/chords.py. Hand-rolled assertions in the style of
tests/test-analysis.py. Run with the venv python (numpy required):

    .venv/bin/python tests/test-chords.py [all|unit|audio|exitcode]
"""

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import chords as ch  # noqa: E402

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


def _chroma(*pcs: int) -> np.ndarray:
    """L1-normalized chroma with unit energy on the given pitch classes."""
    v = np.zeros(12)
    for p in pcs:
        v[p] = 1.0
    return v / v.sum()


def unit() -> None:
    # Triad + 7th recovery at root C (pitch classes: C=0 E=4 G=7 A=9 Bb=10 B=11).
    check(ch.label_bar(_chroma(0, 4, 7), None) == "C", "C major triad -> C")
    check(ch.label_bar(_chroma(0, 3, 7), None) == "Cm", "C minor triad -> Cm")
    check(ch.label_bar(_chroma(0, 4, 7, 10), None) == "C7", "C dom7 -> C7")
    check(ch.label_bar(_chroma(0, 4, 7, 11), None) == "Cmaj7", "C maj7 -> Cmaj7")
    check(ch.label_bar(_chroma(0, 3, 7, 10), None) == "Cm7", "C min7 -> Cm7")

    # Root coverage: a rolled triad must resolve to its own root.
    check(ch.label_bar(_chroma(2, 6, 9), None) == "D", "D major triad -> D")

    # Empty / flat bar -> placeholder, never a crash.
    check(ch.label_bar(np.zeros(12), None) == "-", "flat chroma -> '-'")
    check(ch.label_bar(None, None) == "-", "None chroma -> '-'")

    # Diatonic set correctness (C major: I ii iii IV V vi as triads + 7ths).
    dia = ch._diatonic_names("C")
    check({"C", "Dm", "Em", "F", "G", "Am"} <= dia, "C major diatonic triads present")
    check({"G7", "Fmaj7", "Cmaj7", "Dm7"} <= dia, "C major diatonic 7ths present")
    check("C#" not in dia and "C#m" not in dia, "C# not diatonic to C major")
    check(ch._diatonic_names("unknown") == set(), "unknown key -> empty diatonic set")

    # A minor (natural minor: i III iv v VI VII).
    diam = ch._diatonic_names("Am")
    check({"Am", "C", "Dm", "Em", "F", "G"} <= diam, "A minor diatonic triads present")

    # Soft prior discrimination. Blend is 55% C major + 45% C minor: pure match
    # picks C (the louder triad), but C is out of key in D# major while Cm is its
    # diatonic vi -- a strong prior flips the label to Cm. The prior must NOT fire
    # when there is no mask (unknown key).
    blend = 0.55 * _chroma(0, 4, 7) + 0.45 * _chroma(0, 3, 7)
    check(ch.label_bar(blend, None) == "C", "blend, no prior -> C (pure match)")
    mask_dsharp = ch._diatonic_mask("D#")
    check(
        ch.label_bar(blend, mask_dsharp, prior=5.0) == "Cm",
        "blend, strong D# prior -> Cm",
    )
    check(ch.label_bar(blend, None, prior=5.0) == "C", "no mask -> prior inert")


def _tone(freqs, secs: float) -> np.ndarray:
    t = np.arange(int(secs * ch.at.SR)) / ch.at.SR
    return sum(np.sin(2 * np.pi * f * t) for f in freqs).astype(np.float32) / len(freqs)


def audio() -> None:
    # 8 bars of a sustained C major triad at 120 BPM: 8 bars * 4 beats * 0.5 s.
    # detect_tempo is unreliable on a beatless drone, so drive bar_chroma with a
    # known BPM -- this isolates the chroma/label path, not tempo detection.
    audio_sig = _tone([261.63, 329.63, 392.00], secs=8 * 4 * 0.5)
    sp = ch.at.spectra(audio_sig)
    bars = ch.bar_chroma(sp, 120.0)
    n = None if bars is None else len(bars)
    check(bars is not None and len(bars) >= 6, f"C drone -> >=6 bars (got {n})")
    if bars is not None:
        labels = [ch.label_bar(b, None) for b in bars]
        c_count = sum(1 for x in labels if x == "C")
        check(
            c_count >= len(labels) - 1,
            f"C drone bars label C ({c_count}/{len(labels)})",
        )

    # Too short to bar -> None.
    check(
        ch.bar_chroma(ch.at.spectra(_tone([440.0], secs=0.2)), 120.0) is None,
        "0.2s -> None bars",
    )


def _write_wav(path: Path, audio_sig: np.ndarray) -> None:
    pcm = (np.clip(audio_sig, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(ch.at.SR)
        w.writeframes(pcm.tobytes())


def _clicks_over_tone(bpm: float, secs: float) -> np.ndarray:
    """A tonal C-major bed with periodic clicks, so both tempo and chroma exist."""
    bed = _tone([261.63, 329.63, 392.00], secs=secs)
    period = int(ch.at.SR * 60.0 / bpm)
    for i in range(0, len(bed), period):
        bed[i : i + 200] += 0.8  # a short broadband tick on each beat
    return bed


def exitcode() -> None:
    script = REPO / "Scripts" / "chords.py"
    with tempfile.TemporaryDirectory() as d:
        bad = Path(d) / "garbage.wav"
        bad.write_bytes(b"not audio, just bytes " * 64)
        r = subprocess.run(
            [sys.executable, str(script), str(bad)], capture_output=True, text=True
        )
        check(r.returncode != 0, f"bad file -> non-zero exit (got {r.returncode})")
        check(
            "chord analysis failed" in r.stdout,
            "bad file -> prints 'chord analysis failed'",
        )

        good = Path(d) / "good.wav"
        _write_wav(good, _clicks_over_tone(120.0, secs=12.0))
        r = subprocess.run(
            [sys.executable, str(script), str(good)], capture_output=True, text=True
        )
        check(r.returncode == 0, f"good file -> zero exit (got {r.returncode})")
        check(
            (Path(d) / "chords.txt").is_file(),
            "good file -> writes chords.txt beside it",
        )
        check("BPM" in r.stdout, "good file -> prints a chart header")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("all", "unit"):
        unit()
    if mode in ("all", "audio"):
        audio()
    if mode in ("all", "exitcode"):
        exitcode()
    if mode not in ("all", "unit", "audio", "exitcode"):
        print(f"unknown mode: {mode}")
        sys.exit(2)
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
