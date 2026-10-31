#!/usr/bin/env python3
"""Turn a track's bar-by-bar chords into lyric-style lines: '0:12  Em  G  D  A'.

One line per four bars, prefixed with the time that line starts. Estimates only
(chords.py is chroma template matching). Prints to stdout.

Run with the venv python (numpy required):
    .venv/bin/python Scripts/chords_to_lyrics.py <audio file | Stems folder>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chords  # noqa: E402


def format_lyrics(bpm: float, labels: list[str]) -> str:
    bar_s = chords.BEATS_PER_BAR * 60.0 / bpm
    lines = []
    for i in range(0, len(labels), chords.BEATS_PER_BAR):
        t = int(i * bar_s)
        body = "  ".join(labels[i : i + chords.BEATS_PER_BAR])
        lines.append(f"{t // 60}:{t % 60:02d}  {body}")
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: chords_to_lyrics.py <audio file | Stems folder>")
        sys.exit(1)
    try:
        bpm, _, labels = chords.analyze_chords(Path(sys.argv[1]))
    except Exception as exc:  # noqa: BLE001
        print(f"chord analysis failed -- {exc}")
        sys.exit(1)
    print(format_lyrics(bpm, labels))


if __name__ == "__main__":
    main()
