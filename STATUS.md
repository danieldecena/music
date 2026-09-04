# STATUS — music toolkit

## Confirmed working
- **`Tools/mu-analyze`** (gitignored binary, source `Tools/mu-analyze.swift`) — a
  macOS CLI over Apple's `MusicUnderstanding` framework. Dumps rhythm, key,
  structure, loudness, pace and instrument activity for one audio file as JSON.
  Build: `swiftc -parse-as-library -O -o Tools/mu-analyze Tools/mu-analyze.swift`.
  Observed on `02 Ivy.m4a`: exit 0, 6.4 MB JSON, 57.4s for a 249s track.
- **`Z) Mix report` / `./mix-report.sh` / `catalog.py mix --seed <title>`** — pivots
  on one named track instead of dumping every library pair. Prints a verdict, a
  why-line, rarest-first shared lyric words, and near misses; `--preview` renders
  a tempo-matched crossfade of the top pair, starting each track at its nearest
  detected section boundary (not a fixed offset — fixed 2026-07-24), and plays
  it via `afplay`. Verified
  against the live catalog for seed hits, near-miss-only seeds, nomatch (exit 1),
  `--preview` without `--seed` (exit 1), `--json`, and the unchanged library-wide
  path. Rendering is pure (`Scripts/mix_report.py`), as is the ffmpeg command
  builder (`Scripts/mix_preview.py`); 52 assertions in `tests/test-mix-report.py`.
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
- `scan` still keys tracks by filename stem, so two files with the same name are
  one row — but the collision is now **resolved by decodability and reported**
  rather than decided by iteration order (see the decision log). Keying by album
  instead is not available: `Stems/` and `Samples/` folders on disk are named for
  the bare stem, so an album-qualified key would orphan every derived asset from
  its track. Renaming those folders is the real fix, and it is a migration, not a
  patch. Today's library has exactly one collision.
- **Mix-report caveats, for anything read off `catalog.py mix`.** BPM/key are
  estimates from this repo's analyzer. Tempo is the solid half; key is the weak
  half at 2/13 exact against published labels, so treat key relationships as a
  shortlist to confirm by ear rather than a verdict. The optional lyric score is
  an IDF-weighted word-set overlap — it finds shared vocabulary, not shared
  meaning, so a high score means the two songs use the same words, not that they
  are about the same thing.
- Do NOT "simplify" the tempo fix to just sub-lag refinement. Measured: exact 3,
  octave 5 — WORSE than the original argmax (exact 5, octave 2). Refinement and
  the candidate scoring only work together; refinement alone makes a widened
  range actively harmful.
- All labels in `tests/fixtures-analysis.tsv` are Echo Nest-derived (tunebat /
  songbpm / getsongbpm / musicstax all re-display one pipeline). Their agreement
  is correlated, not corroboration, and they carry the same octave-error risk
  being measured. Rows ending `?` are already suspect.
