#!/usr/bin/env python3
"""
Sort a folder of drum one-shots into kick / snare / hat subfolders.

ADAPTIVE: instead of fixed frequency thresholds (which don't generalize across
tracks), this clusters *this folder's* hits into three brightness groups by
spectral centroid (1-D k-means, pure numpy) and labels them low->kick,
mid->snare, high->hat. A sub-heavy override catches 808/kick hits that happen to
be bright. Self-calibrating, so a track with dark hats still gets a hat group.

Files are COPIED (originals stay put). Usage:
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


def features(audio: np.ndarray) -> tuple[float, float]:
    """Return (spectral_centroid_hz, low_band_ratio) over the hit's transient."""
    if audio.size < 256:
        return 0.0, 0.0
    seg = audio[: int(SR * 0.12)] if audio.size > int(SR * 0.12) else audio
    win = seg * np.hanning(len(seg)).astype(np.float32)
    mag = np.abs(np.fft.rfft(win))
    freqs = np.fft.rfftfreq(len(win), 1.0 / SR)
    total = mag.sum() + 1e-9
    centroid = float((freqs * mag).sum() / total)
    low = float(mag[freqs < 150].sum() / total)
    return centroid, low


def kmeans_1d(x: np.ndarray, k: int = 3, iters: int = 40) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic 1-D k-means. Centers initialised at evenly spaced percentiles."""
    x = np.asarray(x, dtype=float)
    centers = np.percentile(x, np.linspace(15, 85, k))
    labels = np.zeros(len(x), dtype=int)
    for _ in range(iters):
        labels = np.abs(x[:, None] - centers[None, :]).argmin(1)
        new = np.array([x[labels == j].mean() if np.any(labels == j) else centers[j]
                        for j in range(k)])
        if np.allclose(new, centers):
            break
        centers = new
    return labels, centers


def classify_folder(hits: list[Path]) -> dict[Path, str]:
    """Adaptively label each hit kick/snare/hat by clustering brightness."""
    feats = [features(decode_mono(h)) for h in hits]
    centroids = np.array([f[0] for f in feats])
    lows = np.array([f[1] for f in feats])
    valid = centroids > 0
    result: dict[Path, str] = {}

    # Degenerate cases: too few hits or no spread -> simple absolute fallback.
    if valid.sum() < 3 or np.unique(np.round(centroids[valid], -1)).size < 3:
        for h, (c, lo) in zip(hits, feats):
            result[h] = "kick" if (lo > 0.33 or c < 1200) else ("hat" if c > 5000 else "snare")
        return result

    # Cluster on brightness. Kicks fall out naturally as the lowest-centroid
    # group, so we rely on the clustering rather than an absolute sub-bass rule
    # (which over-grabs on muddy source-separated stems). Only a very extreme
    # sub-heavy hit is force-labelled kick.
    logc = np.log(np.clip(centroids, 1.0, None))
    labels, centers = kmeans_1d(logc[valid], k=3)
    order = np.argsort(centers)  # ascending centroid
    cluster_name = {order[0]: "kick", order[1]: "snare", order[2]: "hat"}

    vi = 0
    for h, c, lo in zip(hits, centroids, lows):
        if c <= 0:
            result[h] = "snare"
            continue
        name = cluster_name[labels[vi]]
        vi += 1
        if lo > 0.65 and name == "hat":   # only rescue an obvious sub-heavy false "hat"
            name = "kick"
        result[h] = name
    return result


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

    labels = classify_folder(hits)
    counts = {"kick": 0, "snare": 0, "hat": 0}
    for h in hits:
        label = labels[h]
        dest_dir = src / label
        dest_dir.mkdir(exist_ok=True)
        (shutil.move if args.move else shutil.copy2)(str(h), str(dest_dir / h.name))
        counts[label] += 1

    print(f"Sorted {len(hits)} hits -> "
          f"kick {counts['kick']}, snare {counts['snare']}, hat {counts['hat']}")
    print(f"  {src}/kick  {src}/snare  {src}/hat")


if __name__ == "__main__":
    main()
