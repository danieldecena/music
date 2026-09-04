#!/usr/bin/env python3
"""Cut two tracks on their own bar grids and combine them.

`mix_preview.py` crossfades at whatever offset a section boundary happens to
fall on, with one atempo ratio derived from the two BPM estimates. That is
enough to audition a pair and no use for making something: the cut does not
land on a downbeat, and the two sides are never heard at the same time.

This module cuts on the persisted bar grid instead, and adds the operation the
repo has never had -- playing two sources simultaneously, so A's drums can sit
under B's vocal.

The alignment is measured, not derived. `stretch_for` reads how long n bars
actually take in each track and stretches by that ratio, so a grid that drifts
(Ivy runs 2.08s per bar early and 2.95s by the outro) still lines up. A BPM
ratio would only be right if both tempos were constant, and neither is.

Everything except render() and play() is pure and unit-tested without ffmpeg.
"""

from __future__ import annotations

import argparse
import math
import pathlib
import shutil
import sqlite3
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "catalog.sqlite"
STEM_MODELS = ("htdemucs", "htdemucs_6s")
STEMS = ("drums", "bass", "other", "vocals")


def bar_times(con: sqlite3.Connection, track: str) -> list[float]:
    """Bar start times in seconds, index-ordered."""
    return [r[0] for r in con.execute(
        "SELECT t FROM bars WHERE track=? ORDER BY idx", (track,))]


def bar_time(bars: list[float], idx: float) -> float:
    """Seconds at (possibly fractional) bar `idx`, extrapolating past the end.

    Extrapolation matters because the last scored window can reach one bar past
    the final downbeat; clamping there would silently shorten the cut instead.
    """
    if not bars:
        raise ValueError("no bar grid for this track")
    if len(bars) == 1:
        return bars[0]
    if idx <= 0:
        return bars[0] + idx * (bars[1] - bars[0])
    if idx >= len(bars) - 1:
        tail = bars[-1] - bars[-2]
        return bars[-1] + (idx - (len(bars) - 1)) * tail
    lo = int(idx)
    return bars[lo] + (idx - lo) * (bars[lo + 1] - bars[lo])


def stretch_for(a_bars, a_bar, b_bars, b_bar, n_bars):
    """(b_bar_count, ratio, a_dur, b_dur) to fit B's bars over A's n_bars.

    Returns how many of B's bars to take and the atempo rate that makes them
    last exactly as long as A's. B's count is folded by octaves so the rate
    stays inside [1/sqrt(2), sqrt(2)]: against a track at half the tempo you
    want twice the bars at no stretch, not the same bars slowed to a crawl.
    """
    a0, a1 = bar_time(a_bars, a_bar), bar_time(a_bars, a_bar + n_bars)
    a_dur = a1 - a0
    if a_dur <= 0:
        raise ValueError("A's window has no duration")

    best = None
    for k in (-2, -1, 0, 1, 2):
        count = n_bars * (2.0 ** k)
        if count < 1:
            continue
        b_dur = bar_time(b_bars, b_bar + count) - bar_time(b_bars, b_bar)
        if b_dur <= 0:
            continue
        ratio = b_dur / a_dur
        if not 0.5 <= ratio <= 2.0:
            continue
        score = abs(math.log2(ratio))
        if best is None or score < best[0]:
            best = (score, count, ratio, b_dur)
    if best is None:
        raise ValueError("no octave of B's bars stretches into A's window")
    _, count, ratio, b_dur = best
    return count, ratio, a_dur, b_dur


def stem_dir(track: str) -> pathlib.Path | None:
    for model in STEM_MODELS:
        d = ROOT / "Stems" / model / track
        if d.is_dir():
            return d
    return None


def sources(track: str, source_path: str, want: list[str]) -> list[pathlib.Path]:
    """Files to read for one side. `["mix"]` is the original; else named stems."""
    if want == ["mix"]:
        return [ROOT / source_path]
    d = stem_dir(track)
    if d is None:
        raise ValueError(f"no separated stems for {track!r} -- run Separate stems first")
    out = []
    for s in want:
        p = d / f"{s}.wav"
        if not p.exists():
            raise ValueError(f"{track!r} has no {s}.wav (have: "
                             + ", ".join(sorted(f.stem for f in d.glob('*.wav'))) + ")")
        out.append(p)
    return out


