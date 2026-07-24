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
  `replay`, `score`, and `exitcode` modes). See Known broken for accuracy caveats.
  `analyze_track.py` now EXITS NON-ZERO when analysis fails (both the stem-track
  and file-loop branches) — previously it printed "analysis failed" and exited 0,
  fooling callers that gate on the exit code (music-menu, StudioTUI) and
  `deconstruct`'s catalog parse. Guarded by the `exitcode` subprocess test.
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
  Update 2026-07-22: the MCP read path IS now live-verified on this machine —
  `logic_get_status` returns cleanly against a running Logic (no -1728), so the
  app-name parametrization works end-to-end. The write/UI-scripting paths
  (build, bounce, track ops) remain unverified against a live session.
  `logic_get_tempo` and `logic_get_key` now read **scoped Control Bar
  selectors** (the "Tempo" AXSlider / "Key Signature" popup of the inner
  Control Bar group), NOT `entire contents` — fixed in `c56acf3`, so the
  old 10-20s timeout is gone (raw selectors verified in the probe doc; live
  MCP call still unverified). `logic_list_tracks` is the last tool still
  walking `entire contents of front window` and remains slow/at-risk of
  timeout (different UI area, no verified scoped selector yet — deferred).
  `logic_get_bar_position` uses `every text field` (not entire contents) but
  can't find the transport field on an Untitled project. Only the cheap
  `logic_get_status` (running check + window name) is fast and dependable.
- **Chord-progression analyzer** (`Scripts/chords.py`). Bar-by-bar chord
  estimation reusing `analyze_track.py`'s chroma/tempo/key machinery (no DSP
  duplicated — it imports `spectra`, `detect_tempo`, `detect_key`, `_KEEP`,
  `_PROJ`, `stem_track_dir`). 60 z-scored triad+7th templates matched per bar
  with the same z-score-Pearson dot trick as key detection, nudged by a soft
  diatonic prior (`PRIOR=0.15`, the one tuning knob) from the detected key. A
  Stems folder reads tempo from drums and chords from the harmonic stems; a
  single file uses itself. Prints a 4-bars/line chart (repeats collapsed to
  `·`) and writes read-only `chords.txt` beside the input. Exits non-zero on
  failure (matches the `analyze_track.py` exit-code contract). Reached via
  `H) Chords` in the Tools submenu, `chords.sh`, or `chord_progression()` in
  music-core. 24/24 `tests/test-chords.py` synthetic assertions pass;
  live-verified end-to-end on real `Stems/htdemucs_6s/02 Let Em' Know` (120-bar
  chart + sidecar, exit 0). See Known broken for the accuracy caveat.
  Update 2026-07-22: `analyze_chords` now routes an acapella / 2-stem split
  (vocals.wav + no_vocals.wav, no drums/bass) to its `no_vocals.wav`
  instrumental and refuses any other non-stem directory with a clean
  ValueError — closes an "Is a directory" ffmpeg crash found via `/run`.
  26/26 `tests/test-chords.py` pass.
- **Harmonic mix-match finder** (`Scripts/harmonic_mix.py` + `Scripts/lyrics.py`
  + `catalog.py mix`). Ranks compatible pairs of analyzed catalog tracks the way
  a DJ mixes: Camelot-wheel key compatibility (perfect / relative / adjacent with
  12<->1 wrap) plus tempo tolerance (±6% default, half/double-time folded and
  labeled). Tiers strong (key AND tempo) > key-only > tempo-only. Optional
  `--lyrics` re-rank fetches LRCLIB lyrics (urllib, cached to `Samples/Lyrics/`,
  every failure -> None so it never breaks the audio ranking) and re-sorts the
  strong tier by Jaccard theme similarity. Pure-stdlib logic, fully isolated from
  the fragile network layer. `<2` analyzed tracks -> clean message + non-zero
  exit. Reached via `X) Mix-match` in the Tools submenu, `mixmatch.sh`, or
  `mix_match()` in music-core. 45/45 `tests/test-harmonic-mix.py` pass;
  verified end-to-end against the real catalog (relative-key and half/double
  pairs surface; the two "Rambo" versions top the lyric re-rank).
