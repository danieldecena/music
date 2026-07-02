#!/usr/bin/env python3
"""
Split a drum stem (drums.wav) into individual one-shot hits using spectral-flux
onset detection. Pure numpy — no librosa/aubio, so it works on the demucs venv
(incl. Python 3.14) with nothing extra to install.

Detection runs on a mono 22.05 kHz decode of the file; each hit is then cut from
the ORIGINAL file with ffmpeg stream-copy, so the exported one-shots keep full
quality and stereo. Output mirrors chop.py's layout:

    Samples/One-Shots/<source-folder-name>/<stem>_001.wav, _002.wav, ...

Usage:
    slice_drums.py <drums.wav | Stems folder> <output_dir> [--delta D] [--wait S]
                   [--max-len S] [--min-len S]
"""

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

DETECT_SR = 22050  # detection-only decode rate (slicing uses the original file)
FRAME = 1024
HOP = 512


def decode_mono(path: Path, sr: int) -> np.ndarray:
    """Decode any audio file to a mono float32 array at `sr` via ffmpeg."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="ignore") or "ffmpeg decode failed")
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def get_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def onset_times(audio: np.ndarray, sr: int, delta: float, wait_s: float) -> list[float]:
    """Onset start times (seconds) via spectral flux + adaptive peak picking.

    delta   — how far above the local-average flux a peak must rise to count as a
              hit (lower = more sensitive = more hits).
    wait_s  — minimum spacing between hits, seconds (debounces flams/ringing).
    """
    if audio.size < FRAME * 2:
        return []
    window = np.hanning(FRAME).astype(np.float32)
    n_frames = 1 + (len(audio) - FRAME) // HOP
    if n_frames < 2:
        return []
    # Frame the signal (n_frames, FRAME) and take the magnitude spectrum.
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = audio[idx] * window
    mag = np.abs(np.fft.rfft(frames, axis=1))
    # Spectral flux = energy of positive bin-to-bin increases between frames.
    diff = np.diff(mag, axis=0)
    flux = np.sqrt((np.maximum(diff, 0.0) ** 2).sum(axis=1))
    if flux.max() > 0:
        flux = flux / flux.max()
    # Adaptive threshold: local mean of the flux curve, plus delta.
    w = 8
    pad = np.pad(flux, (w, w), mode="edge")
    local_mean = np.convolve(pad, np.ones(2 * w + 1) / (2 * w + 1), mode="valid")
    thresh = local_mean + delta
    # Peak-pick: above threshold and a local maximum, respecting the wait gap.
    wait_frames = max(1, int(round(wait_s * sr / HOP)))
    times, last = [], -wait_frames
    for i in range(1, len(flux) - 1):
        if (flux[i] >= thresh[i] and flux[i] > flux[i - 1]
                and flux[i] >= flux[i + 1] and i - last >= wait_frames):
            times.append(i * HOP / sr)
            last = i
    return times


def slice_hits(src: Path, out_dir: Path, times: list[float], total_dur: float,
               max_len: float, min_len: float) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for i, start in enumerate(times):
        nxt = times[i + 1] if i + 1 < len(times) else total_dur
        dur = min(nxt, start + max_len) - start
        if dur < min_len:
            continue
        n += 1
        out = out_dir / f"{src.stem}_{n:03d}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.4f}", "-i", str(src),
             "-t", f"{dur:.4f}", "-c", "copy", str(out)],
            capture_output=True,
        )
        print(f"  [{n:03d}] {start:.2f}s ({dur:.2f}s)  ->  {out.name}")
    return n


def main() -> None:
    p = argparse.ArgumentParser(description="Split a drum stem into one-shot hits")
    p.add_argument("input", help="drums.wav file, any stem .wav, or a Stems folder")
    p.add_argument("output_dir", help="Where one-shots are saved (per-source subfolder)")
    p.add_argument("--delta", type=float, default=0.06,
                   help="Onset sensitivity above local flux mean (lower = more hits)")
    p.add_argument("--wait", type=float, default=0.08,
                   help="Minimum seconds between hits")
    p.add_argument("--max-len", type=float, default=1.5,
                   help="Cap each one-shot at this length, seconds")
    p.add_argument("--min-len", type=float, default=0.05,
                   help="Drop hits shorter than this, seconds")
    args = p.parse_args()

    inp = Path(args.input)
    out_root = Path(args.output_dir)
    files = [inp] if inp.is_file() else sorted(inp.rglob("drums.wav"))
    if not files:
        print("No drums.wav found (pass a stem file directly to split something else).")
        sys.exit(1)

    total = 0
    for f in files:
        audio = decode_mono(f, DETECT_SR)
        times = onset_times(audio, DETECT_SR, args.delta, args.wait)
        out_dir = out_root / f.parent.name
        print(f"\n{f.parent.name}/{f.stem}: {len(times)} onsets")
        total += slice_hits(f, out_dir, times, get_duration(f), args.max_len, args.min_len)

    print(f"\n✓ {total} one-shots saved to {out_root}")


if __name__ == "__main__":
    main()
