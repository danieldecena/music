#!/usr/bin/env python3
"""Line a song's chart up with its record, then lay Logic's chords on the lined-up grid.

The chord script and Logic both assume bar 1 starts at the top of the audio file, but records
start their first beat 0.1 to 0.7 s in, so every chord change and every strum in the phone's
play-along landed between beats (2026-11-15). This measures, from the record:

  - the tempo, within 2% of the chart's (a steady grid of onset energy, 0.05 BPM steps),
  - where the first beat falls,
  - which of the next four beats is the downbeat: the one most of Logic's chord changes fall on,

and rewrites "<name> chords.txt" with that tempo and `start <seconds> s` on its tempo line, the
chords laid again from "<name> logic.tsv" (written by logic_chords.py). Title and key are kept.

Usage: .venv/bin/python Scripts/align_chart.py "<song>.m4a"
Exit 1 when the chart or Logic's chord times are missing.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_track as at
import logic_chords as lc

SEARCH = 0.02  # how far from the chart's tempo to look
STEP = 0.05  # BPM
PHASES = 24  # positions tried within one beat
BEATS_PER_BAR = 4


def beat_grid(env: np.ndarray, fps: float, lo: float, hi: float) -> tuple[float, float]:
    """The tempo in lo..hi and the first beat (seconds) whose steady grid lands on the most onset
    energy. A grid a little off tempo walks off the beats over a whole song, so the true one wins."""
    best = (-1.0, lo, 0.0)
    for bpm in np.arange(lo, hi + 1e-9, STEP):
        lag = fps * 60 / bpm
        k = np.arange(int(len(env) / lag))
        if len(k) < 4:
            continue
        for phase in np.linspace(0, lag, PHASES, endpoint=False):
            on = env[np.rint(phase + k * lag).astype(int).clip(0, len(env) - 1)].mean()
            if on > best[0]:
                best = (on, bpm, phase / fps)
    return round(float(best[1]), 2), float(best[2])


def downbeat(changes: list[float], first_beat: float, bpm: float) -> float:
    """Where bar 1 starts: the first beat, or one of the three after it, whichever has the most
    chord changes on its bar lines (within a third of a beat). Ties keep the earlier beat."""
    beat = 60 / bpm
    bar = BEATS_PER_BAR * beat
    best_k, best = 0, -1
    for k in range(BEATS_PER_BAR):
        start = first_beat + k * beat
        hits = sum(
            1 for t in changes if abs((t - start + bar / 2) % bar - bar / 2) < beat / 3
        )
        if hits > best:
            best_k, best = k, hits
    return first_beat + best_k * beat


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 1
    audio = Path(argv[0]).expanduser().resolve()
    chart = audio.with_name(f"{audio.stem} chords.txt")
    raw = audio.with_name(f"{audio.stem} logic.tsv")
    for needed in (chart, raw):
        if not needed.is_file():
            print(
                f"No {needed.name} beside the song: run Logic chords (music.sh, T then K) first."
            )
            return 1
    title, key, old_bpm, _, _ = lc.read_grid(chart.read_text())
    changes = lc.load_changes(raw)
    samples = at.decode_mono(audio, at.SR)
    sp = at.spectra(samples)
    env = np.maximum(sp.flux - sp.flux.mean(), 0.0)
    bpm, first = beat_grid(env, sp.fps, old_bpm * (1 - SEARCH), old_bpm * (1 + SEARCH))
    moments = [t for t, c in changes[1:] if c != "-"]
    start = round(downbeat(moments, first, bpm), 3)
    bars = int((len(samples) / at.SR - start) // (BEATS_PER_BAR * 60 / bpm))
    labels = lc.bar_labels(changes, bpm, bars, start=start)
    chart.write_text(lc.chart_text((title, key, bpm, bars, start), labels))
    print(
        f"Lined up: {bpm} BPM (was {old_bpm}), first beat {first:.2f} s, bar 1 at {start:.2f} s, {bars} bars."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
