# STATUS — music toolkit

## Confirmed working
- `music.sh` / `music` interactive menu (both `~/Bin` symlinks; `./music` from the
  repo also works). No `set -e` (a failed step returns to the prompt).
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
- `Scripts/analyze_track.py` — reworked 2026-07-18. One spectral pass (`Spec`)
  shared by tempo/key/boundaries. Tempo: refined-lag candidate scoring.
  Key: 55-2000 Hz weighted chroma, vectorized. Boundaries: beat-synchronous
  SSM + checkerboard novelty, snapped to the bar grid. A Stems track folder is
  analyzed as ONE track (tempo from drums, key from bass+other) — it no longer
  fans out per stem. Tests: `tests/test-analysis.py` (18 synthetic, plus
  `replay` and `score` modes). See Known broken for accuracy caveats.
- **Stem quality profiles** (merged `feat/stem-quality-profiles`, commit 014bad9).
  `separate_stems` now takes a profile, not a mode: `stem_profile_args` +
  `stem_profile_model` replace `stem_mode_args`. Profiles: `acapella`
  (`--two-stems=vocals`, htdemucs), `fast` (4-stem, htdemucs), `6stem`
  (htdemucs_6s), `hq` (`-n htdemucs_6s --shifts 2 --overlap 0.5`, htdemucs_6s) —
  hq is the clean 6-stem path that isolates guitar/piano and is the Separate
  default. Menu `2)` and `stems.sh` prompt Quality (empty = hq); the full
  pipeline uses `acapella`; `deconstruct` stays `fast`. 18/18 test-core assertions
  pass. Live-verified against demucs 4.0.1 / torch 2.12.1 (MPS) on Jordana
  "01 Summer's Over": hq produced all 6 stems; guitar came out `present`
  (mean -24.2 / peak -1.6 dB), piano `faint`. hq is ~3-4x slower.
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
- **The tempo octave fix shipped (685a489) on best-available evidence, not
  proof.** Against 10 trusted fixture labels it moves exact 5 -> 6 and octave
  errors 2 -> 1, but trades those for 3:2 errors 1 -> 3 — Exchange and Don't
  went from exact to two-thirds readings. It also removes the old ceiling
  artifact entirely. Still worth settling by ear: tap Exchange, Don't, Rambo,
  Nikes, update `tests/fixtures-analysis.tsv`, drop the `?`, rerun
  `tests/test-analysis.py score`. If the 3:2 errors prove real, the prior's
  sigma (0.85) and the 3.0 harmonic multiplier are the two knobs implicated.
- Do NOT "simplify" the tempo fix to just sub-lag refinement. Measured: exact 3,
  octave 5 — WORSE than the original argmax (exact 5, octave 2). Refinement and
  the candidate scoring only work together; refinement alone makes a widened
  range actively harmful.
- All labels in `tests/fixtures-analysis.tsv` are Echo Nest-derived (tunebat /
  songbpm / getsongbpm / musicstax all re-display one pipeline). Their agreement
  is correlated, not corroboration, and they carry the same octave-error risk
  being measured. Rows ending `?` are already suspect.
- Key detection is no longer degenerate but is still weak: 2/13 exact against
  published keys, unchanged by the chroma rewrite. The rewrite fixed the
  collapse (44% of baseline rows reported "F"), not the accuracy.
- NEGATIVE RESULT — do not rebuild this. An attempt to settle the tempo question
  without the ear, by scoring which BPM hypothesis makes harmonic change points
  land on whole 4/8-bar boundaries, was written, validated, and then discarded.
  It works on synthetic audio with exact 8-bar sections (rejects 3:2 errors with
  0.17-0.35 separation) but FAILED the control test on real music: for Ivy,
  where the published 116 and our 118 agree, it ranked 137 and 96 above both and
  rejected the correct answer. Real-track separations were ~0.04, inside its own
  noise. It is also octave-blind by construction — an 8-bar grid at B is exactly
  a 4-bar grid at B/2 — so it could never have settled Rambo or Nikes anyway.
