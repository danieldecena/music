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
AUDIO_EXT = (".m4a", ".mp3", ".wav", ".flac")
STEM_NAMES = ("vocals", "drums", "bass", "other", "guitar", "piano")

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


def _chroma_projection() -> tuple[np.ndarray, np.ndarray]:
    """Bin mask and (n_kept_bins, 12) pitch-class projection matrix.

    Range is 55-2000 Hz, narrowed from the original 27.5-5000. Below 55 Hz a
    2048-point FFT at 22050 Hz has ~10.8 Hz resolution, so a single bin spans
    more than a semitone — those bins were charging noise to a pitch class.
    Above ~2000 Hz is mostly cymbals and air.

    The Gaussian weight favours roughly C3-C6, the register where pitch class is
    legible, instead of treating every octave as equally informative.
    """
    freqs = np.fft.rfftfreq(FRAME, 1.0 / SR)
    keep = (freqs >= 55.0) & (freqs <= 2000.0)
    midi = 69 + 12 * np.log2(freqs[keep] / 440.0)
    weight = np.exp(-0.5 * ((midi - 60.0) / 18.0) ** 2)
    proj = np.zeros((keep.sum(), 12), np.float32)
    proj[np.arange(keep.sum()), np.rint(midi).astype(int) % 12] = weight
    return keep, proj


_KEEP, _PROJ = _chroma_projection()


def _chroma_vector(sp: Spec) -> np.ndarray | None:
    """Average energy per pitch class, L1-normalized. None if nothing to read.

    Three cheap defenses against percussive smear, in place of a median-filter
    HPSS that would cost far more memory than it is worth here:

      1. log1p compression, so one loud hit cannot dominate the average;
      2. per-frame L1 normalization, so a snare frame counts the same as a frame
         of sustained pads rather than eight times as much;
      3. dropping the top 15% of frames by spectral flux — transients are
         exactly where broadband energy smears across every pitch class.
    """
    if sp.n_frames < 2:
        return None
    m = np.log1p(sp.mag[:, _KEEP])
    if sp.flux.size and m.shape[0] > 1:
        quiet = np.ones(m.shape[0], bool)
        quiet[1:] = sp.flux <= np.percentile(sp.flux, 85)
        if quiet.sum() >= 8:
            m = m[quiet]
    c = m @ _PROJ
    total = c.sum(axis=1, keepdims=True)
    c = np.divide(c, total, out=np.zeros_like(c), where=total > 0)
    chroma = c.mean(axis=0).astype(np.float64)
    if chroma.sum() == 0:
        return None
    return chroma / chroma.sum()


def _key_profiles() -> tuple[np.ndarray, list[str]]:
    """All 24 rotated key profiles, z-scored, plus their names."""
    rows, names = [], []
    for i in range(12):
        for prof, mode in ((_MAJ, ""), (_MIN, "m")):
            rows.append(np.roll(prof, i))
            names.append(f"{PITCHES[i]}{mode}")
    p = np.array(rows)
    p = (p - p.mean(axis=1, keepdims=True)) / p.std(axis=1, keepdims=True)
    return p, names


_PROFILES, _PROFILE_NAMES = _key_profiles()


def _key_from_chroma(chroma: np.ndarray | None) -> str:
    """Best-correlating Krumhansl-Schmuckler key for a chroma vector.

    Correlating against all 24 profiles at once: z-scoring both sides makes the
    Pearson correlation a plain dot product, so this is one (24,12) @ (12,)
    instead of 24 separate np.corrcoef calls.
    """
    if chroma is None or chroma.sum() == 0:
        return "unknown"
    std = chroma.std()
    if std == 0:
        return "unknown"
    z = (chroma - chroma.mean()) / std
    return _PROFILE_NAMES[int(np.argmax(_PROFILES @ z))]


def detect_key(sp: Spec) -> str:
    return _key_from_chroma(_chroma_vector(sp))


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


def stem_track_dir(p: Path) -> dict[str, Path] | None:
    """Return the stem files if `p` is a separated track folder, else None.

    Gated on drums AND bass both being present. That admits htdemucs (4-stem)
    and htdemucs_6s (which adds guitar/piano), while excluding an acapella split
    — that produces only vocals.wav and no_vocals.wav, which is not a track
    folder and should keep fanning out per file.
    """
    if not p.is_dir():
        return None
    found = {n: p / f"{n}.wav" for n in STEM_NAMES if (p / f"{n}.wav").is_file()}
    return found if {"drums", "bass"} <= found.keys() else None


def analyze_stem_track(stems: dict[str, Path]) -> tuple[float, str, list[float]]:
    """Analyze a separated track as ONE track, using the best stem per metric.

    Previously a Stems folder was rglobbed into one line per stem, so the
    reported "key" could come from drums.wav — which is meaningless. Each metric
    now reads the stem that carries it: drums for tempo (cleanest onsets), the
    pitched stems for key, and `other` for boundaries (harmonic change marks
    sections better than percussion does).
    """
    bpm = detect_tempo(spectra(decode_mono(stems["drums"], SR)))

    # Bass pins the tonic but cannot distinguish major from minor -- the third
    # lives in the mid stems. Weight bass below them rather than above.
    key_parts = [(stems["bass"], 0.6)]
    key_parts += [(stems[n], 1.0) for n in ("other", "guitar", "piano") if n in stems]
    chroma = np.zeros(12)
    for path, weight in key_parts:
        sp = spectra(decode_mono(path, SR))
        c = _chroma_vector(sp)
        if c is not None:
            chroma += weight * c
    key = _key_from_chroma(chroma)

    bounds_src = stems.get("other") or stems["bass"]
    bounds = estimate_boundaries(spectra(decode_mono(bounds_src, SR)))
    return bpm, key, bounds


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: analyze_track.py <audio file | folder>")
        sys.exit(1)
    p = Path(sys.argv[1])

    stems = stem_track_dir(p)
    if stems is not None:
        try:
            bpm, key, bounds = analyze_stem_track(stems)
            print(f"{p.name}:  {bpm} BPM   key {key}   transitions {bounds}")
        except Exception as exc:  # noqa: BLE001
            print(f"{p.name}:  analysis failed — {exc}")
        return

    if p.is_dir():
        files = sorted(f for f in p.rglob("*") if f.suffix.lower() in AUDIO_EXT)
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
