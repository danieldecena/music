#!/usr/bin/env python3
"""
Click-comparator — settle a track's tempo by ear.

The analyzer estimates BPM but can land an octave (or 3:2) off, and the only
honest tie-break is the ear. This plays a short excerpt of a track with a
metronome click laid over it at each candidate BPM (the estimate plus its
half/double/1.5x/0.667x octaves, and any known label). Whichever click locks
to the groove is the real tempo.

Decode/tempo machinery is reused from analyze_track (no DSP duplicated); the
click synthesis and candidate logic are the only new pieces here.

    .venv/bin/python Scripts/click_compare.py <file|StemsFolder> [--bpm B] \
        [--label L ...] [--dur S] [--start S] [--render-only DIR]

Without --render-only it is interactive: each candidate plays, then you press
Enter (next), r (replay), y (lock this one), or q (quit). It prints the locked
BPM and the fixtures-analysis.tsv line to paste.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze_track as at  # noqa: E402

BPM_MIN = 40.0
BPM_MAX = 220.0
CLICK_HZ = 1500.0
CLICK_MS = 45.0
CLICK_GAIN = 0.4


def candidate_bpms(base: float, extra: list[float] | None = None) -> list[float]:
    """Candidate tempos to audition: the estimate, its octaves, and any labels.

    Covers the two error shapes the analyzer actually makes — octave (half /
    double) and 3:2 metrical (1.5x / 0.667x) — plus any externally-known BPMs
    passed as `extra`. Rounded to 0.1, clamped to a musical range, deduped, and
    sorted so the audition walks slow-to-fast.
    """
    cands = {
        round(base, 1),
        round(base * 2.0, 1),
        round(base / 2.0, 1),
        round(base * 1.5, 1),
        round(base * 2.0 / 3.0, 1),
    }
    for e in extra or []:
        cands.add(round(e, 1))
    return sorted(c for c in cands if BPM_MIN <= c <= BPM_MAX)


def beat_times(bpm: float, duration: float, offset: float = 0.0) -> list[float]:
    """Beat timestamps (seconds) at `bpm` across `duration`, starting at `offset`."""
    if bpm <= 0.0:
        return []
    step = 60.0 / bpm
    out = []
    t = offset
    while t < duration:
        out.append(round(t, 6))
        t += step
    return out


def render_click(bpm: float, duration: float, sr: int) -> np.ndarray:
    """A mono click track: a short decaying tone at every beat, silence between."""
    n = int(duration * sr)
    track = np.zeros(n, dtype=np.float32)
    burst_n = int(CLICK_MS / 1000.0 * sr)
    t = np.arange(burst_n) / sr
    burst = (np.sin(2.0 * np.pi * CLICK_HZ * t) * np.exp(-t * 40.0)).astype(np.float32)
    for bt in beat_times(bpm, duration):
        i = int(bt * sr)
        end = min(i + burst_n, n)
        track[i:end] += burst[: end - i]
    return track


def _peak_norm(audio: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = float(np.max(np.abs(audio))) if audio.size else 0.0
    return audio * (peak / m) if m > 0.0 else audio


def mix_click(excerpt: np.ndarray, bpm: float, sr: int) -> np.ndarray:
    """Lay a click at `bpm` over a peak-normalized excerpt, guarding clipping."""
    music = _peak_norm(excerpt, 0.9)
    click = render_click(bpm, len(music) / sr, sr)[: len(music)]
    if click.size < music.size:
        click = np.pad(click, (0, music.size - click.size))
    mixed = music + click * CLICK_GAIN
    return _peak_norm(mixed, 0.97)


def _write_wav(path: Path, audio: np.ndarray, sr: int) -> None:
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def resolve_audio(target: Path) -> Path:
    """The file to click against: a Stems folder's drums stem, else the file itself.

    Drums give the least ambiguous beat to lock to. A non-stem directory (e.g.
    an acapella split) has no drums and is refused with a clean message.
    """
    if target.is_dir():
        stems = at.stem_track_dir(target)
        if stems and "drums" in stems:
            return stems["drums"]
        raise ValueError(f"{target} is not a Stems track folder (no drums stem)")
    if not target.is_file():
        raise ValueError(f"no such file or folder: {target}")
    return target


def excerpt_of(audio: np.ndarray, sr: int, start: float, dur: float) -> np.ndarray:
    """A `dur`-second slice starting `start` seconds in, clamped to the audio."""
    if audio.size == 0:
        return audio
    s = min(int(start * sr), max(audio.size - 1, 0))
    e = min(s + int(dur * sr), audio.size)
    return audio[s:e]


def _tsv_line(name: str, bpm: float) -> str:
    return f"{name}\t{bpm:g}\t<key>\t<source>"


def _audition(mixes: list[tuple[float, Path]], name: str) -> float | None:
    print(f"\nAuditioning {len(mixes)} candidates for {name!r}.")
    print("Each plays once; then: [Enter] next  r replay  y lock  q quit\n")
    i = 0
    while i < len(mixes):
        bpm, path = mixes[i]
        print(f"  [{i + 1}/{len(mixes)}] {bpm:g} BPM ...", flush=True)
        subprocess.run(["afplay", str(path)])
        ans = input(f"    {bpm:g} BPM — [Enter]/r/y/q: ").strip().lower()
        if ans == "y":
            return bpm
        if ans == "q":
            return None
        if ans == "r":
            continue
        i += 1
    print("\n(reached the end without locking one)")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Settle a track's tempo by ear.")
    ap.add_argument("target", type=Path, help="audio file or Stems track folder")
    ap.add_argument("--bpm", type=float, default=None, help="base estimate (else auto)")
    ap.add_argument("--label", type=float, action="append", help="known BPM to include")
    ap.add_argument("--dur", type=float, default=18.0, help="excerpt seconds")
    ap.add_argument("--start", type=float, default=None, help="excerpt start seconds")
    ap.add_argument(
        "--render-only",
        type=Path,
        default=None,
        metavar="DIR",
        help="write candidate mixes to DIR and exit (no playback)",
    )
    args = ap.parse_args()

    try:
        src = resolve_audio(args.target)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    audio = at.decode_mono(src, at.SR)
    if audio.size == 0:
        print("error: decoded empty audio", file=sys.stderr)
        return 1
    total = audio.size / at.SR

    base = args.bpm
    if base is None:
        print("estimating base tempo ...", flush=True)
        base = at.detect_tempo(at.spectra(audio))
    print(f"base estimate: {base:g} BPM  (track {total:.0f}s)")

    cands = candidate_bpms(base, args.label)
    start = args.start if args.start is not None else min(30.0, total * 0.25)
    exc = excerpt_of(audio, at.SR, start, args.dur)
    print(f"candidates: {', '.join(f'{c:g}' for c in cands)}")

    name = args.target.stem if args.target.is_file() else args.target.name

    if args.render_only is not None:
        out = args.render_only
        out.mkdir(parents=True, exist_ok=True)
        for c in cands:
            p = out / f"{name}_{c:g}bpm.wav"
            _write_wav(p, mix_click(exc, c, at.SR), at.SR)
            print(f"wrote {p}")
        return 0

    with tempfile.TemporaryDirectory() as td:
        mixes = []
        for c in cands:
            p = Path(td) / f"{c:g}.wav"
            _write_wav(p, mix_click(exc, c, at.SR), at.SR)
            mixes.append((c, p))
        locked = _audition(mixes, name)

    if locked is None:
        print("\nnothing locked.")
        return 0
    print(f"\nlocked: {locked:g} BPM")
    print("fixtures-analysis.tsv line (fill key/source):")
    print(f"  {_tsv_line(name, locked)}")
    print("then: .venv/bin/python tests/test-analysis.py score")
    return 0


if __name__ == "__main__":
    sys.exit(main())
