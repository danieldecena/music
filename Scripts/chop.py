#!/usr/bin/env python3
"""
Slice a vocals.wav into individual phrase clips using ffmpeg silence detection.
Output goes to Samples/Vocals/<source-stem>/clip_001.wav etc.
"""

import subprocess
import re
import sys
from pathlib import Path


def get_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def detect_segments(
    path: Path, noise_db: int, min_silence: float, min_clip: float
) -> list[tuple[float, float]]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )

    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", result.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", result.stderr)]
    duration = get_duration(path)

    # Pair up silence regions; leading silence gets end-only handling
    silence_regions = []
    if len(ends) > len(starts):
        starts = [0.0] + starts
    for s, e in zip(starts, ends):
        silence_regions.append((s, e))

    segments = []
    cursor = 0.0

    for s_start, s_end in silence_regions:
        if s_start - cursor >= min_clip:
            segments.append((cursor, s_start))
        cursor = s_end

    if duration - cursor >= min_clip:
        segments.append((cursor, duration))

    return segments


def slice_file(
    input_path: Path,
    output_dir: Path,
    noise_db: int,
    min_silence: float,
    min_clip: float,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    segments = detect_segments(input_path, noise_db, min_silence, min_clip)

    if not segments:
        print(f"  No clips found — try adjusting silence threshold")
        return 0

    for i, (start, end) in enumerate(segments, 1):
        dur = end - start
        out = output_dir / f"{input_path.stem}_{i:03d}.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-ss",
                str(start),
                "-t",
                str(dur),
                "-c",
                "copy",
                str(out),
            ],
            capture_output=True,
        )
        print(f"  [{i:03d}] {start:.1f}s–{end:.1f}s ({dur:.1f}s)  →  {out.name}")

    return len(segments)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Chop vocals into phrase clips")
    parser.add_argument("input", help="vocals.wav file or directory of .wav files")
    parser.add_argument("output_dir", help="Where to save clips")
    parser.add_argument(
        "--noise-db",
        type=int,
        default=-35,
        help="Silence threshold in dB (default: -35)",
    )
    parser.add_argument(
        "--min-silence",
        type=float,
        default=0.25,
        help="Min silence duration to split on, seconds (default: 0.25)",
    )
    parser.add_argument(
        "--min-clip",
        type=float,
        default=0.5,
        help="Min clip length to keep, seconds (default: 0.5)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_root = Path(args.output_dir)
    total = 0

    if input_path.is_file():
        files = [input_path]
    else:
        files = sorted(input_path.rglob("vocals.wav"))

    if not files:
        print("No vocals.wav files found.")
        sys.exit(1)

    for f in files:
        out_dir = output_root / f.parent.name
        print(f"\n{f.parent.name}")
        count = slice_file(f, out_dir, args.noise_db, args.min_silence, args.min_clip)
        total += count

    print(f"\n✓ {total} clips saved to {output_root}")


if __name__ == "__main__":
    main()
