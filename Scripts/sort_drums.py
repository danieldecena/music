#!/usr/bin/env python3
"""
Sort a folder of drum one-shots into kick / snare / hat subfolders by timbre.
Pure numpy — decodes each hit via ffmpeg and classifies on spectral centroid
plus low/high band energy. Heuristic, but turns a flat pile of hits into a
usable kit.

Rules (on the hit's early transient):
    - lots of sub-200 Hz energy, low centroid           -> kick
    - high centroid (bright, > ~4 kHz)                   -> hat
    - otherwise (mid-band, noisy body)                   -> snare

Files are COPIED (originals left in place). Usage:
    sort_drums.py <one-shots folder> [--move]
"""

import argparse
import shutil
import subprocess
from pathlib import Path

import numpy as np

SR = 22050


def decode_mono(path: Path) -> np.ndarray:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return np.empty(0, dtype=np.float32)
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def classify(audio: np.ndarray) -> str:
    if audio.size < 256:
        return "snare"
    seg = audio[: int(SR * 0.12)] if audio.size > int(SR * 0.12) else audio
    win = seg * np.hanning(len(seg)).astype(np.float32)
    mag = np.abs(np.fft.rfft(win))
    freqs = np.fft.rfftfreq(len(win), 1.0 / SR)
    total = mag.sum() + 1e-9
    centroid = float((freqs * mag).sum() / total)
    low = mag[freqs < 200].sum() / total       # kick body
    high = mag[freqs > 6000].sum() / total      # hat sizzle
    if low > 0.30 and centroid < 1500:
        return "kick"
    if high > 0.25 or centroid > 4500:
        return "hat"
    return "snare"


def main() -> None:
    ap = argparse.ArgumentParser(description="Sort drum one-shots into kick/snare/hat")
    ap.add_argument("folder", help="Folder of one-shot .wav files")
    ap.add_argument("--move", action="store_true", help="Move instead of copy")
    args = ap.parse_args()

    src = Path(args.folder)
    hits = sorted(src.glob("*.wav"))
    if not hits:
        print(f"No .wav one-shots in {src}")
        return

    counts = {"kick": 0, "snare": 0, "hat": 0}
    for h in hits:
        label = classify(decode_mono(h))
        dest_dir = src / label
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / h.name
        (shutil.move if args.move else shutil.copy2)(str(h), str(dest))
        counts[label] += 1

    print(f"Sorted {len(hits)} hits -> "
          f"kick {counts['kick']}, snare {counts['snare']}, hat {counts['hat']}")
    print(f"  {src}/kick  {src}/snare  {src}/hat")


if __name__ == "__main__":
    main()
