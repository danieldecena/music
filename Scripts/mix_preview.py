#!/usr/bin/env python3
"""Render a mix pair as a tempo-matched crossfade and play it.

The report recommends pairs on estimated BPM and key, and key is the weak half.
A ten-second listen is the only oracle that does not share the estimator's blind
spots, so the preview exists to make the verdict checkable rather than something
taken on faith.

Everything except render() and play() is pure and unit-tested without ffmpeg.
"""

from __future__ import annotations

import math
import shutil
import subprocess

SECONDS = 20
FADE = 8


def atempo_ratio(a_bpm: float, b_bpm: float) -> float:
    """Rate to stretch B onto A's grid, folded to the octave nearest no stretch.

    Folding into [1/sqrt(2), sqrt(2)] rather than atempo's full [0.5, 2.0] picks
    the octave that moves the audio least: a 128 against a 64 needs no stretch at
    all, because the tracks already share a pulse and one just counts it twice.
    Doubling it instead would be an audible, pointless mangling of a pair that
    already locks. The result is always inside atempo's accepted range.
    """
    if not a_bpm or not b_bpm or a_bpm <= 0 or b_bpm <= 0:
        return 1.0
    r = a_bpm / b_bpm
    while r > math.sqrt(2):
        r /= 2.0
    while r < 1 / math.sqrt(2):
        r *= 2.0
    return r


def excerpt_start(transitions, duration: float) -> float:
    """Where to start the excerpt: the first section boundary with room to run.

    Starting at a musical boundary beats an arbitrary offset -- a preview that
    begins mid-phrase sounds broken whether or not the pair actually works.
    """
    for t in transitions or []:
        if 0 < t <= max(0.0, duration - SECONDS):
            return float(t)
    return duration * 0.25


def preview_args(
    a_path,
    b_path,
    ratio: float,
    out_path,
    a_start: float,
    b_start: float,
    seconds: int = SECONDS,
    fade: int = FADE,
) -> list[str]:
    """The ffmpeg command for a tempo-matched crossfade.

    -vn is mandatory: Apple Music .m4a files carry an embedded mjpeg cover art
    stream, and without it ffmpeg maps that into the output and the wav muxer
    fails with a message that never mentions cover art.
    """
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{a_start:g}",
        "-t",
        f"{seconds:g}",
        "-i",
        str(a_path),
        "-ss",
        f"{b_start:g}",
        "-t",
        f"{seconds:g}",
        "-i",
        str(b_path),
        "-filter_complex",
        "[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a];"
        f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,atempo={ratio:.6f}[b];"
        f"[a][b]acrossfade=d={fade:g}:c1=tri:c2=tri[out]",
        "-map",
        "[out]",
        "-vn",
        "-ac",
        "2",
        str(out_path),
    ]


def render(args: list[str]) -> bool:
    """Run the ffmpeg command. False if ffmpeg is missing or the render failed."""
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found on PATH -- install it with: brew install ffmpeg")
        return False
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"preview render failed: {proc.stderr.strip()}")
        return False
    return True


def play(path) -> None:
    if not shutil.which("afplay"):
        print(f"afplay not found; preview written to {path}")
        return
    subprocess.run(["afplay", str(path)])