- **Click-comparator** (`Scripts/click_compare.py`) — settles a track's tempo by
  ear, the honest tie-break the analyzer can't make. Auditions the estimate
  against its half/double/1.5x/0.667x octaves (plus any `--label`), laying a
  synthesized metronome click over a ~18s excerpt (drums stem if a Stems folder,
  clearest beat) and playing each candidate via `afplay`; whichever locks is the
  tempo. Reuses `analyze_track`'s decode + `detect_tempo` (no DSP duplicated);
  click synth + candidate/octave logic are the only new pure pieces. Reached via
  `T) Tempo lock` in Tools, `click-compare.sh`, or `click_compare()` in
  music-core; `--render-only DIR` writes mixes non-interactively. 24/24
  `tests/test-click-compare.py` pass; render path verified end-to-end on a real
  Stems drums stem (6 candidate mixes written, base+label+octaves correct). The
  interactive afplay/listen loop is unverified here (headless, no audio out) —
  needs a real listen to settle the 4 tracks.
- **Type-a-title track input** (`Scripts/find_track.py` + `find_tracks`/`pick_track`/
  `resolve_target` in music-core). At any track-level prompt you can now type a
  song title instead of dragging a path — typos tolerated. `find_track.py` (stdlib,
  difflib) fuzzy-ranks Stems folders + source audio (Apple Music/SoundCloud/
  Downloads), collapses a track that is both source and stem to one row (stem
  wins, has drums), and trims the weak tail. `resolve_target` passes an existing
  path through untouched and only searches non-paths; a lone match auto-resolves,
  several show a numbered picker (Enter = best, q = cancel). Wired into
  `click-compare.sh` and the menu's generic file + no-current-track stems prompts.
  18/18 `tests/test-find-track.py` pass.

## Known broken / unverified
- **The tempo octave fix shipped (685a489) on best-available evidence, not
  proof.** Against 10 trusted fixture labels it moves exact 5 -> 6 and octave
  errors 2 -> 1, but trades those for 3:2 errors 1 -> 3 — Exchange and Don't
  went from exact to two-thirds readings. It also removes the old ceiling
  artifact entirely. Still worth settling by ear: tap Exchange, Don't, Rambo,
  Nikes, update `tests/fixtures-analysis.tsv`, drop the `?`, rerun
  `tests/test-analysis.py score`. If the 3:2 errors prove real, the prior's
  sigma (0.85) and the 3.0 harmonic multiplier are the two knobs implicated.
  - **Follow-up shipped 2026-07-22 (triple-grid penalty).** `_grid_support` now
    also samples the 1/3 and 2/3 offsets and penalizes a candidate whose thirds
    are as full as its beats — the signature of a 3:2 metrical misread, which the
    old on-vs-halfway test was blind to. Against the 10 trusted labels: 3:2 errors
    3 -> 2, exact 6 -> 7, no new octave errors. Still
    unfixed: Godspeed (3:2 fast), Exchange (2:3 slow), Self Control (2:1).
    **Corrected 2026-07-23:** this entry originally said "Exchange recovered to
    exact" and listed Don't as unfixed — the two are swapped. Re-running `score`
    shows `Don't 96 -> 99.3 exact` and `Exchange 160 -> 106.7 two-thirds`. The
    aggregate counts above were right; the named tracks were not. Research
    (research-analyst, cited) confirmed the mechanism: essentia's Percival sums
    only duple (2x/4x) harmonics. Dropping our 3x harmonic term was tried and
    REVERTED — redundant with the grid penalty and it broke Pink + White into a
    2:1. Same caveat holds: this improves a correlated-label score, not proven by
    ear. Tap the four tracks to settle it.
  - **Exchange resolved 2026-07-23 (grid lag search, 4300a1d).** The suspects
    named above — the prior's sigma and the 3x harmonic multiplier — were both
    wrong. The real cause was resolution: `_grid_support` laid a rigid tick comb
    at exactly the candidate lag, and at short lags the autocorrelation cannot
    express the right one (at lag 16 / 43 fps, adjacent integer lags are 160.8
    and 152.0 BPM). `_refine_lag` got within ~0.5%, but rigid means that error
    compounds — 0.076 frames/beat over 521 beats walked the grid 39.8 frames off
    the music, 2.5 whole beat periods. Support for the true 160 candidate fell
    1.14 -> 0.64 and it lost a near-tie to the 106.7 misread. Fix: search nine
    lags across +/-2% jointly with the eight phase offsets, keep the best fit.
    +/-2% cannot reach an octave (100%) or a 3:2 (50%), so the discrimination is
    intact. Trusted labels: exact 7 -> 8, two-thirds 1 -> 0, double and
    three-halves unchanged; the other 12 tracks byte-identical. Still open:
    Godspeed (3:2 fast) and Self Control (2:1). Same standing caveat — a
    correlated-label score, not the ear.
