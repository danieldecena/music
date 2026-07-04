#!/usr/bin/env python3
"""Re-voice a monophonic melodic stem as another instrument.

Transcribe a single-note melodic line to MIDI (reusing bass_to_midi's
autocorrelation transcriber, widened to a full melodic range), stamp it with a
General MIDI instrument program, then render it to audio with fluidsynth + a GM
soundfont. Best-effort: monophonic lines only (leads, basslines, vocal melodies,
single-note riffs). Chords/strumming will not transcribe well.

Usage:
    resynth.py <input.wav> <out_dir> --instrument guitar [--tempo BPM]

Setup: `brew install fluid-synth` and a GM soundfont in <repo>/soundfonts/ (or
point $MUSIC_SOUNDFONT at one). Without them, the .mid is still written.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from bass_to_midi import decode_mono, transcribe, write_midi

# Widened melodic range: C2 (~65 Hz) to B6 (~1976 Hz).
LO_HZ = 65.0
HI_HZ = 2000.0

# Friendly name -> General MIDI program number (0-indexed).
INSTRUMENTS = {
    # keys
    "piano": 0,
    "epiano": 4,
    "harpsichord": 6,
    "clav": 7,
    "music-box": 10,
    "vibraphone": 11,
    "marimba": 12,
    "bells": 14,
    "organ": 16,
    "accordion": 21,
    # guitars
    "guitar": 24,  # nylon
    "guitar-steel": 25,
    "guitar-jazz": 26,
    "guitar-clean": 27,
    "guitar-muted": 28,
    # bass
    "bass-finger": 33,
    "bass-pick": 34,
    "bass-synth": 38,
    # strings
    "violin": 40,
    "cello": 42,
    "harp": 46,
    "strings": 48,
    "choir": 52,
    # brass / wind
    "trumpet": 56,
    "brass": 61,
    "sax": 65,
    "clarinet": 71,
    "flute": 73,
    # synth
    "synth": 81,  # sawtooth lead
    "synth-square": 80,
    "synth-pad": 89,
    # world / misc
    "sitar": 104,
    "banjo": 105,
    "kalimba": 108,
    "steel-drum": 114,
}

REPO_ROOT = Path(__file__).resolve().parent.parent
SF_DIR = REPO_ROOT / "soundfonts"


def list_soundfonts() -> list[Path]:
    """All .sf2/.sf3 soundfonts in the soundfonts/ folder, sorted by name."""
    if not SF_DIR.is_dir():
        return []
    return sorted(p for p in SF_DIR.iterdir() if p.suffix.lower() in (".sf2", ".sf3"))


def resolve_soundfont(pref: str | None = None) -> Path | None:
    """Pick a soundfont. `pref` may be a path or a name substring of a file in
    soundfonts/. Falls back to $MUSIC_SOUNDFONT, then the first soundfont found.
    """
    if pref:
        p = Path(pref).expanduser()
        if p.is_file():
            return p
        matches = [f for f in list_soundfonts() if pref.lower() in f.stem.lower()]
        if matches:
            return matches[0]
    env = os.environ.get("MUSIC_SOUNDFONT")
    if env and Path(env).is_file():
        return Path(env)
    fonts = list_soundfonts()
    return fonts[0] if fonts else None


def build_fluidsynth_cmd(soundfont: Path, midi: Path, wav: Path) -> list[str]:
    """argv to render `midi` to `wav` with `soundfont` (pure, for testing).

    `-F <wav>` MUST precede the positional soundfont/midi args — fluidsynth
    rejects it after them (and misleadingly still exits 0).
    """
    return [
        "fluidsynth",
        "-ni",
        "-q",
        "-r",
        "44100",
        "-F",
        str(wav),
        str(soundfont),
        str(midi),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Re-voice a monophonic stem as another instrument"
    )
    ap.add_argument("input")
    ap.add_argument("out_dir")
    ap.add_argument("--instrument", default="guitar")
    ap.add_argument("--tempo", type=float, default=120.0)
    ap.add_argument(
        "--soundfont", default=None, help="path or name substring of a .sf2/.sf3"
    )
    args = ap.parse_args()

    if args.instrument not in INSTRUMENTS:
        print(
            f"Unknown instrument '{args.instrument}'. Choose from: "
            f"{', '.join(INSTRUMENTS)}",
            file=sys.stderr,
        )
        return 2
    program = INSTRUMENTS[args.instrument]

    events = transcribe(decode_mono(Path(args.input)), LO_HZ, HI_HZ)
    if not events:
        print(
            "No pitched notes detected (is this a clean monophonic line?).",
            file=sys.stderr,
        )
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.input).stem
    midi_path = out_dir / f"{stem}_{args.instrument}.mid"
    wav_path = out_dir / f"{stem}_{args.instrument}.wav"
    write_midi(events, midi_path, args.tempo, program)
    print(f"[ok] {len(events)} notes -> {midi_path}")

    soundfont = resolve_soundfont(args.soundfont)
    if not soundfont:
        print(
            "No soundfont found — wrote MIDI only. Install a GM soundfont in "
            f"{REPO_ROOT / 'soundfonts'}/ or set $MUSIC_SOUNDFONT to render audio.",
            file=sys.stderr,
        )
        return 0

    try:
        subprocess.run(
            build_fluidsynth_cmd(soundfont, midi_path, wav_path),
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print(
            "fluidsynth not on PATH — wrote MIDI only. Run: brew install fluid-synth",
            file=sys.stderr,
        )
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"fluidsynth render failed: {exc.stderr or exc}", file=sys.stderr)
        return 1
    if not wav_path.exists():  # fluidsynth can exit 0 without writing the file
        print(
            f"fluidsynth exited cleanly but produced no audio at {wav_path}.",
            file=sys.stderr,
        )
        return 1
    print(f"[ok] rendered {args.instrument} ({soundfont.name}) -> {wav_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