- Key detection was WEAK (1/10 exact vs the independent UG oracle) and is now
  **FIXED to 4/10 exact, 7/10 sharing the pitch-class set** (`key_oracle.py
  score`, 2026-07-24, `_chroma_projection` in `analyze_track.py`). Two changes,
  and the second one is where the real fix was:
  - Subharmonic-summation votes (3rd/5th harmonic -> its subharmonic's pitch
    class) alone moved NOTHING — same 1/10 exact, same per-track buckets,
    confirmed by `git stash` diff. The "weak fundamental" theory was wrong (or
    at least not the dominant cause).
  - **The actual bug: `_chroma_projection`'s per-pitch-class total weight was
    content-independent and uneven.** Linear FFT bin spacing vs. logarithmic
    semitone spacing means a bin can span more than a semitone at the low end
    of 55-2000 Hz, and `np.rint(midi) % 12` rounds each such bin to one pitch
    class — which classes catch the extra bins is an accident of the
    frequency grid. Proof: pure white noise (zero tonal content) still
    resolved to a specific key (`D`; column totals ~16.2 for D/A vs ~11.3 for
    C#/D#) regardless of what's playing. Equalizing the column totals in
    `_chroma_projection` collapsed that bias (white-noise chroma spread 0.030
    -> 0.001) and, *combined with* the subharmonic votes (normalization alone
    only got to 2/10 exact, 3/10 pitch-class), took the oracle score to 4/10
    exact, 7/10 pitch-class match. The two fixes are synergistic, not
    independently additive — measured across 4 variants (baseline, harmonics
    only, normalize only, both) before shipping.
  - Remaining misses (Pink+White, Nights, Godspeed, The Color Violet): Nights
    and Pink+White are now `unrelated` rather than a near-tie; Godspeed reads
    `adjacent` (a fifth off — plausible dominant/tonic confusion, a smaller
    problem than the pre-fix wrong-pitch-class-entirely errors). All 21
    `test-analysis.py` and 26 `test-chords.py` assertions still pass.
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
- **A loop ranking is platform-dependent and stays that way.** MusicUnderstanding
  produces materially different structure-prediction curves on macOS and iOS
  (max |delta| 0.056 to 0.176 across levels), which flips which of two adjacent
  candidate boundaries it emits. Measured on `testclip.m4a` the effect is
  confined to ranks 7-10 and the top pick is unchanged, but that is one clip.
  Reconciled 2026-09-04, not fixed -- mechanism and numbers in the decision log.

## Next Up
- **[you] Tempo lock on Nikes + Rambo** — the two remaining `?` rows. `T) Tempo lock`
  now writes the fixtures row and reruns `score` itself, so this is a pure listen
  step. Tried and exhausted without the ear: independent BPM sources, `beat_this`
  (incoherent on exactly these two), Logic Smart Tempo (ruled out).

Full open list: `TASKS.md`.

**Parked, not scheduled:** live-verify the `P` Logic build with Logic open +
Accessibility granted (selectors may have moved; Logic launches from
`/Applications/Logic Pro Creator Studio.app`, and `pgrep -x "Logic Pro"` never
matches). One-shot -> Logic Quick Sampler loader. Per-stem loudness into the
catalog (YAGNI — `scan` rebuilds `assets` every run). StudioTUI's 4 pre-existing
dead-code warnings.

## Decision log

### 2026-09-04

- Decided: **the stem map is republished under the icloud account and the gmail
  url is retired.** Daniel switched the CLI login to danieldecena@icloud.com
  (uuid 1414539c); `~/.claude-work/.claude.json` still holds the gmail account,
  so the two directories now genuinely differ where earlier today they did not.
  New url `c5d0c33b`, owned by the account that persists.
- Observed: **the old artifact cannot be updated from here, and the failure is
  explicit rather than silent.** A republish was refused ("could not verify the
  target page is not a review page"), and a direct read of `ace836b3` returns
  "served to you as a public (non-member) reader". `Artifact list` under icloud
  shows 15 artifacts, none of them tonight's two -- and it does include
  `db42c89c`, which another session had guessed was icloud-owned, so that guess
  is now confirmed rather than assumed.
- Mechanism worth knowing: an artifact is bound to (conversation, file path), so
  a republish of the same path keeps trying to reach the old page. Minting under
  the new account required a new path, which is why the generated page is now
  `flip-stem-map.html`. The content is byte-identical -- it restamped to the same
  `43306caaa3bc`, which is the determinism property doing its job.
- Consequence, currently RED and not mine to fix: **invariants check 29 fails**
  with "binding not on the register: c5d0c33b / on the register but not bound
  anywhere: ace836b3". That is the check working -- it caught a url change the
  same night it was widened, which is the discrimination its author wanted to
  demonstrate. The fix is a one-row edit to paper-system's hand-authored design
  canvas, which belongs to the session that owns that tooling.

- Shipped: **the three timeline tabs, branch `flip-timeline-tabs`
  (`cdf61dc..eb423b8`, 12 commits).** Analysis (four activity lanes on a bar grid
  with section rules), Lyrics (timed `.lrc` against the same grid), Loops (ranked
  candidates, each playable). `LoopScorer.swift` and
  `TimedLyrics.swift` are ports of `Scripts/regions.py` and `Scripts/lyrics.py`
  with parity tests pinned to the Python's current output. 31 tests in 4 suites.
- Observed, by screenshot of the running simulator app: BPM 116.6, C major, 14
  bars, 2 sections, lane peaks drum 0.09 / bass 0.35 / other 0.85 / vocal 0.82;
  Lyrics 11 lines, "Back then" first at 0:02.32; Loops ranked 0.47 down to 0.27.
- Decided: **Task 7's "confirm you hear audio" step replaced with an offline
  assertion.** No device attached. The engine is driven through
  `enableManualRenderingMode` and the test asserts non-zero RMS over rendered
  frames plus repeat N starting at exactly `N * length`. `isPlaying == true` was
  explicitly ruled insufficient: a transport running over silence is the failure
  that step existed to catch. Audio session category, output routing and hardware
  playback remain unverified and parked.
- Found and fixed: **`LoopEngine` was not `@Observable` while `LoopList` read
  `engine.isPlaying` in the view body.** Playback stopped correctly; the icon did
  not update, so the control read as broken. Fixed in `eb423b8`. Worth noting how
  it was caught -- no UI test and no driveable tap exist on this machine, and it
  was still established with certainty by reading for the missing dependency edge.
  "No interaction test" is not the same as "no evidence available".
- RETRACTED, my error: **I claimed `App/Flip/Resources/README.md` recorded a stale
  sha.** `shasum` defaults to SHA-1 (`111194ee...`); `shasum -a 256` gives
  `1552377b...`, which is exactly what the README says. I compared the two and
  wrote a "correction" into STATUS, a commit message (`b4cc47e`) and the plan. The
  Task 5/6 implementer re-hashed, found its observation contradicted mine, refused
  the edit and flagged it. `b4cc47e`'s message still carries the wrong claim;
  commits are not amended, so this entry is the record.
- RETRACTED, my error: **I concluded Simulator.app had no window and recommended
  deleting its saved application state.** Both wrong.
  `CGWindowListCopyWindowInfo` finds the `iPhone 17` window at
  `(296,-1346,456,972)` -- inside the BetterDisplay virtual-display rect, i.e.
  parked off-screen the whole time. `System Events` reporting 0 windows is an AX
  blind spot for Simulator specifically. My control (ghostty reports 1 window)
  proved Accessibility *permission* works; it did not prove Simulator *exposes*
  windows through AX -- the wrong control for the claim (silent-failure rule 8).
  The saved-state directory I proposed deleting does not exist, so that repair
  would have been a no-op reported as a fix. Correct coordinates were then derived
  (device origin `(323.5,-1271)` at 1:1 point scale, Loops tab at `(610,-441)`) and
  `cliclick` still does not flip the tab, focused or not. Taps stay unavailable.
- Process note: **subagents corrected me five times on this branch** -- a
  non-existent second signing team, a fabricated xcodegen requirement for
  pre-existing files, the sha above, an unfounded worry that the drift test had
  stopped testing the real clip, and a test-count arithmetic conflict I had
  created with my own ruling. One earlier instance had already produced a false
  green (`TEST SUCCEEDED` with the file under test never compiled), which is why
  the plan now requires checking the suite COUNT rather than the exit code.

- CORRECTED, same night: **an earlier version of the entry above said the
  Analysis tab shows the "top loop span shaded". On a fresh launch it shades
  nothing.** `TimelineTabs.swift:5` declares `@State private var selectedLoop:
  LoopCandidate?` with no initial value and nothing assigns it on appear, and
  `ActivityChart` draws the span only `if let loop = selectedLoop`. The final
  reviewer caught the committed claim contradicting the code.
  The mechanism is worth recording because the reviewer guessed it wrong and the
  screenshots settle it: my 01:45 capture really does show filled yellow
  rectangles across all four lanes, and my 02:14 captures of the same build,
  after I relaunched the app, show none. The reviewer supposed I had mistaken a
  section `RuleMark` for the span; I had not. The earlier instance had been
  tapped by the Task 5/6 implementer, which set the selection, so I photographed
  a tapped state and described it as the launch state. A real observation of the
  wrong moment (silent-failure rule 7), not a misread mark.
  Being fixed by assigning `selectedLoop = analysis.loops.first` on appear, which
  makes the claim true rather than merely deleting it.
- Known limit, not a defect: **`LoopEngine.play()` schedules exactly 8 repeats**,
  inherited from the plan's own sample code rather than chosen. At this clip's
  ~8.2s window that is about 66 seconds, after which playback stops with no UI
  change. Tracked as its own decision rather than patched blind.
  - **Decided and shipped 2026-09-04: a loop runs until it is stopped.** The
    "no UI change" half of this was already stale when written -- the last
    segment's completion handler clears `playingID`, so the row does return to
    its play icon. See that date's entry for the scheduler.
- Recorded so it survives a `git clean`: **instrument activity diverges between
  macOS and iOS as well as section count.** Drum peaks 2.25x and bass 2.69x
  higher on iOS for identical bytes; vocal agrees within 4%. STATUS carries both
  sets of numbers in different entries but had never said they disagree, unlike
  the section-count split which it states outright. Because vocal is the one
  family that agrees, and vocal is what `clean` is computed from, loop-rank
  stability across the two platforms is an inference and not a measurement.
- Decided (Daniel, asked): **loop playback repeats until stopped, not 8 times.**
  Auditioning a loop ends when you stop it; 66 seconds was an arbitrary cliff
  inherited from the plan's sample code and never chosen. `LoopEngine.play`'s
  `repeats:` becomes `queued:` -- how many passes sit scheduled ahead of the
  playhead, default 4 -- and each pass's completion handler queues another,
  guarded by the same `playToken` that already stops a superseded play() from
  acting on a newer one. Hand-scheduling is unchanged, so the drift the
  `.loops` option accumulates is still avoided. `playingID` is now cleared only
  by `stop()`, because there is no natural completion left to report.
- The top-up is observed, not assumed, and the test carries its own control:
  `topsUpTheQueue` primes 2 passes, renders 6, and asserts the sixth is audible
  -- and first runs the identical call through the blocking `renderOffline`,
  where the MainActor top-up cannot get a turn, asserting the sixth pass is
  silent there. Without that half the test would pass just as happily against a
  player that scheduled everything up front. 33 tests in 4 suites.
- Shipped: **`catalog.py backfill-grid`, and the bar grid backfilled from 14
  tracks to 55 of 58.** The grid, structure boundaries and activity signal come
  from MusicUnderstanding alone -- `backfill` fills bpm/key from
  `analyze_track.py` and cannot touch them -- so 44 tracks were invisible to the
  region scorers. The new command runs `Tools/mu-analyze` for every track with
  a source file and no bars, ingests the JSON, and keeps it under
  `Samples/Analysis/` (gitignored, now 269 MB for 53 files). 40 tracks in 3m13s,
  no failures. The remaining 3 have no `source_path` -- `Let Em Know`, `demo`
  and `vocals`, artifacts of the filename-stem keying already in Known broken --
  so there is nothing to analyze, which is the correct outcome and not a gap.
- Two branches were written to fail loudly and both were observed failing, then
  the same command was observed passing on a real analysis (six assertions in
  `tests/test_catalog_ingest.py`, 24 passing): a missing `Tools/mu-analyze` is
  an error naming the `swiftc` line, never a quiet "0 tracks needed a grid" --
  the binary is gitignored, so absent is a fresh checkout's normal state; and an
  analysis that ingests cleanly but carries no rhythm block is reported as no
  bars rather than counted done. Found while writing them: a cached
  `Samples/Analysis` JSON is reused as-is, so a bad one stays bad until
  `--refresh`. Documented rather than fixed.
- Observed: **the macOS/iOS structure split is one boundary, and it is peak
  competition rather than the detection threshold.** `structurePredictions`
  exposes the raw per-frame curve behind each level (`sections`, `segments`,
  `phrases`; float32 base64, shape [1,600] at `predictionResolution` 0.05s for
  the 30s clip) alongside `detectionThreshold` 0.33. Decoding both platforms'
  curves for `testclip.m4a`:
  - The curves themselves diverge well past float rounding -- max |delta| 0.056
    on sections, 0.098 on segments, 0.176 on phrases, differing in ~598 of 600
    frames. This is the model producing different numbers per platform, not a
    different rule applied to the same numbers.
  - The entire structural difference is ONE boundary. macOS puts it at 10.131s,
    iOS at 12.199s. Segments and phrases substitute it, which is why their
    counts (5 and 9) matched and read as "identical everywhere" -- they are not.
    Sections drop it outright on iOS, which is the whole of 3 versus 2.
  - Both candidates clear the threshold on both platforms at segment and phrase
    level, and each platform emits exactly one, so the selection has a spacing
    rule beyond thresholding. The higher peak wins and the platforms rank the
    two oppositely, consistently across two independent levels: segments
    mac 0.648 vs 0.602 and iOS 0.616 vs 0.652; phrases mac 0.616 vs 0.582 and
    iOS 0.578 vs 0.620. Margins of 0.03-0.05 -- inside the divergence measured
    above, so the flip is fully explained by it.
  - `detectionThreshold` is NOT the knob, and the correlation runs backwards:
    the sections curve at the disputed boundary is 0.306 on macOS (under 0.33)
    and 0.335 on iOS (over), and it is macOS that emits the boundary. The
    section level plausibly requires a coinciding segment boundary -- iOS has
    none near 10.2s -- but that rule was not closed and is inference.
- Measured, not inferred: **what the split does to loop ranks.** Holding the
  macOS bars and activity fixed and swapping only the section set, `score_loops`
  at 4 bars gives 10 windows. Ranks 1-6 are identical in order and in score,
  the top pick included (bar 6, 14.270s, 0.4922). Ranks 7-10 reorder: bars 1, 2
  and 3 straddle macOS's 10.131s boundary and take the 0.75x penalty, but sit
  inside iOS's single 0-28.651s section and lose it, so they climb over bar 0.
  So on this clip the split moves the tail of the ranking and not the pick.
  Bounded deliberately: one clip, and it isolates the section variable only --
  iOS's own bars and vocal activity differ slightly on top of this.
- Consequence: **no code change.** A design change off n=1 would be premature,
  and the top pick is stable where it was measured. The standing instruction is
  unchanged: do not treat a loop ranking as platform-independent. The comment
  in `LoopScorerTests.swift` pinning the test's sections by hand is the guard.
- Method note, cost a run: **no iOS 27 simulator device existed on this Mac**,
  so `xcodebuild test` against any named simulator fails with a deployment-target
  mismatch against every iOS 26.5 device. Created `Flip-iOS27` (iPhone 17 Pro,
  iOS 27.0) and kept it; the 32 tests in 4 suites pass on it. Two iOS 27.0
  runtimes are installed (24A5355p and 24A5380i) and they share one runtime
  identifier, so `simctl create` cannot choose between them.

### 2026-09-03

- Observed: **both published artifacts are owned by the gmail account, whose
  subscription is temporary.** `~/.claude.json` and `~/.claude-work/.claude.json`
  both hold danieldecena10@gmail.com, uuid ffd06fee -- the same account and uuid,
  so the config files do not distinguish them at all and only the directory
  differs. That makes `ace836b3` (Flip Stem Map) and `c4d78867` (iOS Build
  Runbook) gmail-owned. A switch back to icloud is planned, which inverts which
  set of pointers resolves; eight other recorded pointers are already unreachable
  from gmail. Inventory kept by another session at
  `~/Archive/account-switch-20260903/NOTES.md`.
- Observed: **invariants check 36 cannot see an artifact that becomes
  unreachable.** It hashes a local file against a sha recorded at publish time
  and makes no network call, so a lapsed artifact and a healthy one are
  byte-identical from where it stands: `Artifacts/stem-map` will keep reading OK
  after the URL changes hands. This is the same blind direction the check already
  documents for "published ahead of local", widened to everything server-side.
  The artifact register is therefore not a safety net for the account switch.
  Not restamped or repointed ahead of the switch -- a binding recording a url the
  user cannot open is his call, not something to rewrite quietly.
- Corrected: an earlier reading here found `firing-audit: off` in
  `~/.claude/settings.json`. That was accurate when taken and is now false --
  `55ba939` added the override and `cf902f8` removed it mid-session, so the skill
  is live. A third session diagnosed the disagreement as this session having read
  `~/.claude-work/settings.json` instead; it had not, and two config files
  carrying the same key name is what made that cause plausible. The record is
  "the override was removed mid-session", and nothing in this session edited
  `settings.json`.

- Decided: **two sessions were editing `~/.claude/skills/ios-build/` at once.
  Tooling is owned; the runbook is not.** Corrected within the hour: an earlier
  version of this entry handed that session all of `~/.claude`, which was an
  overreach. The ios-build runbook is shared knowledge with no single owner --
  either session may hit an iOS lesson and must be able to write it the same
  turn rather than queue behind the other. What *is* owned is the tooling: that
  session builds the `invariants.sh` drift check, this one does not. This
  session owns `~/developer/music` and the Ivy Stem Map artifact.
  Five rules govern the shared page, agreed with that session: read the live
  artifact immediately before any republish; publish with the url recorded in
  `artifact.json`, never bare; move `SKILL.md` and `artifact.html` in one commit,
  because a lesson that lands only on the page never routes in a session;
  explicit pathspec on every `~/.claude` commit, never `-a`; and write a lesson
  up the same turn it is learned, because short-lived divergence is what keeps a
  shared page safe.
  - First move made here: dropped this session's watch on the iOS Build Runbook
    artifact, so their republishes no longer wake this session.
  - Their `sha256(artifact.html)` in `artifact.json`, compared by an
    `invariants.sh` check, is adopted as-is rather than competed with. Nothing
    on this machine currently compares an artifact's source against what is
    live, and one implementation of that is enough.
  - This also explains two anomalies recorded earlier today as unexplained:
    `artifact.html` changing size between an `ls` and a `cp` minutes later, and
    `published` reading 2026-09-02 in a `cat` but 2026-09-03 in git's base. Both
    were the other session writing to the same working tree. No content was
    lost either way: HEAD is `ec9cf0c`, all four additions are present exactly
    once, and that session synced to this one rather than over it.
  - Standing rules that held and stay: scoped pathspecs on every commit in a
    shared tree (the commit here was 3 files, 93 insertions, every line
    attributable), and re-read a shared file immediately before editing rather
    than from a copy read earlier in the session.

- Observed: **R4a is done on hardware.** Flip runs on the iPhone (iOS 27.0) and
  reports 116.596 BPM, 58 beats, 14 bars, C major against the bundled clip,
  matching `Tools/mu-analyze` on the Mac to rounding. Analysis took 1.4s on
  device for a 30s clip and produced 406,870 bytes of JSON. The framework runs
  on real hardware, which was the single biggest risk in the whole design.
- Observed: **the section-count split is macOS versus iOS, not Simulator versus
  device.** Identical bytes give 3 sections on macOS and 2 on both the iOS
  Simulator and the phone; segments (5) and phrases (9) are identical
  everywhere. `structurePredictions` carries a `detectionThreshold`, which is
  the likely knob. This matters because `score_loops` gives a containment bonus
  to a window that falls inside one section, so the phone and the Mac can rank
  the same track's loops differently. Not yet reconciled; do not treat a loop
  ranking as platform-independent until it is.
  - **Reconciled and partly corrected 2026-09-04** -- see that date's entry.
    Two claims here are wrong. Segments and phrases are identical in COUNT
    only; their boundary TIMES differ, which a count comparison cannot see.
    And `detectionThreshold` is not the knob: at the disputed boundary the
    sections curve reads 0.306 on macOS (under the 0.33 threshold) and 0.335
    on iOS (over it), yet macOS is the platform that emits the boundary.
- Confirmed: **MusicUnderstanding reports four instrument families and only
  four** -- `bass`, `drum`, `other`, `vocal` -- and that is the framework's
  fixed taxonomy, not a detection that happened to find four. `other` is the
  catch-all, and on the test clip it dominates (peak 0.821 against bass 0.127
  and drum 0.036), because guitar, keys, synths and strings all land there.
  Discrete `ranges` were emitted for `other` and `vocal` only, so the framework
  withholds them where it is not confident. For finer granularity the repo's own
  `separate_stems 6stem` (htdemucs_6s) splits guitar and piano out separately,
  which Apple does not.

- Decided: two tracks are combined by cutting both on the persisted bar grid,
  not by a BPM ratio. `Scripts/mix_render.py` (`449b195`) adds `layer` (both
  sides at once, per stem) and `transition` (A into B). The repo previously had
  no way to sound two sources together at all: grepping `amix`, `amerge`,
  `layer` and `overlay` across `Scripts/` and `lib/` returned nothing, and
  `mix_preview` only crossfades A then B at a section boundary. `stretch_for`
  measures how long n bars actually take in each track and folds B's bar count
  by octaves, so a double-tempo partner contributes twice the bars at no
  stretch. A BPM ratio would only be right if both tempos were constant, and
  Ivy alone runs 2.08s per bar early and 2.95s by the outro. Verified on audio,
  not exit codes: Ivy's bass and other under Nikes' vocals over bars 111-115
  rendered 11.859s against an 11.86s window, mean -18.3 dB, max -0.4 dB.
- Decided: `deconstruct()` now runs `apple_analyze` (`76be55b`), so a new track
  gets Apple's bar grid instead of only bpm/key from this repo's analyzer. Before
  this, 13 of 58 catalogued tracks were mixable and nothing said so until a mix
  was attempted. The three failure causes are kept distinct on purpose; an
  earlier draft collapsed a mistyped path, an unsupported format and an unbuilt
  binary into one "needs macOS 27" message, which reports a fabricated cause.
  Proven against a known-good input as well as bad ones: "01 Intro (Difference)"
  gained 40 bars, 5 sections, 7,356 activity points and 10 loop candidates.
- Observed: device signing is retired with no hardware attached.
  `build-for-testing` against `generic/platform=iOS` gives **TEST BUILD
  SUCCEEDED**, and the product carries `application-identifier`
  `877MLS29T9.com.danieldecena.flip`, `team-identifier` `877MLS29T9`, on a
  profile valid to 2027-09-02. This settles the OU-vs-CN question empirically:
  the build signs with `DEVELOPMENT_TEAM: 877MLS29T9` while the certificate's CN
  reads "Apple Development: Daniel Decena (FU9H8VF2PN)". R4a's remaining half is
  the phone.
- RETRACTED 2026-09-04: an earlier entry here claimed the plan's recorded sha for
  `App/Flip/Resources/testclip.m4a` was stale. **It was not.** The README and the
  plan record `1552377b9407a32754e56e85`, which is the file's SHA-**256**. I ran
  bare `shasum`, which defaults to SHA-**1** and returns
  `111194ee858465c6f01f940f`, compared the two, and reported a mismatch that never
  existed. Nothing was wrong with the README. Found by the Task 5/6 implementer,
  which verified the claim before acting on it and refused the edit — the
  silent-failure rule working from the other direction, against me.
  The reference readings stand and were independently re-derived from the shipping
  file: **116.597755 BPM, 58 beats, 14 bars, 3 sections, 5 segments, 9 phrases,
  C major**. Those are what the device must reproduce.
- Decided: build the flip toolkit's future around a **song database**, not a
  feature list. Apple's `MusicUnderstanding` (macOS/iOS 27) supplies rhythm, key,
  structure, loudness, pace and instrument activity on-device and free; loop
  finding, mixing two tracks, and social-clip extraction are all then *queries*
  over one `regions(track, kind, start_s, end_s, start_bar, n_bars, score)` table
  rather than three separate features. Design:
  `docs/superpowers/specs/2026-09-03-song-database-design.md`. Executable plan for
  Phases 0-2: `docs/superpowers/plans/2026-09-03-song-database.md`.
- **Phase 0 probe: the framework works, and the data is good.** `Tools/mu-analyze`
  compiled first try and ran on `02 Ivy.m4a` (249s). Observations, not inferences:
  - **Timing:** 57.4s warm, about 4.3x faster than realtime. The first run took
    6m38s at 4% CPU — that was one-time model provisioning, not analysis cost.
  - **Structure is bar-aligned.** 14 sections, 31 segments, 64 phrases. At the
    detected 113.0 BPM one bar is 2.12s, so 8 bars is 17.0s. Observed section
    lengths 16.5 / 16.7 / 16.2 / 16.5 / 16.5 (8 bars), 8.3 twice (4 bars), and
    32.9 / 30.9 / 35.0 (16 bars). Boundaries land on musical units.
  - **Instrument activity uses the demucs taxonomy:** `bass`, `drum`, `other`,
    `vocal`, as a continuous 0.0-1.0 signal sampled every 0.05s (20 Hz, 4984
    points). Consequence worth acting on: **finding** vocal-free regions needs no
    stem separation at all, only **extracting** an isolated stem does. That
    loosens the "Mac must run demucs first" constraint for the loop-hunting half.
  - **BPM 113.007** against a published 116 and our 118. Within
    `_bpm_class`'s 4.5% tolerance, so it scores exact. **Key `C major`** against
    a published `Am` — the relative, i.e. the right pitch-class set but the wrong
    tonic. On this one track our analyzer's `Am` is closer than Apple's. Apple's
    key detection is not automatically better; Phase 1 measures it properly.
- Gotchas recorded so they are not rediscovered:
  - `SessionResult` is `Encodable`, so the whole analysis serializes with a plain
    `JSONEncoder`. No hand-written mapping needed.
  - **Loudness reports `-inf` LUFS for digital silence and `JSONEncoder` throws
    `EncodingError.invalidValue` on it.** Fixed with
    `nonConformingFloatEncodingStrategy = .convertToString(...)`, so downstream
    consumers see either a number or the strings `"inf"` / `"-inf"` / `"nan"`.
  - **All times are `CMTime` encoded as `{epoch, flags, timescale, value}`,**
    timescale 44100. Seconds are `value / timescale`. Ingest must convert.
  - `result` carries an eighth key the docs do not list, `structurePredictions`,
    holding raw tensor output (`scalarType`, `scalars`, `shape`, `strides`) plus
    `detectionThreshold` and `predictionResolution`.
- Decided: **iOS ingest is not Files-import-only.** `MPMediaItem.assetURL`
  (MediaPlayer) yields a URL an `AVAsset` can read for the user's own library
  items; it is nil only for DRM-protected content. So the app can enumerate and
  analyze anything DRM-free the user owns. A paid Developer Program membership
  (team 877MLS29T9, confirmed via `Developer ID` + `Apple Distribution` certs)
  does **not** unlock decodable Apple Music audio — that boundary stands — but it
  does unlock MusicKit metadata, and ISRC gives a stable track identity that
  would properly fix the filename-stem collision recorded below.
- Sliced the work into a lettered roadmap in `TASKS.md` per
  `executor-review-roadmap`. Reconciliation worth recording: that skill wants
  roadmap lines to grow into compressed changelogs carrying SHAs and evidence,
  but this machine's `CLAUDE.md` says `TASKS.md` is titles only, under 60 chars
  and free of `.` and `#`, because `session-start.sh` truncates at the first
  period. CLAUDE.md wins, so the lettered structure and the `[code]`/`[you]` and
  behavior tags live in `TASKS.md` and the evidence lives here.
  - **R1 Analysis probe and measurement — DONE.** `Tools/mu-analyze.swift` plus
    `tests/test-mu-analyze.sh` (`555debc`, 3/3, and observed failing 0/3 with the
    binary absent). `tests/score_apple.py` plus 15 assertions (`cae6669`).
  - **R2 Song database: schema and ingest — DONE.** Schema `c37f02b`
    (`test_catalog_schema.py` 15/15, fails 10/15 without it; the live catalog
    upgraded with 58 tracks and 3923 assets unchanged). Ingest `4308a19`
    (`test_catalog_ingest.py` 14/14, fails 13/14 without it; all 13 fixture
    tracks loaded).
  - **R3 Region scorers — IN PROGRESS.** Unblocked for modern material: querying
    the live catalog for the quietest vocal bars in Ivy returns bars 110-117
    (227-248s), its instrumental outro. Not yet written.
  - **R7 stays `[you]`, and this is what was tried.** Whether structure holds up
    on old and lo-fi records cannot be settled here: all 56 files in the library
    are contemporary and well-produced. This is not an ear question, it is a
    missing-input question, and it needs such records in the crate first.
- **R3 loop scorer shipped.** `Scripts/regions.py` `score_loops` slides an
  n-bar window over the bar grid and scores each as (1 - mean vocal activity)
  times a section-containment multiplier; `catalog.py regions <track>` stores and
  ranks them. The continuous 0-1 activity signal is what makes this principled
  rather than hand-tuned -- mean vocal level over a span *is* its cleanliness.
  Levels are duration-weighted, because the activity rows are sample intervals
  and an unweighted mean would let a run of short rows outvote a long one.
  Verified on Ivy: the top eight candidates all land in the 218-249s outro at
  vocal 0.04-0.22 and bass 0.00-0.33, which is the sparse guitar section.
  `tests/test_regions.py` 9/9 and it fails to import without the module.
- **Apple's bar grid tracks the music, it is not a fixed ruler.** Ivy's bars run
  ~2.08s (115 BPM) through bar 109 and ~2.95s (81 BPM) from bar 110, because the
  outro genuinely slows. So "4 bars" is not a fixed duration, and a chop taken
  off this grid follows the performance rather than a click. Worth knowing before
  anyone "fixes" the apparent inconsistency.
- **MusicUnderstanding runs in the iOS 27 Simulator.** It does not need device
  ML hardware, which was an open risk. Flip (`App/`, xcodegen) installed and
  launched headlessly on a booted iOS 27.0 simulator and analyzed a bundled 30s
  clip in 2.27s against the Mac's 2.5s.
- **But macOS and the iOS Simulator disagree by one section.** Same clip, same
  bytes: BPM 116.597755 vs 116.596405, beats 58/58, bars 14/14, segments 5/5,
  phrases 9/9, key C major both. **Sections 3 on macOS, 2 in the Simulator.**
  Since segments and phrases are identical, boundary detection agrees and it is
  the section-grouping step that differs -- consistent with a prediction sitting
  on `structurePredictions.detectionThreshold` and falling the other way, nudged
  by the 0.0014 BPM difference. Consequence to design around: section
  containment feeds the loop scorer's bonus, so the Mac and the phone can rank
  the same track's loops differently. Whether the *device* matches macOS or the
  Simulator is untested -- the phone dropped off `devicectl` before the run.
- **Two corrections from the radio reference scripts** (`~/developer/radio/
  scripts/ios_run.sh`), which the `ios-build` skill points at and which had not
  been read:
  - A `generic/platform=iOS` build performs real device signing but produces
    **no installable product for a specific device**. The device build needs
    `-destination "id=<UDID>"`.
  - `Simulator.app` is not missing from this Xcode. **Xcode 27 replaced it with
    DeviceHub.app.** The cerebrum entry dated 2026-08-14 records this as a
    stripped install with the GUI absent from disk; that diagnosis is wrong.
- **The machine's slowness was Ollama, not the simulator.**
  `qwen2.5-coder:14b-32k` held 15 GB of 24 GB with 3.8 GB swapped;
  `ollama stop` took free memory from 13% to 70%. The whole simulator, 202
  processes, was 0.5 GB.
- **Escalation change on the two tempo tasks.** They were parked on the ear
  because every BPM source tried was Echo Nest-derived and therefore correlated.
  MusicUnderstanding is genuinely independent, and on all three suspect rows it
  agrees with our own analyzer and against the label: Nights 80.0 vs ours 80.2
  against a labelled 90, Nikes 69.0 vs ours 69.1 against 137, Rambo 92.9 vs ours
  89.7 against 181. Two uncorrelated detectors converging to within 0.2 BPM is
  the corroboration STATUS said was missing, so the ear is now an optional
  confirmation rather than a gate. Nights in particular has a mid-song beat
  switch, so a single BPM for the whole track is a malformed question and no
  detector will ever settle it.
- **Apple does not replace the analyzer, and should not.** On the 10 trusted
  labels both score 8 exact; ours has fewer octave errors (1 vs 2). They fail on
  different tracks -- Apple gets Self Control and Godspeed where ours reads a 2:1
  and a 3:2; ours gets Exchange and Pink + White where Apple halves and doubles.
  The follow-up worth building is an ensemble that prefers agreement, not a
  swap. Key: Apple 5/13 exact, 6/13 sharing the pitch-class set.
- Ruled out, so it is not re-investigated: `MediaIntelligence` looks apt because
  `HighlightAnalysisRequest` finds "the most engaging segments", but it is
  video-only with no audio path. `SoundAnalysis` is largely redundant with
  `instrumentActivity`.

### 2026-07-24
- Fixed: **mix preview crossfaded at fixed offsets, not real section boundaries.**
  `mix_preview.excerpt_start()` existed to pick a track's first section boundary
  (from `estimate_boundaries`) but `catalog.py`'s `_play_preview` never called it
  — it hardcoded 40s/30s start points instead. Noticed when asked whether the
  preview mixed at a lyric/beat transition point; it didn't. Added
  `_excerpt_start(path, bpm)` (lazy `analyze_track` import, matching
  `key_oracle.py`'s pattern since `catalog.py` stays numpy-free at module level)
  to decode each side, estimate boundaries, and feed both into `excerpt_start`.
  python-reviewer caught two real issues before commit: `bpm=None` would throw
  inside `estimate_boundaries` (guarded with `bpm or 0.0`), and the exception
  fallback silently swallowed failures (now prints a one-line diagnostic).
  Verified: both test suites still pass, live preview still renders. `618dc07`.
- Tried and REVERTED-IN-SPIRIT (code kept, hypothesis rejected): **subharmonic-
  summation chroma for detect_key.** `_chroma_projection` now also votes a
  bin's energy toward the pitch class of freq/3 and freq/5 (weights 0.5/0.35),
  on the theory that a fifth- or third-heavy harmonic spectrum (weak
  fundamental, common on bass/guitar) was piling votes onto the harmonic's
  own pitch class instead of the true tonic's — the standard HPCP mechanism
  for exactly the "wrong pitch class, not mode" error the oracle measured.
  Graded against `key_oracle.py score`: **no change** — still 1/10 exact,
  3/10 pitch-class match, 7/10 unrelated, identical per-track buckets to the
  pre-fix run (verified via `git stash`). 3 tracks' raw labels moved (Solo,
  Self Control: C->F; Godspeed: F->Dm) but none crossed into a correct
  bucket. All 21 `test-analysis.py` and 26 `test-chords.py` assertions still
  pass, so nothing regressed — left shipped since it's mechanistically sound
  and harmless, but it did not fix the measured problem on its own.
  - **Follow-up, same session: found and fixed the actual bug.** Suspecting the
    stem-blend weighting was a dead end — the oracle grades `detect_key` on
    the raw full-mix `.m4a` (fixtures column 0), which never goes through
    `analyze_stem_track` at all, so that theory couldn't apply. Instead:
    dumped the two full-mix chroma vectors that were miscalled (Solo, Self
    Control) and found them nearly FLAT (spread ~0.03-0.04 across all 12
    pitch classes) — the discriminating signal was already weak before any
    profile matching. More aggressive percussive-frame dropping (15% -> 70%)
    changed nothing, ruling out drum-transient smear. Tested pure white noise
    through `_chroma_vector` next: it resolved to a specific key (`D`) rather
    than a flat/arbitrary result, proving a content-independent bias baked
    into `_chroma_projection` itself, not the audio. Root cause: linear FFT
    bin spacing vs. logarithmic semitone spacing means low-range bins can
    span more than a semitone, and `np.rint(midi) % 12` rounds each such bin
    to one pitch class — which classes catch the extra bins is an accident
    of the 55-2000 Hz frequency grid (column totals ~16.2 for D/A vs. ~11.3
    for C#/D#). Fix: equalize `_chroma_projection`'s per-pitch-class column
    totals after the harmonic-vote step. Tested 4 variants against the
    oracle before shipping (baseline / harmonics-only / normalize-only /
    both): normalize-only reached 2/10 exact but only 3/10 pitch-class
    (same as baseline); harmonics+normalize together reached **4/10 exact,
    7/10 pitch-class** — the two fixes are synergistic, neither alone gets
    there. Shipped both. See the Known-broken entry above for the final
    per-track breakdown.
- Fixed: **`key_oracle.py score` was grading the wrong thing.** `_fixture_tracks`
  yielded fixtures-analysis.tsv **column 3** as "our_key" and `score` graded that
  against UG. But column 3 is the Echo Nest ground-truth reference (its header
  says so; `test-analysis.py` scores the live analyzer *against* it). So the
  oracle compared two reference label sets and never ran `detect_key` — the
  reported "4/10 exact, 6/10 share pitch-class, mode-flip on Ivy+Nights" measured
  Echo-Nest-vs-UG, not the analyzer. Caught by reproducing: live `detect_key`
  disagreed with column 3 on Nights (F vs Fm), Pink+White (Am vs A), Self Control
  (C vs G#). Fix: added `_analyzer_key(path)` (lazy `analyze_track` import, ""
  on missing/undecodable audio), and `score`/`fetch` now grade the live analyzer.
- Reframed: **the real key defect is pitch, not mode.** Live `detect_key` vs UG
  is **1/10 exact, 3/10 share the pitch-class set, 7/10 unrelated** — far worse
  than believed, and only Ivy + The Color Violet are relative flips. The planned
  relative-pair tie-break would touch ~2 tracks; the chroma/pitch stage is the
  larger problem. Next-Up + the key-detection Known-broken bullet + CLAUDE.md's
  key_oracle description all corrected. Direction on the pitch-stage rework is
  open — user chose "fix the oracle first" so the roadmap measures reality.

### 2026-07-23
- Shipped: **an independent key oracle, and it reframes the key problem.**
  `Scripts/key_oracle.py` grades `detect_key` against Ultimate Guitar tab
  tonalities — human transcriptions, wrong in different ways than the Echo Nest
  labels, which is the entire point. UG states `tonality_name` per tab, so no
  chord inference was needed. Result on the 13 fixtures: **10 covered, 4 exact, 2
  relative, 1 adjacent, 3 unrelated.** The headline is not 4/10 but **6/10 sharing
  the pitch-class set**: Ivy (Am vs C) and Nights (Fm vs Ab) are major/minor mode
  flips, not pitch errors. So "key detection is 2/13 exact" was always partly an
  artifact of grading against a correlated source — the real, narrower defect is
  which tonic of a correct pitch-class set gets called home. Three measured
  gotchas, each of which silently costs coverage: most user tabs leave tonality
  blank while `Official` (licensed) tabs fill it in and carry zero votes, so
  weight is `votes + 1`; UG files "Pink + White" as "Pink Plus White", so titles
  match on a variant set; and a cover band's tab can out-vote every real one, so
  rows must match artist AND title. `urllib` gets a 404 from UG's search where
  `curl` gets a 200, so the fetch shells out. Responses cache to
  `Samples/KeyLabels/` (gitignored) — a re-run is offline; labels are committed at
  `tests/fixtures-keys-ug.tsv`. Caveats: a tab's tonality can be a capo key, and
  coverage is partial (Don't, Rambo, SPEED DEMON have no stated tonality anywhere).
- Rejected on measurement: **Hooktheory TheoryTab**, despite being the better
  source on paper — human by-ear, key and mode stated, tabs for the fixture
  tracks. Its public dump (`owencm/hooktheory-data`) is a stale 375-song sample
  overlapping the fixtures **0/13**, and its live pages return 403, leaving only
  an account or a scrape. Ultimate Guitar needed neither and covered 10/13.
- Decided (user's call): **lyric similarity is a tie-break, not a lead signal.**
  `_sort_key` had `lyric_sim` above the tempo gap, so `--lyrics` reordered across
  tempo buckets and undid the tempo-first ranking decided hours earlier: seeding
  YUKON led with a 6-BPM pair while both 1-BPM straight beatmatches sat 4th and
  5th, won on words as generic as "make" and "tell". The gap now outranks it, and
  lyrics only reorder pairs already inside one whole-BPM bucket — where they still
  beat the key relation, since word overlap is at least measured off the actual
  text while the key is a 2/13-exact estimate. Live: `--seed YUKON --lyrics` now
  leads with the two 1-BPM pairs, tie-broken to '87 Stingray. Rejected: a
  similarity threshold above which lyrics could still outrank tempo — it needs a
  constant with no labelled data to pick it from.
- Decided (user's call): **the mix report ranks by tempo before key** (`483f45c`).
  `_sort_key` had key relation above tempo gap, so a 4-BPM/perfect-key pair
  outranked a 1-BPM/relative one — the report hedged every key claim with "confirm
  by ear" and then ranked by that same signal. Tempo now leads, bucketed to whole
  BPM (the report's own "straight beatmatch" threshold) so an inaudible 1.0-vs-0.8
  difference cannot override the key; inside a bucket key still decides. Rejected
  the weighted-score alternative as a bigger change than the evidence justifies.
  Seeding YUKON now leads with Skyline To, which is what the hand-written report
  the user liked had said all along.
- Fixed alongside it: **`why_line` claimed a rejected tempo was workable.** It
  assumed the tempo check had passed, so a key-only pair — one that check
  REJECTED — still rendered "35 BPM apart — inside pitch-fader range". Key-only
  pairs now say the gap is too far to beatmatch and to mix on the drums. Found by
  reading the live output after the ranking change, not by a test; the fixture
  pair in the suite was always tempo-compatible, so nothing exercised that branch.
- Fixed: **`scan`'s filename-stem collision now resolves by decodability, not by
  iteration order.** New pure `pick_source(candidates, probe)`; `scan()` groups
  source files by stem and returns the conflicts it resolved, which the CLI
  prints (`indexed` / `shadowed`). Two things the data changed about the fix:
  (1) The obvious rule — biggest file wins — is measurably an **anti-signal**.
  The corrupt `03 Exchange` is 12.0 MB and the good Deluxe copy is 6.7 MB, so a
  size rule picks exactly wrong on the only real collision in the library. I had
  it backwards initially from an `ls -l` whose arguments ls had re-sorted, and
  shipped a size rule that then picked the corrupt file on a live scan. Reading
  sizes per-path in Python is what caught it. Decodability (one ffprobe, only on
  a collision) is the honest discriminator; path breaks ties so a rescan is
  stable. (2) The earlier note claimed "the Deluxe album's other 17 tracks are
  indexed and the plain album's are shadowed" — wrong. The plain "album" holds a
  single stray file, and the library has **1 collision in 56 sources**. Scoped
  the fix to that. Keying tracks by album was rejected outright: `Stems/` and
  `Samples/` folders are named for the bare stem, so an album-qualified key
  orphans every derived asset. Live scan now indexes the Deluxe file and repairs
  the inconsistent `album` the earlier hand-repair left behind, so the manual fix
  is no longer needed. TDD, 6 new asserts.
- Shipped: **seed-pivot mix report** (`9fa69b9..8156cdd`, 8 commits). `catalog.py mix
  --seed <title>` pivots on one named track instead of dumping every library pair,
  printing a verdict, a why-line, rarest-first shared lyric words, and near misses;
  `--preview` renders a tempo-matched crossfade and plays it via `afplay`. Two
  deviations from the plan, both because the plan was wrong: `shared_words` dropped
  its `n_docs` parameter (sorting by raw document frequency is identical to sorting
  by IDF, so it was dead weight), and `atempo_ratio` folds into `[1/sqrt2, sqrt2]`
  rather than atempo's full `[0.5, 2.0]` — the planned version stretched a 128-vs-64
  pair by 2x when those tracks already lock and need no stretch. A test caught the
  latter. Also learned: ffmpeg's `wav muxer does not support more than one stream of
  type audio` is what an embedded mjpeg cover art looks like — Apple Music `.m4a`
  files carry one, so the preview needs `-vn`. The error text never says so.
- Decided: **the mix report leads with tempo and hedges key** (spec `9ce8728`,
  shipped `850f501`). Tempo is the reliable half of the analysis; key detection is
  2/13 exact. A verdict line that led with the key relation would project
  confidence the estimate has not earned, so the why-line states the BPM gap first
  and marks the key claim "confirm by ear". Revisit the wording if key accuracy
  improves — it is conservative phrasing, not a permanent verdict. Follow-on found
  at wrap-up and NOT fixed: `_sort_key` still ranks key above tempo, so the report
  hedges the key in prose while ordering by it. Filed in Known broken.
- Decided: **IDF replaced the lyric stopword list on measured evidence.** Over the
  repo's 56 `.lrc` files, ranking two songs' shared words by document frequency
  puts `speed` and `fast` (4/56 each) 2nd and 3rd for SPEED DEMON x Skyline To
  while `you`/`the`/`and` sink unaided — recovering mechanically the thematic
  observation that looked like it needed a language model. That result is why the
  report is deterministic rather than model-narrated. It also fixed a real
  mis-ordering: flat Jaccard scored the winning pair 0.040 against a worse pair's
  0.054, because a shared `you` counted as much as a shared `speed`. Measuring the
  hypothesis before designing on it is what turned a guess into the architecture.
- Resolved: **the catalog's stale bpm/key** (`132b5ce`). All 20 analyzed rows
  carried one timestamp predating every tempo/key change and held two distinct keys
  across 20 tracks, so `catalog.py mix`'s near-universal "perfect" key verdict was
  an artifact of a flat key distribution, not a real match. `backfill` could not
  repair it — it only filled rows where bpm/key were NULL, so it skipped all 20.
  Added `--refresh` to overwrite: 55 analyzed tracks (was 20), eight distinct keys
  (was two), cross-artist pairs where the output had been almost entirely
  same-album. Lesson: a fill-NULLs-only backfill silently freezes whatever the
  estimator believed the day each row was written.
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

Older entries: `STATUS-ARCHIVE.md`.