- **The catalog's stored bpm/key are stale and the key column is not usable.**
  All 20 analyzed rows carry one timestamp (2026-07-10T09:51:56), predating every
  tempo/key change, and hold only two distinct keys across 20 tracks (F and Am).
  Re-analyzing three at random: `07 Ten Nine Fourteen` F/70 -> C/105.0,
  `13 Overtime` F/103 -> Dm/105.6, `06 Open Interlude` Am/62 -> Am/119.6. The
  four rows overlapping the fixtures are all labelled `F` where the estimator
  reads C, Am, D, A#, and Ivy's published label confirms Am. Consequence:
  `catalog.py mix` returns pairs that are mechanically correct but built on bad
  inputs — its near-universal "perfect" key verdict is an artifact of the flat
  key distribution, not a real match. 38 of 58 tracks have no analysis at all.
  `backfill` will not repair this: it only fills rows where bpm/key are NULL, so
  it skips all 20. A re-index needs a refresh path that overwrites.
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
- **Chord-analyzer accuracy is unverified by ear** — same caveat as tempo/key,
  and it inherits the weak key detection above (its diatonic prior leans on the
  detected key). On real "02 Let Em' Know" it reported key `A` while the chart
  is heavily minor (Am/Bm7/Dm7), i.e. the tonic may be off. The chart is a
  starting estimate, not ground truth. If real charts look noisy with
  out-of-key labels, raise `PRIOR`; if flattened onto the diatonic set, lower
  it — one constant in `Scripts/chords.py`. Synthetic tests cover the mechanism
  (template recovery, prior discrimination, exit code), not real-track accuracy.
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
- **Settle 4 tracks by ear with the new click-comparator** (Exchange, Don't,
  Rambo, Nikes): run `T) Tempo lock` (or `./click-compare.sh`) on each, pass the
  analyzer reading as `--bpm` and the fixture label as `--label`, listen for the
  click that locks, then put the values in `tests/fixtures-analysis.tsv`, drop the
  `?`, and run `.venv/bin/python tests/test-analysis.py score`. The tool now exists;
  this is a pure human-listen step (the last blocker) — no code left.
- Live-verify the `P` Logic build (and StudioTUI's Logic tab / Build Logic Proj
  action, same underlying `logic_cli.py`/`build_project.py`) with Logic open +
  Accessibility granted; fix any moved selectors. Note Logic launches from
  `/Applications/Logic Pro Creator Studio.app` — `open -a "Logic Pro"` fails,
  and `pgrep -x "Logic Pro"` never matches (process is `Logic Pro Creator Studio`).
- Re-record `tests/baseline-analysis.tsv`. The frozen one predates tasks 6-8, so
  its ~65 per-stem rows are obsolete now that a Stems folder collapses to one
  row. Keep the old file until the tempo question is settled — it is the only
  record of pre-change behaviour.