def layer_args(a_srcs, b_srcs, a_start, a_dur, b_start, b_dur, ratio, out_path):
    """ffmpeg command playing both sides at once, B stretched onto A's grid.

    -vn because Apple Music .m4a carries embedded cover art as a video stream,
    and the wav muxer fails on it with a message that never says so.
    normalize=0 keeps each side at its own level rather than halving both;
    alimiter catches the clipping that summing two masters otherwise causes.
    """
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for p in a_srcs:
        cmd += ["-ss", f"{a_start:g}", "-t", f"{a_dur:g}", "-i", str(p)]
    for p in b_srcs:
        cmd += ["-ss", f"{b_start:g}", "-t", f"{b_dur:g}", "-i", str(p)]

    fmt = "aformat=sample_rates=44100:channel_layouts=stereo"
    chains, labels = [], []
    for i in range(len(a_srcs)):
        chains.append(f"[{i}:a]{fmt}[a{i}]")
        labels.append(f"[a{i}]")
    for j in range(len(b_srcs)):
        i = len(a_srcs) + j
        chains.append(f"[{i}:a]{fmt},atempo={ratio:.6f}[b{j}]")
        labels.append(f"[b{j}]")
    chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:"
                  f"duration=shortest:normalize=0,alimiter=limit=0.95[out]")

    cmd += ["-filter_complex", ";".join(chains), "-map", "[out]", "-vn",
            "-ac", "2", str(out_path)]
    return cmd


def transition_args(a_src, b_src, a_start, a_dur, b_start, b_dur, ratio,
                    fade, out_path):
    """ffmpeg command running A into B, crossfading over `fade` seconds.

    Both cuts start on a downbeat, so the fade happens between two aligned
    grids rather than at an arbitrary offset the way a section-boundary cut does.
    """
    fmt = "aformat=sample_rates=44100:channel_layouts=stereo"
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{a_start:g}", "-t", f"{a_dur:g}", "-i", str(a_src),
        "-ss", f"{b_start:g}", "-t", f"{b_dur:g}", "-i", str(b_src),
        "-filter_complex",
        f"[0:a]{fmt}[a];[1:a]{fmt},atempo={ratio:.6f}[b];"
        f"[a][b]acrossfade=d={fade:g}:c1=tri:c2=tri[out]",
        "-map", "[out]", "-vn", "-ac", "2", str(out_path),
    ]


def render(args: list[str]) -> bool:
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found on PATH -- install it with: brew install ffmpeg")
        return False
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"render failed: {proc.stderr.strip()}")
        return False
    return True


def play(path) -> None:
    if not shutil.which("afplay"):
        print(f"afplay not found; written to {path}")
        return
    subprocess.run(["afplay", str(path)])


def _track_row(con, name):
    row = con.execute(
        "SELECT source_path, apple_bpm, bpm FROM tracks WHERE name=?", (name,)).fetchone()
    if row is None:
        raise SystemExit(f"no track named {name!r} in the catalog")
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=("layer", "transition"))
    ap.add_argument("--a", required=True, help="track name, as catalog.py lists it")
    ap.add_argument("--b", required=True)
    ap.add_argument("--a-bar", type=int, required=True)
    ap.add_argument("--b-bar", type=int, required=True)
    ap.add_argument("--bars", type=int, default=8, help="bars of A to cover")
    ap.add_argument("--a-stems", default="mix",
                    help="comma-separated: mix, or any of " + ",".join(STEMS))
    ap.add_argument("--b-stems", default="mix")
    ap.add_argument("--fade", type=float, default=4.0, help="transition only")
    ap.add_argument("--out", default="Exports/mix.wav")
    ap.add_argument("--play", action="store_true")
    a = ap.parse_args(argv)

    if not DB.exists():
        raise SystemExit(f"no catalog at {DB} -- run: catalog.py scan")
    con = sqlite3.connect(DB)
    a_src_path, a_bpm, a_fallback = _track_row(con, a.a)
    b_src_path, b_bpm, b_fallback = _track_row(con, a.b)
    a_bars, b_bars = bar_times(con, a.a), bar_times(con, a.b)
    for name, bars in ((a.a, a_bars), (a.b, b_bars)):
        if not bars:
            raise SystemExit(
                f"{name!r} has no bar grid -- run: catalog.py ingest on its analysis JSON")

    b_count, ratio, a_dur, b_dur = stretch_for(a_bars, a.a_bar, b_bars, a.b_bar, a.bars)
    a_start, b_start = bar_time(a_bars, a.a_bar), bar_time(b_bars, a.b_bar)

    a_srcs = sources(a.a, a_src_path, a.a_stems.split(","))
    b_srcs = sources(a.b, b_src_path, a.b_stems.split(","))

    out = pathlib.Path(a.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"A  {a.a}  bars {a.a_bar}-{a.a_bar + a.bars}  "
          f"{a_start:.2f}s +{a_dur:.2f}s  [{a.a_stems}]")
    print(f"B  {a.b}  bars {a.b_bar}-{a.b_bar + b_count:g}  "
          f"{b_start:.2f}s +{b_dur:.2f}s  [{a.b_stems}]  atempo {ratio:.4f}")

    if a.mode == "layer":
        args = layer_args(a_srcs, b_srcs, a_start, a_dur, b_start, b_dur, ratio, out)
    else:
        if len(a_srcs) != 1 or len(b_srcs) != 1:
            raise SystemExit("transition takes one source per side; use --a-stems mix")
        args = transition_args(a_srcs[0], b_srcs[0], a_start, a_dur, b_start, b_dur,
                               ratio, a.fade, out)

    if not render(args):
        return 1
    print(f"wrote {out}")
    if a.play:
        play(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
