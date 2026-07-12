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
- `Scripts/analyze_track.py`: added `estimate_boundaries()` (spectral-flux
  section/transition detection). Verified via `build-logic-project.sh` run —
  prints `transitions [...]` per stem alongside BPM/key.
- **Stem quality profiles** (merged `feat/stem-quality-profiles`, commit 014bad9).
  `separate_stems` now takes a profile, not a mode: `stem_profile_args` +
  `stem_profile_model` replace `stem_mode_args`. Profiles: `acapella`
  (`--two-stems=vocals`, htdemucs), `fast` (4-stem, htdemucs), `6stem`
  (htdemucs_6s), `hq` (`-n htdemucs_6s --shifts 2 --overlap 0.5`, htdemucs_6s) —
  hq is the clean 6-stem path that isolates guitar/piano and is the Separate
  default. Menu `2)` and `stems.sh` prompt Quality (empty = hq); the full
  pipeline uses `acapella`; `deconstruct` stays `fast`. 18/18 test-core assertions
  pass. Runtime only (no live demucs run in this env) — hq is ~3-4x slower.
- **Per-stem analysis** (merged `feat/per-stem-analysis`, commit 409b918).
  `analyze_stems <folder|stem.wav>` runs ffmpeg `volumedetect` per stem and
  `stem_presence_label` classifies each `silent`/`faint`/`present` from mean+peak
  dBFS (`max < -50` silent; else `mean < -45` faint; else present). Prints an
  aligned table and writes `analysis.txt` beside the stems (read-only, no
  re-encode). Wired into `deconstruct`, an `A) Analyze stems` menu entry
  (current-track aware via `resolve_stems`), and `analyze-stems.sh`. Verified on
  a real `Stems/htdemucs_6s/02 Let Em' Know` folder — guitar/piano correctly
  flagged `faint`, bass/drums/vocals `present`. 20/20 test-core assertions pass.
- **`StudioTUI/` (Rust/ratatui)** — chosen over two other exploratory ports
  (`studio_tui.py`/Textual — deleted; `StudioUI/` HTML mockup — kept as the
  design reference `music-studio.pdf` was rendered from). Builds warning-free
  beyond pre-existing dead-code lints. Pipeline tab's Bass->MIDI, Re-voice
  Melody, and Build Logic Proj actions now call real new wrapper scripts
  (`bass-to-midi.sh`, `revoice.sh`, `build-logic-project.sh` — thin shells
  over `lib/music-core.sh` functions, matching `download.sh`'s pattern).
  Sequencer Export MIDI (`m`) / Render WAV (`w`) now shell out to
  `Scripts/beat_export.py`, best-effort matching WAV rows to real
  `Samples/One-Shots/<track>/{kick,snare,hat}/*.wav` samples where sort_kit
  has classified them. Logic Pro tab (`c` connect, `s` status, `p` play/stop,
  `w` save) now calls `logic-pro-mcp/logic_cli.py` for real instead of faking
  connection state. All three wrapper scripts + `beat_export.py` +
  `logic_cli.py status` verified directly against real repo data (a real
  `Stems/htdemucs_6s/02 Let Em' Know` track); the compiled binary was smoke-
  tested under a pty (clean start/quit, no panic). The Logic-tab/Build-Logic-
  Proj live-Logic-session behavior itself is unverified here (no Logic Pro
  in this environment) — same caveat as the existing `P` build path below.

## Known broken / unverified
- The entire Logic-side UI-scripting path (`P` build: new project + import audio +
  import MIDI) is BEST-EFFORT and has NOT been verified against a live Logic
  session. Selectors (template chooser, import sheets) may need re-deriving with
  `entire contents of front window`. The bass `.mid` fallback covers import failure.
- `R` on a full-length track is slow (autocorrelation over the whole file) — feed
  it short mono loops, not whole songs.
- Transcription is monophonic only; chordal/strummed parts won't transcribe.

## Next Up
- Live-verify the `P` Logic build (and StudioTUI's Logic tab / Build Logic Proj
  action, same underlying `logic_cli.py`/`build_project.py`) with Logic open +
  Accessibility granted; fix any moved selectors.
- Optional: chord-progression analyzer on top of the now-working section-
  boundary detection in `analyze_track.py`.
- Optional: one-shot -> Logic Quick Sampler instrument loader.
- StudioTUI: `cargo build` still emits 4 pre-existing dead-code warnings
  (unused `Focus::SeqBpm`, `fs::skip_dir`, `Theme.seq_pad_off`, unused `Theme`
  style helpers) — harmless, not touched by the TUI-wiring work.
- Optional (deferred from per-stem-analysis spec, YAGNI): per-stem loudness into
  the catalog. `catalog.py scan` rebuilds `assets` every run, so per-asset
  loudness would be recomputed/lost each scan — revisit only if a digest needs it.
- Two design specs still pending a plan->build: none outstanding (resynth,
  build-logic-project, stem-quality-profiles, per-stem-analysis all shipped).

### 2026-07-12
- Decided: bundle stem quality as four named profiles (acapella/fast/6stem/hq)
  instead of exposing raw demucs model names. htdemucs_ft excluded — it is
  4-stem only and cannot produce guitar/piano, which is the user's goal; the
  only path to those is htdemucs_6s, cleaned up with --shifts 2 --overlap 0.5
  (the `hq` default). deconstruct kept on `fast` so the quick-prep path stays
  fast-by-default; keeper-track quality lives in Separate.
- Decided: per-stem analysis uses ffmpeg volumedetect (no new Python deps) and
  writes a human-readable analysis.txt beside the stems rather than into the
  catalog — the beside-stems report delivers the "which stems have audio" value
  without fighting the catalog's rebuild-on-scan model.
