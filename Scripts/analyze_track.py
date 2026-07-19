#!/usr/bin/env python3
"""
Detect tempo (BPM) and musical key of an audio file. Pure numpy — decodes via
ffmpeg, so no librosa/aubio needed (works on the demucs venv, incl. Python 3.14).

Tempo:  onset-strength envelope -> autocorrelation -> best lag in 60-180 BPM.
Key:    average chroma vector -> Krumhansl-Schmuckler profile correlation over
        all 24 major/minor keys.

Estimates, not ground truth — good enough to line up chops and pick a repitch.

Usage:
    analyze_track.py <audio file | folder>
"""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SR = 22050
FRAME = 2048
HOP = 512
PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Schmuckler key profiles.
_MAJ = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_MIN = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)


def decode_mono(path: Path, sr: int) -> np.ndarray:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            str(sr),
            "-f",
            "s16le",
            "-",
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.decode(errors="ignore") or "ffmpeg decode failed"
        )
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def _frames(audio: np.ndarray) -> np.ndarray:
    n = 1 + (len(audio) - FRAME) // HOP
    if n < 2:
        return np.empty((0, FRAME))
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(n)[:, None]
    return audio[idx] * np.hanning(FRAME).astype(np.float32)


@dataclass
class Spec:
    """One pass of spectral analysis, shared by all three detectors.

    `flux` is the RAW onset-strength envelope. detect_tempo subtracts its mean
    and estimate_boundaries does not, so the mean subtraction stays at the call
    site — folding it in here would silently change one of them.
    """

    mag: np.ndarray  # (n_frames, n_bins) magnitude spectrogram
    flux: np.ndarray  # (n_frames-1,) raw spectral flux
    fps: float  # envelope frames per second

    @property
    def n_frames(self) -> int:
        return self.mag.shape[0]


def spectra(audio: np.ndarray) -> Spec:
    """Frame, FFT, and difference the signal once.

    The FFT runs in chunks so the frame matrix and its transform are not both
    fully materialized — a 5-minute track is ~13k frames x 2048 samples.
    """
    frames = _frames(audio)
    fps = SR / HOP
    if frames.shape[0] == 0:
        return Spec(
            np.empty((0, FRAME // 2 + 1), np.float32), np.empty(0, np.float32), fps
        )
    chunks = [
        np.abs(np.fft.rfft(frames[i : i + 2048], axis=1)).astype(np.float32)
        for i in range(0, frames.shape[0], 2048)
    ]
    mag = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
    flux = np.sqrt((np.maximum(np.diff(mag, axis=0), 0.0) ** 2).sum(axis=1))
    return Spec(mag, flux, fps)


def detect_tempo(sp: Spec) -> float:
    if sp.n_frames < 4:
        return 0.0
    flux = sp.flux - sp.flux.mean()
    fps = sp.fps
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1 :]
    lo = int(fps * 60 / 180)  # 180 BPM
    hi = int(fps * 60 / 60)  # 60 BPM
    if hi >= len(ac):
        hi = len(ac) - 1
    if lo < 1 or hi <= lo:
        return 0.0
    lag = lo + int(np.argmax(ac[lo:hi]))
    return round(60.0 * fps / lag, 1)


def detect_key(sp: Spec) -> str:
    if sp.n_frames < 2:
        return "unknown"
    mag = sp.mag.mean(axis=0)
    freqs = np.fft.rfftfreq(FRAME, 1.0 / SR)
    chroma = np.zeros(12)
    for f, m in zip(freqs[1:], mag[1:]):
        if f < 27.5 or f > 5000:
            continue
        midi = 69 + 12 * np.log2(f / 440.0)
        chroma[int(round(midi)) % 12] += m
    if chroma.sum() == 0:
        return "unknown"
    chroma = chroma / chroma.sum()
    best_score, best = -2.0, "unknown"
    for i in range(12):
        for prof, mode in ((_MAJ, ""), (_MIN, "m")):
            r = np.corrcoef(chroma, np.roll(prof, i))[0, 1]
            if r > best_score:
                best_score, best = r, f"{PITCHES[i]}{mode}"
    return best


def estimate_boundaries(sp: Spec) -> list[float]:
    """Estimate section boundaries (in seconds) by analyzing spectral flux novelty."""
    if sp.n_frames < 10:
        return []
    flux = sp.flux

    # Smooth flux using a moving average window
    window_len = int(SR / HOP * 2.0)  # 2-second window
    if len(flux) < window_len:
        return []
    smoothed = np.convolve(flux, np.ones(window_len) / window_len, mode="same")
    novelty = flux - smoothed

    # Peak-picking: local maxima above threshold
    threshold = novelty.mean() + novelty.std() * 0.8
    peaks = []
    fps = SR / HOP
    for i in range(1, len(novelty) - 1):
        if (
            novelty[i] > novelty[i - 1]
            and novelty[i] > novelty[i + 1]
            and novelty[i] > threshold
        ):
            time_sec = round(i / fps, 1)
            peaks.append(time_sec)

    # Filter peaks closer than 8 seconds
    filtered = []
    for p in peaks:
        if not filtered or (p - filtered[-1]) >= 8.0:
            filtered.append(p)

    return filtered


def analyze(path: Path) -> tuple[float, str, list[float]]:
    sp = spectra(decode_mono(path, SR))
    return detect_tempo(sp), detect_key(sp), estimate_boundaries(sp)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: analyze_track.py <audio file | folder>")
        sys.exit(1)
    p = Path(sys.argv[1])
    if p.is_dir():
        files = sorted(
            f
            for f in p.rglob("*")
            if f.suffix.lower() in (".m4a", ".mp3", ".wav", ".flac")
        )
    else:
        files = [p]
    if not files:
        print("No audio files found.")
        sys.exit(1)
    for f in files:
        try:
            bpm, key, bounds = analyze(f)
            print(f"{f.name}:  {bpm} BPM   key {key}   transitions {bounds}")
        except Exception as exc:  # noqa: BLE001
            print(f"{f.name}:  analysis failed — {exc}")


if __name__ == "__main__":
    main()