- Optional: one-shot -> Logic Quick Sampler instrument loader.
- StudioTUI: `cargo build` still emits 4 pre-existing dead-code warnings
  (unused `Focus::SeqBpm`, `fs::skip_dir`, `Theme.seq_pad_off`, unused `Theme`
  style helpers) — harmless, not touched by the TUI-wiring work.
- Optional (deferred from per-stem-analysis spec, YAGNI): per-stem loudness into
  the catalog. `catalog.py scan` rebuilds `assets` every run, so per-asset
  loudness would be recomputed/lost each scan — revisit only if a digest needs it.
- Two design specs still pending a plan->build: none outstanding (resynth,
  build-logic-project, stem-quality-profiles, per-stem-analysis all shipped).

### 2026-07-23
- Verified live (Logic off-screen on BetterDisplay VD): the **scoped Control Bar
  tempo/key reads work** — `logic_get_key` returned `C Major` via MCP; tempo
  returns `120.0` (<0.2s) via raw osascript, the shipped `_TEMPO_SCRIPT`, and the
  server's own python, and `120` is legible on the transport. The 20s
  `entire contents` hang is gone. Two caveats: (1) `logic_get_tempo` through the
  *long-running* MCP server returned empty for the AXSlider read (the key popup
  beside it worked) — stale AX context in a server started before Logic existed.
  **Confirmed the fix by restart:** a freshly-spawned `server.py` (started with
  Logic already running), driven over stdio through the real tool dispatch,
  returned `{"bpm":120.0,"source":"transport"}` and `{"key":"C Major"}`. So the
  read fix is fully verified end-to-end; the empty read was purely the stale
  process, cleared by restarting the server. (2) **build.py's live import is
  fragile** — an end-to-end run
  left Logic with 0 windows (no tracks imported) yet returned its hardcoded
  "imported N stems" success string; the summary is unverified. Both filed in
  TASKS. Process for driving Logic off-screen saved to project memory.
- Decided: **build.py now verifies the import before reporting** (logic-pro-mcp
  1aa52b9). Two pure read-only script builders (`_track_count_script`,
  `_window_count_script`) drive a before/after track-header count and a
  window-count check: no window afterward -> `ToolError` (the exact 0-window
  failure above); count didn't rise for the stems -> an explicitly *unverified*
  summary instead of the old unconditional success; count rose -> reports the
  verified track count, flagging any shortfall. Reads use bare `tell process`
  (no activate) so verification never steals focus off-screen. Live-checked both
  primitives against the running off-screen Logic (`window_count=1`,
  `track_count=1`); did not re-run the full fragile build against the live
  session. TDD (+2 pure-builder tests, 39 green).
- Probed (ad-hoc, nothing landed in the repo): **`beat_this` as an independent
  tempo cross-check.** madmom is a dead end — its PyPI release is from 2017, breaks
  on Python >=3.10 and pins numpy <2 (we run 3.14.6 / numpy 2.5.0); git-main is
  CI-tested only to 3.12 and last moved Aug 2024. BeatNet inherits that. `beat-this`
  1.1.0 (CPJKU, transformer) installed clean on 3.14 with torch 2.13 — but needs
  `soundfile` (its loader falls back to madmom otherwise). Results vs ours/label:
  Don't 96.8/99.3/96 and Exchange 81.1/106.7/160 came back on **clean 4/4 bars**;
  Nikes (120.0, 3.5-beat bars) and Rambo (176.5, 5.8-beat bars) came back
  **incoherent** — it fails on exactly the two `?` rows, as the octave-ambiguity
  caveat predicted. Value: confirmed Don't (3-way agreement, drop it from the ear
  list) and caught the Exchange/Don't mixup above. Downbeat-spacing coherence, not
  the BPM, is what made its output trustworthy or not. Not wired in — a multi-GB
  torch dep for a 2-track gain isn't worth it; revisit if cross-checking every
  track becomes routine.
