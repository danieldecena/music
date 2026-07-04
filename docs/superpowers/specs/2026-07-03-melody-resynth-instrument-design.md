# Melody -> Instrument Re-synth — Design

Date: 2026-07-03
Status: Approved, pending implementation plan

## Context

The toolkit can transcribe a monophonic bass stem to MIDI
(`Scripts/bass_to_midi.py`), but there is no way to hear a melodic part played
back as a *different* instrument. This feature adds "transcribe -> re-synth":
take a single-note melodic stem (lead, bassline, vocal melody, riff), transcribe
it to MIDI, and render it as audio played by a chosen instrument (e.g. a banjo
line heard as a guitar). The payoff is an instantly listenable WAV.

Scope decisions (from brainstorming):
- Monophonic, single-note melodies only. Full-range, no polyphony. Strummed
  chords are out of scope (would need a polyphonic model like basic-pitch).
- Output is a rendered audio preview (plus the intermediate MIDI), using
  `fluidsynth` + a General MIDI soundfont.

## Architecture

Reuse `bass_to_midi.py`'s transcription pipeline by parameterizing it, rather
than duplicating or rewriting. A new orchestrator script adds the wide pitch
range, instrument program, and audio render. Three pieces:

1. `Scripts/bass_to_midi.py` — generalized (backward-compatible).
2. `Scripts/resynth.py` — the transcribe -> render orchestrator.
3. `lib/music-core.sh` + `music` — a core function and menu option.

### 1. Generalize `Scripts/bass_to_midi.py` (backward-compatible)

- `pitch_hz(seg, lo_hz=40, hi_hz=400)` and `transcribe(audio, lo_hz=40, hi_hz=400)`
  gain range parameters; the defaults preserve the current bass behavior so the
  existing `M)` bass->MIDI menu option and `bass_to_midi` core fn are unchanged.
- `write_midi(events, path, tempo, program=None)` — when `program` is not None,
  emit a GM Program Change event (0xC0, program) at the start of the track;
  `None` preserves current output.

### 2. New `Scripts/resynth.py`

- Imports `decode_mono`, `transcribe`, `write_midi` from `bass_to_midi`.
- Transcribes with a widened melodic range (C2-B6, ~65-2000 Hz).
- `INSTRUMENTS`: a small friendly-name -> GM program dict, e.g.
  `piano=0, epiano=4, guitar=24 (nylon), guitar-steel=25, bells=14,
  strings=48, synth=81`. Writes the MIDI with the chosen program.
- Renders WAV: `fluidsynth -ni <soundfont> <out.mid> -F <out.wav> -r 44100`.
- Soundfont resolution: `$MUSIC_SOUNDFONT` if set, else the first `*.sf2` in
  `<music_root>/soundfonts/`.
- CLI: `resynth.py <input.wav> <out_dir> --instrument guitar [--tempo BPM]`.
  Outputs `<stem>_<instrument>.wav` and `<stem>_<instrument>.mid` in `out_dir`.
- Uses the venv python (numpy) — invoked like the other numpy scripts.

### 3. Toolkit wiring

`lib/music-core.sh`:
- New `resynth_instrument(input, out_dir, instrument, tempo)` calling
  `"$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/resynth.py" ...`, matching
  how `bass_to_midi` / `chop_drums` are invoked.

`music` menu:
- New option `R) Convert a melody to another instrument`: drag a stem/wav, pick
  a target instrument from a numbered list (the `INSTRUMENTS` keys), output to
  `Samples/Resynth/<track>/`.

## Setup Dependency

- `brew install fluid-synth`.
- A free GM soundfont (e.g. FluidR3_GM) placed in `<music_root>/soundfonts/` or
  pointed to by `$MUSIC_SOUNDFONT`.
- `.gitignore`: ignore `soundfonts/` (the `.sf2` is large) and
  `Samples/Resynth/`.

## Error Handling / Degradation

- No pitched notes detected -> print a message and skip the render (matches
  `bass_to_midi`), exit non-zero.
- `fluidsynth` not on PATH, or no soundfont found -> still write the `.mid`,
  print exact `brew install fluid-synth` / `$MUSIC_SOUNDFONT` guidance, and exit
  0 (MIDI-only degradation, not a crash).
- Input not decodable audio -> surface the ffmpeg decode error.
- Unknown instrument name -> list the valid `INSTRUMENTS` keys and exit non-zero.

Reliability: transcription is best-effort (autocorrelation, monophonic); the
render is deterministic once fluidsynth + soundfont are present.

## Testing

`tests/test-core.sh` (zsh assertions, no framework — matches the repo). Add
cases for the pure parts:
- instrument-name -> GM program mapping (valid name resolves; unknown name
  fails).
- the fluidsynth command builder produces the expected argv.
- `write_midi(..., program=N)` output contains a `0xC0` program-change byte,
  and `write_midi(...)` without a program does not (backward-compat).

Transcription accuracy and the actual audio render are verified manually: run
`R)` on a clean monophonic stem, play the output WAV, confirm it plays the
melody in the chosen instrument.

## Out of Scope (YAGNI)

- Polyphonic transcription (chords/strumming).
- Auto-placing the result on a Logic track (user drags the WAV/MIDI in).
- Bundling a soundfont in the repo.
- Per-note velocity/expression modeling beyond the current fixed velocity.
