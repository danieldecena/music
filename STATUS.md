# STATUS — music toolkit

## Confirmed working
- `./music` interactive menu. No `set -e` (a failed step returns to the prompt).
- Menu options: 0 Guide, L Library (name filter, descends into track folders),
  M Bass->MIDI, O Open outputs, 1-9 pipeline, 8 Deconstruct (now also chops vocals).
- `R) Re-voice a melody` — 35 GM instruments by name + multi-soundfont picking.
  Transcribe (mono, widened range) -> MIDI -> fluidsynth render to WAV.
  Verified end-to-end on 8s clips (piano, guitar, sitar). Needs fluid-synth +
  a soundfont in `soundfonts/` (FluidR3_GM.sf2 installed; both gitignored).
- `Scripts/resynth.py` + generalized `bass_to_midi.py` (backward-compatible
  pitch-range params + optional program-change). Pure parts verified.
- logic-pro-mcp: `tools/build.py` (collect_stems + best-effort UI build),
  `build_project.py` CLI, MCP tool `logic_new_project_with_stems`. 27 tests pass.
  `P` build now also transcribes the bass and imports it as a MIDI instrument
  track; bass `.mid` always saved to `Samples/MIDI/` as a fallback.
- Fixed `session.py` `_get_fields` empty-return bug (AppleScript `result` clobber);
  `logic_get_bar_position` works again.

## Known broken / unverified
- The entire Logic-side UI-scripting path (`P` build: new project + import audio +
  import MIDI) is BEST-EFFORT and has NOT been verified against a live Logic
  session. Selectors (template chooser, import sheets) may need re-deriving with
  `entire contents of front window`. The bass `.mid` fallback covers import failure.
- `R` on a full-length track is slow (autocorrelation over the whole file) — feed
  it short mono loops, not whole songs.
- Transcription is monophonic only; chordal/strummed parts won't transcribe.

## Next Up
- Live-verify the `P` Logic build with Logic open + Accessibility granted; fix any
  moved selectors.
- Optional: song-map / structure + chord-progression analyzer (spec-scoped, not
  built; would need librosa + matplotlib).
- Optional: one-shot -> Logic Quick Sampler instrument loader.
- Two design specs still pending a plan->build: none outstanding (resynth shipped;
  build-logic-project shipped).