- The entire Logic-side UI-scripting path (`P` build: new project + import audio +
  import MIDI) is BEST-EFFORT and has NOT been verified against a live Logic
  session. Selectors (template chooser, import sheets) may need re-deriving —
  use `logic_dump_ui_hierarchy`, which now actually works (see below).
  The bass `.mid` fallback covers import failure.
- `R` on a full-length track is slow (autocorrelation over the whole file) — feed
  it short mono loops, not whole songs.
- Transcription is monophonic only; chordal/strummed parts won't transcribe.

## Next Up
- **Tap 4 tracks** (Exchange, Don't, Rambo, Nikes), put the values in
  `tests/fixtures-analysis.tsv`, drop the `?`, then run
  `.venv/bin/python tests/test-analysis.py score`. The tempo fix already
  shipped; this decides whether its 3:2 tradeoff is real and worth tuning out.
  The only remaining task-list item, and it needs an ear rather than code.
- Live-verify the `P` Logic build (and StudioTUI's Logic tab / Build Logic Proj
  action, same underlying `logic_cli.py`/`build_project.py`) with Logic open +
  Accessibility granted; fix any moved selectors. Note Logic launches from
  `/Applications/Logic Pro Creator Studio.app` — `open -a "Logic Pro"` fails,
  and `pgrep -x "Logic Pro"` never matches (process is `Logic Pro Creator Studio`).
- Re-record `tests/baseline-analysis.tsv`. The frozen one predates tasks 6-8, so
  its ~65 per-stem rows are obsolete now that a Stems folder collapses to one
  row. Keep the old file until the tempo question is settled — it is the only
  record of pre-change behaviour.
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

### 2026-07-18
- Decided: freeze a behavioural baseline BEFORE touching analyze_track.py. It
  proved the old detector was degenerate in three independent ways that were
  invisible without it: tempo railed at its 184.6 BPM ceiling on 28/120 rows
  (49/120 sat on just 3 integer lags), key collapsed to "F" on 53/120, and
  boundaries fired every 8s because the minimum-gap filter, not the threshold,
  was doing the work.
- Decided: do NOT commit the tempo octave fix until it is verified by ear. It is
  objectively correct on synthetic signals (140 BPM read as 69.8 before, 140.3
  after) and the sub-lag refinement is a genuine correctness fix -- at ~43
  envelope fps, integer lags cannot represent 140 BPM at all. But against
  published BPM it scored 6/13 both before and after, and the published values
  are one algorithm with the same octave bias. Reasoning that sounds right is
  not evidence.
- Learned: the plan's diagnosis of octave errors as a *scoring* problem was
  incomplete. The mechanism is lag quantization -- an 0.46-frame-per-beat error
  accumulates to a full beat of drift in 30s, which collapses the evidence for
  the FAST candidate while the slow one drifts half as fast. The resolution
  asymmetry itself biases toward halving.
- Learned: `entire contents of front window` returns ZERO elements for Logic
  Pro 12.3 even when frontmost, so logic_dump_ui_hierarchy silently returned "".
  Walk with `every UI element` and recurse through a handler parameter --
  storing element refs in a list and mutating it invalidates them (-10000).
- Learned: "simplify to only the provably-correct part" was itself falsified.
  Sub-lag refinement alone scored exact 3 / octave 5, worse than the original
  argmax (5/2), while refinement plus candidate scoring scored 6/1. The safe-
  looking subset was the worst of three variants -- measuring it before shipping
  it is the only reason that was caught.
- Learned: a verification step that cannot distinguish "no differences" from "I
  was not shown the differences" is worthless. Piping a replay through `tail -60`
  silently dropped every full-mix row (source paths sort before Stems/), and a
  confident drift summary was then built on the survivors. Same silent-failure
  shape as the dump returning "" and deconstruct's sed writing to /dev/null --
  three in one session. Counts now sum to a known total.

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
