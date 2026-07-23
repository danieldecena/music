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
  Live data point 2026-07-22: the heavier read tools that walk `entire
  contents of front window` (`logic_list_tracks`, `logic_get_tempo`) TIME OUT
  (10s/20s) against "Logic Pro Creator Studio", and `logic_get_bar_position`
  can't find the transport field on an Untitled project — the ★★-brittle tier
  is confirmed slow/unreliable here. Only the cheap `logic_get_status`
  (running check + window name) is fast and dependable. If these are worth
  fixing, the culprit is the full-tree traversal — scope it to specific
  UI element roles/paths instead of `entire contents`.
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
    3 -> 2 (Exchange recovered to exact), exact 6 -> 7, no new octave errors. Still
    unfixed: Godspeed (3:2 fast), Don't (2:3 slow), Self Control (2:1). Research
    (research-analyst, cited) confirmed the mechanism: essentia's Percival sums
    only duple (2x/4x) harmonics. Dropping our 3x harmonic term was tried and
    REVERTED — redundant with the grid penalty and it broke Pink + White into a
    2:1. Same caveat holds: this improves a correlated-label score, not proven by
    ear. Tap the four tracks to settle it.
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
- Bug found in passing: `logic-pro-mcp/tools/build.py` `_import_stems`/`_import_midi`
  use the menu string `"Audio File..."` (three ASCII dots) — WRONG on Logic 12
  Creator Studio, which uses a real ellipsis `…`. Not fixed this session.
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
