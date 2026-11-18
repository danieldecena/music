#!/opt/homebrew/bin/python3
"""Merge a guitar-only chart into a song's full-mix chart.

Logic's Chord ID on the guitar stem names what the guitar plays (WALKING AWAY: plain D#, F, A#)
where the full mix adds colour the guitar does not play (D#maj7). The guitar chart is used for
every bar the guitar plays; bars where it rests ("-") take the full-mix chord, spelled the way
the guitar spells that root elsewhere. The tempo line stays the full-mix chart's.

Usage: combine_charts.py "<name> guitar chords.txt" "<name> chords.txt"
"<name> chords (mix).txt" always holds the latest full-mix chart: a fresh full-mix song chart is
copied there before the song chart is rewritten, and a song chart that is already merged is
left alone as the input (the merge re-reads "(mix)" instead).
"""

import re
import sys
from collections import Counter
from pathlib import Path

GUITAR_NOTE = "# chords from Logic Pro Chord ID: the guitar part, the full mix where the guitar rests"
_BAR = re.compile(r"(\d+)\t(\S+)")
_MID = re.compile(r"(\d+)\.3\t(\S+)")
_TEMPO = re.compile(r"# key \S+\s+([\d.]+) BPM\s+\d+ bars(?:\s+start ([\d.]+) s)?")


def root(chord: str) -> str:
    m = re.match(r"[A-G]#?", chord)
    return m.group(0) if m else ""


def _parse(text: str) -> tuple[list[str], dict[int, str], dict[int, str]]:
    header, bars, mids = [], {}, {}
    for line in text.splitlines():
        if line.startswith("#"):
            header.append(line)
        elif m := _BAR.fullmatch(line):
            bars[int(m.group(1))] = m.group(2)
        elif m := _MID.fullmatch(line):
            mids[int(m.group(1))] = m.group(2)
    return header, bars, mids


def tempo(text: str) -> tuple[float, float]:
    """(bpm, start seconds) from the chart's tempo line; a missing start is 0.0."""
    for line in text.splitlines():
        if m := _TEMPO.match(line):
            return float(m.group(1)), float(m.group(2) or 0.0)
    raise ValueError("no tempo line")


def grid_mismatch(guitar: str, mix: str) -> str:
    """Why the two charts' bars would not line up, or "" when they do."""
    try:
        g_bpm, g_start = tempo(guitar)
        m_bpm, m_start = tempo(mix)
    except ValueError:
        return "A chart has no tempo line, so its bars cannot be lined up. Nothing written."
    if abs(g_start - m_start) > 0.5 * 60 / m_bpm:
        return (
            f"The guitar chart starts at {g_start:.3f} s and the mix chart at {m_start:.3f} s "
            "(more than half a beat apart); bars would not line up. Nothing written."
        )
    if abs(g_bpm - m_bpm) / m_bpm > 0.02:
        return (
            f"The guitar chart is {g_bpm:g} BPM and the mix chart {m_bpm:g} BPM "
            "(more than 2% apart); bars would not line up. Nothing written."
        )
    return ""


def combine(guitar: str, mix: str) -> str:
    _, g_bars, g_mids = _parse(guitar)
    header, m_bars, m_mids = _parse(mix)
    played = [c for c in list(g_bars.values()) + list(g_mids.values()) if c != "-"]
    by_root = {}
    for chord, _ in Counter(played).most_common():
        by_root.setdefault(root(chord), chord)

    def fallback(chord: str) -> str:
        return by_root.get(root(chord), chord) if chord != "-" else chord

    lines = [GUITAR_NOTE if h.startswith("# chords from") else h for h in header]
    for bar in sorted(m_bars):
        if g_bars.get(bar, "-") != "-":
            lines.append(f"{bar}\t{g_bars[bar]}")
            if g_mids.get(bar, "-") != "-":
                lines.append(f"{bar}.3\t{g_mids[bar]}")
        else:
            lines.append(f"{bar}\t{fallback(m_bars[bar])}")
            if bar in m_mids:
                lines.append(f"{bar}.3\t{fallback(m_mids[bar])}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 1
    guitar, song = (Path(a) for a in argv)
    for p in (guitar, song):
        if not p.is_file():
            print(f"No chart at {p}")
            return 1
    if not song.name.endswith(" chords.txt"):
        print(f"The song chart must be named '<name> chords.txt', not {song.name}; nothing written.")
        return 1
    backup = song.with_name(song.name[: -len(" chords.txt")] + " chords (mix).txt")
    g_text, s_text = guitar.read_text(), song.read_text()
    merged = GUITAR_NOTE in s_text.splitlines()
    if merged:
        if not backup.is_file():
            print(f"{song.name} is already merged but {backup.name} is missing; nothing written.")
            return 1
        mix_text = backup.read_text()
    else:
        mix_text = s_text
    g_n, m_n = len(_parse(g_text)[1]), len(_parse(mix_text)[1])
    if g_n != m_n:
        print(
            f"The guitar chart has {g_n} bars and the full-mix chart {m_n} bars; nothing written."
        )
        return 1
    if reason := grid_mismatch(g_text, mix_text):
        print(reason)
        return 1
    if not merged:
        backup.write_text(mix_text)
    song.write_text(combine(g_text, mix_text))
    print(f"Wrote {song.name} (guitar first); the full-mix chart is {backup.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