- Decided: **click_compare writes the fixtures row itself** (149a7aa). On lock it
  updates the matching `fixtures-analysis.tsv` row in place (dropping the `?`),
  preserving path + key, and offers to rerun `score` — killing the copy-paste that
  was the only friction left in the tempo-lock task. Pure `_apply_locked_bpm`
  (update/nomatch/ambiguous), TDD. A standalone **tap-tempo tool was rejected as
  redundant** (click_compare already auditions the octave/3:2 candidates by ear)
  and **Logic Smart Tempo stays ruled out** (import into Logic unreliable). The
  `LISTEN: Tempo lock` task stays open — still ear-blocked; only the paste friction
  is gone.
- Decided: track prompts accept a **typed title, not just a dragged path**
  (`Scripts/find_track.py`, stdlib difflib). Fuzzy so typos still match; a lone
  hit auto-resolves, several show a picker. Kept it out of the bass-stem and
  One-Shots-folder prompts (they want a specific sub-asset, not a track) — only
  the track-level prompts (`click-compare.sh`, generic file, no-current-track
  stems) route through `resolve_target`. `resolve_target` passes real paths
  through untouched so nothing regresses for drag users. TDD (18 tests).
- Shipped: **click-comparator** (`Scripts/click_compare.py` + `click-compare.sh` +
  `click_compare()` in music-core + `T) Tempo lock` menu, TDD). This is the chosen
  unblock for the parked "settle the 4 tempos by ear" task — Logic Smart Tempo was
  ruled out (can't report a single BPM for a finished song), so the tool lays a
  synthesized metronome click over a track excerpt at each candidate BPM (estimate +
  half/double/1.5x/0.667x octaves + optional `--label`) and plays them via `afplay`;
  the ear picks the one that locks. Decided to reuse `analyze_track` decode/tempo
  rather than duplicate DSP (mirrors how `chords.py` imports it); the only new pure
  logic is click synthesis + octave-candidate generation, both unit-tested (24/24).
  Verified the render path end-to-end on a real drums stem (6 mixes, candidates
  correct); the interactive listen loop is inherently ear-gated and unverified
  headless. **Next actual step is a human listen** — run `T) Tempo lock` on
  Exchange/Don't/Rambo/Nikes, then update `fixtures-analysis.tsv` and rerun score.
- Shipped (logic-pro-mcp `c56acf3`, pushed): `logic_get_tempo` and `logic_get_key`
  now read **scoped Control Bar selectors** instead of `entire contents of front
  window`, killing the 10-20s timeout. Root cause for tempo was structural, not just
  slow: the BPM is an `AXSlider`, so the fast text-field path (`_get_fields`) could
  never see it and every call fell to the 20s full-tree scan. New primary reads bind
  `icb` (inner Control Bar group) and pull the "Tempo" slider / "Key Signature" popup
  directly — the selectors live-verified in `docs/smart-tempo-probe.md` (120.0 /
  C Major). Factored into a pure `_control_bar_read_script` builder (testable without
  Logic, mirrors `tracks._select_track_script`); deleted `_UI_VALUES_SCRIPT`,
  `_tempo_from_ui`, `_BPM_DECIMAL_RE`, `_KEY_POPUP_SCRIPT`, `_KEY_RE`. `.logicx`
  fallback unchanged. 35 tests pass (4 new pure-builder asserts). **`logic_list_tracks`
  is now the last `entire contents` reader** — deferred (different UI area, no verified
  scoped selector yet). Live MCP call unverified this session (Logic not running); raw
  AppleScript already proven in the probe doc, unit + static checks gate the change.
- Explored using **Logic Pro Smart Tempo as an independent tempo detector** for the
  4 unsettled tracks (Exchange/Don't/Rambo/Nikes), driving Logic live on an
  off-screen BetterDisplay virtual display. RULED OUT — Logic Smart Tempo does not
  report a single BPM for a finished mixed song. What worked: the off-screen harness
  (Logic launches, parks, and takes menu/keystroke automation invisibly); the Smart
  Tempo control is `pop up button 2` of the Control Bar (KEEP/ADAPT/AUTO), settable;
  and the tempo is readable directly from an `AXSlider` value (defused the read-back
  kill-risk). What failed: opening/importing Exchange.m4a imported the audio but left
  `File Tempo: 0.00`, project stuck at 120 KEEP — Smart Tempo is built to tempo-MAP
  performances, not to report a master's BPM. Forcing a region analysis would likely
  yield a tempo map, not one number. Decision: abandon the Logic path; recommend the
  click-comparator (metronome-at-candidate-BPM, listen for the lock) to settle the 4
  tempos. Redirect left open with the user (not yet chosen). Full live-discovery
  notes: `logic-pro-mcp/docs/smart-tempo-probe.md`.
- Fixed (logic-pro-mcp `babbad8`, pushed): `build.py` `_import_stems`/`_import_midi`
  clicked `"Audio File..."` / `"MIDI File..."` (three ASCII dots) with a wrong
  `menu "Import" of menu "File"` nesting — silently no-ops on Logic 12 Creator
  Studio, which uses a real ellipsis `…`. Corrected the glyph AND the nesting to
  the probe-verified `menu 1 of menu item "Import" of menu 1 of menu bar item
  "File" of menu bar 1`, via a new pure `_import_menu_click` builder (2 tests,
  37 pass). The full `P` build UI path is still best-effort / unverified live.
- Env note: a focus-stealing game (Hearthstone/Battle.net) and macOS out-of-process
  open panels made live modal UI-scripting flaky — relevant to any future Logic
  automation.

### 2026-07-22 (later)
- Shipped: harmonic mix-match finder (`feat/harmonic-mix-match`), brainstormed +
  spec'd + planned + built TDD in 4 commits, then merged. Scope decided with the
  user: rank pairs from the EXISTING catalog (no discovery/download), "mix well"
  = DJ harmonic mixing (Camelot key adjacency + tempo tolerance incl.
  half/double), lyrics a SECONDARY opt-in re-rank. Hardened per "harden this":
  null/unknown key+bpm excluded at query and re-checked in `rank_pairs`; flats
  mapped defensively though the analyzer emits sharps; unordered-pair dedupe;
  `<2` tracks -> clean non-zero exit; the lyrics/network layer is fully isolated
  (urllib timeout, disk cache, all-exceptions->None, opt-in flag) so it can never
  crash or change the audio ranking. Pure logic in `harmonic_mix.py` (no DB, no
  net) tested to 45 assertions; `lyrics.py` greenfield; `catalog.py mix`
  subcommand with `--json`/`--limit`/`--tempo-tol`/`--lyrics`. `from __future__
  import annotations` added so the `str | None` hints run under system py3.9.
- Fixed: `H) Chords` crashed with an opaque ffmpeg "Is a directory" when fed an
  acapella / 2-stem split folder (only vocals.wav + no_vocals.wav) — `stem_track_dir`
  correctly returned None, but the fallback handed the directory to ffmpeg.
  `analyze_chords` now resolves such a split to its `no_vocals.wav` instrumental
  and raises a clean ValueError for any other non-stem directory. Found via `/run`,
  fixed TDD (two new `dirs` cases). 26/26 chord tests pass.
- Clarified (reading this log against `fixtures-analysis.tsv`): the parked
  "drop the `?`" task named the wrong rows. Self Control / Godspeed / Don't carry
  NO `?` — they are already in strict scoring. The `?` rows are Nikes / Nights /
  Rambo, and the standing decision (recorded below) is to NOT edit them off a
  black-box source without the ear. Both tempo tasks are therefore ear-blocked,
  not code-actionable; TASKS.md collapsed to the single tap-4-tracks item.
- Live-verified the logic-pro-mcp app-name fix (committed last session in the
  nested logic-pro-mcp repo): with the MCP server reattached, `logic_get_status`
  returns "Logic Pro is running" against a running "Logic Pro Creator Studio"
  with no -1728 — the systemic hardcoded-"Logic Pro" bug is closed for the read
  path. Write/UI-scripting tools (build, bounce, track ops) still need a live
  check.
- Shipped: `analyze_track.py` exits non-zero on analysis failure (+ TDD
  `exitcode` subprocess test). Closes the silent-failure hole where a corrupt
  file read green. TASKS.md tasks 1-2 done; task 3 (re-record replay baseline)
  still blocked on the ear.
- RESOLVED much of the tempo-verification question with INDEPENDENT (non-Echo-
  Nest) sources, not the ear. RunHundred (distinct pipeline) + Beatport corroborate
  the analyzer's SLOWER readings, exposing the fixture's Echo-Nest labels as the
  errors: Nikes analyzer 69.1 vs indep 69 (fixture 137 is the double); Rambo
  analyzer 89.7 vs indep ~91 — Echo Nest's 181 was the *2020 "Last Blood" remix*,
  a different song the aggregators merged; Don't analyzer 99.3 vs indep ~97 (agree).
  Exchange resolved separately: on the CLEAN drums stem the analyzer reads 161.1
  = Echo Nest 160 (the junk 106.7 was purely the corrupt-mvhd `.m4a`; RunHundred's
  80 is the half-time feel). Net: the analyzer looks CORRECT on all four; the
  suspect fixture rows (Nikes 137?, Rambo 181?) are the ones wrong. Have NOT
  edited `fixtures-analysis.tsv` yet — updating ground-truth labels off a
  black-box source (RunHundred's method undisclosed) is a call to make with the
  ear as final tie-break; recorded here so the evidence isn't lost.
- Decided: cut the 3:2 tempo regression with a triple-grid penalty in
  `_grid_support`, not by touching the harmonic-multiplier weights or the prior.
  Web-grounded DSP research (research-analyst; Gemini offload was down) named the
  mechanism — essentia's Percival reinforces only duple (2x/4x) autocorrelation
  harmonics, and `_grid_support` only tested the halfway offset, so triple-meter
  misreads (real onsets on the 1/3, 2/3 slots) sailed through. Adding the thirds
  test moved 3:2 errors 3 -> 2 and exact 6 -> 7 with no new octave errors.
- Learned (measured, four configs): dropping the 3x harmonic term from
  `_TEMPO_MULTS` is a WASH on its own (fixes Godspeed, breaks Pink + White into a
  2:1) and REDUNDANT once the grid penalty exists — Edit-2-alone scored identically
  to Edit-1+Edit-2. Kept only the grid penalty; reverted the harmonic-term change.
- Learned: the `replay` test has been RED since before this session — the frozen
  `baseline-analysis.tsv` predates the octave fix, chroma rewrite, and boundary
  rewrite, so its per-stem rows are obsolete. Proven by stashing the working edit
  and re-running: identical drift with and without the change. It isn't guarding
  anything until re-recorded (tracked). The synthetic suite (18 assertions) stays
  the real regression gate.
- Caveat unchanged: the fixture labels are Echo-Nest-derived and correlated, so a
  better `score` is necessary-not-sufficient. Settle by ear (tap Exchange,
  Godspeed, Don't) before trusting it.
- Shipped: chord-progression analyzer (`Scripts/chords.py`), brainstormed +
  spec'd + planned + built TDD on `feat/chord-progression-analyzer` in 4 commits.
  Decided to IMPORT from `analyze_track.py` rather than duplicate any DSP — the
  per-bar chroma is the exact `_beat_features` recipe, matching is the
  `_key_from_chroma` z-score-dot trick over 60 triad+7th templates. Soft
  diatonic prior chosen over hard-constraint (borrowed chords are constant in
  sampled soul) and over pure-match (too noisy); `PRIOR=0.15` is a first guess,
  the single retune knob. Granularity per-bar (not per-section/per-beat), vocab
  triads+7ths (not full jazz — chroma can't resolve 9ths/sus reliably). Verified:
  24/24 synthetic tests incl. a deterministic prior-flip case (C vs its vi Cm in
  D# major) and an exit-code subprocess test; live 120-bar chart on a real
  6-stem folder. Caveat carried to Known broken: real-track accuracy is
  ear-unverified and rides on the weak key detector.

### 2026-07-21
- Decided: build `music-menu/` — a new ratatui menu-launcher for the flip path in
  the external "Ratatui Design" Claude Design system (navy/cream/yellow, JetBrains
  Mono, box-drawing, yellow reversed-video selection). Chosen over restyling
  StudioTUI so its LCD-Green/Phosphor look is untouched. Adapted the design kit's
  `script-menu` template; reused StudioTUI's `worker::run_zsh` pattern (stdin
  nulled, `sh_quote`) so it calls arg-driven `lib/music-core.sh` functions, never
  the interactive `*.sh` wrappers (which read stdin and would hang the TUI).
- Built warning-free (cargo build + clippy clean). Verified in tmux: renders to
  the design, source picker discovers the real library, and running Tempo & key
  streamed `analyze_track`'s live output + status. Note: analyze_track exits 0 but
  prints "analysis failed" on `03 Exchange.m4a` (corrupt mvhd time scale in that
  file) — a pre-existing pipeline/ffmpeg quirk, faithfully surfaced by the TUI,
  not a menu bug.
- Fixed the zsh `music` menu navigation the same session: Download (arm 1) now
  auto-selects the fetched track; arms 1/8 accept a pasted URL (download->select);
  "Need an audio file" now guides; blank Enter redraws. And logic-pro-mcp's
  `_ensure_logic_running` launched `open -a "Logic Pro"` (wrong app on this
  machine) and hung 30s — now launches `LOGIC_APP_NAME` (default "Logic Pro
  Creator Studio", env-overridable) and fails fast. Both committed + pushed.
- CORRECTION to the tmux-verification claim above: it was a false PASS. The
  "analysis failed" line was NOT the Exchange mvhd quirk — it was a path bug that
  broke EVERY source/stem step. `main.rs` took the CLI root arg raw; launched with
  a relative `..` (the README's own `cargo run -- ..`), `find_sources` baked `../`
  into every path while `run_zsh` also set cwd to `..`, so `../Apple Music/x`
  resolved from the wrong dir -> "No such file or directory". The earlier verify
  saw "analysis failed", pattern-matched it to the known mvhd issue, and never read
  the actual error text — the exact "can't tell no-diff from not-shown" trap logged
  on 2026-07-18. Reproduced on `01 Nikes.m4a` (a clean file), not just Exchange.
- Fixed: `let root = root.canonicalize().unwrap_or(root);` in main.rs, so discovery
  and run cwd are both absolute. Re-verified by driving the TUI with `..`:
  `analyze_track` now runs the absolute path and returns `69.1 BPM key C` + ✓ done.
  Also added 14 unit tests for the pure fns (sh_quote real-shell round-trip incl.
  injection, build fns, short_label, display_val) — these don't cover the path/cwd
  seam, which is why running the app caught what the tests couldn't.
- Two UX rough edges found while driving (NOW FIXED, main.rs key routing): in a
  filtered list the first Enter only committed the filter (a second opened the
  step) — Enter in filter mode now calls `start_selected()`, so one Enter runs the
  highlighted step. And Esc from a committed filter used to quit the app — menu-mode
  Esc now clears a non-empty filter first and only quits when there's nothing left
  to back out of. Re-verified in tmux: filter->Enter opens the step; Esc drops
  Steps (2)->Steps (8) with the app still alive, second Esc quits.
- Also unaddressed: the TUI marks a step `✓ done` purely on exit code, so a step
  that self-reports failure while exiting 0 (like analyze_track on a bad file) still
  reads green.

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
