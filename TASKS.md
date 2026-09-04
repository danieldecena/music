## Tasks

- [ ] (you) Amend silent-failure rule 10 in place, vs the byte budget
- [ ] Tempo lock by ear on Nikes and Rambo (optional confirm now)
- [ ] Re-record replay baseline after the tempo question settles
- [ ] (you) Install Flip on the phone and read BPM/bars/lyrics off it
- [ ] Library browser over the iCloud container (R5 remainder)

## Roadmap — song database

Tags: [code] I can move it, [you] needs you. B = behavior-preserving,
C = changes behavior. Evidence and SHAs live in STATUS's decision log.

- [x] (R1) Analysis probe and measurement [code] C
- [x] (R2) Song database: schema and ingest [code] C
- [x] (R3) Region scorers over the beat grid [code] C
- [x] (R4a) Flip on device, analyzing a bundled track [you] C
- [ ] (R4b) Register the iCloud container in Xcode, then mirror it to project.yml [you] C
- [ ] (R5) The iOS app: browse, charts, loop candidates [code] C
- [ ] (R6) Downstream ports: chopping, lyrics, kit [code] C
- [ ] (R7) Verdict on old and lo-fi material [you] B

## Completed

- [x] (R4b) iCloud container and publish_to_icloud -- Mac half, 6bac72d
- [x] Decide whether loop playback should repeat past 8 iterations -- 3d06275
- [x] Backfill the bar grid for the 44 tracks without one -- 5bdb181
- [x] Reconcile the macOS/iOS section-count split before trusting loop ranks -- fc8f6cf
- [x] Repoint the design canvas row from ace836b3 to c5d0c33b -- paper-system 3cf3622
- [x] Add tests/score_apple reusing existing classifiers -- cae6669
- [x] Three-way table Apple vs ours vs label -- cae6669
- [x] Extend catalog schema: time-series + regions tables -- c37f02b
- [x] Scaffold Flip iOS app (Xcode 27, iOS 27 target) -- eda7938
- [x] Build Tools/mu-analyze.swift, dump full analysis JSON -- 4209e42
- [x] Verify analysis runs in the iOS 27 Simulator -- 692f964
- [x] Batch-analyze the 13 fixture tracks to JSON -- cae6669
- [x] Track detail charts in Swift Charts -- eb423b8
- [x] Lyrics and loops tabs with bar-accurate playback -- eb423b8
- [x] Loop region scorer over the beat grid -- e5ed1ae

- [x] Fix key_oracle to grade live detect_key vs UG, not Echo Nest column 3
- [x] Independent key oracle (key_oracle.py) — grade detect_key off Ultimate Guitar
- [x] Demote --lyrics to a tie-break inside the tempo bucket in _sort_key

- [x] Mix report: rank tempo before key; fix key-only pair's false tempo claim — 483f45c

- [x] Fix scan's filename-stem track collision (decodability, not size) — aa868ce

- [x] Seed-pivot mix report: .lrc lyrics, IDF word ranking, preview, TDD — d42d7da

- [x] Re-index catalog bpm/key via backfill --refresh, clean song titles — 132b5ce

- [x] Fix the Exchange 3:2 misread by searching the grid's lag, not just phase — 4300a1d

- [x] click_compare: auto-write locked BPM to fixtures + rerun score, TDD — 149a7aa

- [x] Harden build.py live import: verify window + track-count before claiming success — logic-pro-mcp 1aa52b9

- [x] Confirm restarting the MCP server clears the empty tempo read — fresh server returns bpm 120.0 via transport
- [x] Type-a-title fuzzy track input at prompts (find_track.py + core resolver, TDD)
- [x] Fix build.py File>Import menu path (real ellipsis + verified nesting), TDD — logic-pro-mcp babbad8
- [x] Click-comparator to settle tempos by ear (Scripts/click_compare.py + menu/wrapper/core, TDD)
- [x] Repair logic_get_tempo/key entire-contents timeout — scoped Control Bar reads, TDD — logic-pro-mcp c56acf3

- [x] Smart Tempo spike + probe: off-screen Logic drivable, control mapped, tempo readable — but Logic can't report a single BPM for a full song (File Tempo 0.00). Feature ruled out; findings in logic-pro-mcp/docs/smart-tempo-probe.md
- [x] Harmonic mix-match finder (harmonic_mix.py + catalog mix + lyrics.py + wiring, TDD) — 1b0e978
- [x] Fix H) Chords crash on non-stem folders (no_vocals.wav route, else clean error) — 9802370
- [x] Chord-progression analyzer (Scripts/chords.py + menu/wrapper/core, TDD)
- [x] Make analyze_track.py exit non-zero on analysis failure
- [x] Add exit-code test to tests/test-analysis.py (TDD, subprocess)
- [x] Enable rust-analyzer-lsp per-project (music-menu, StudioTUI)

- [x] Test music-menu pure fns (sh_quote shell round-trip, build fns, short_label, display_val)
- [x] Scaffold music-menu ratatui crate (Cargo.toml, main event loop)
- [x] Ratatui Design theme.rs (brand navy/cream, yellow reversed-video select)
- [x] steps.rs: flip-path catalog + source/stem/one-shots discovery
- [x] worker.rs: run_zsh (stdin-null) + sh_quote, adapted from StudioTUI
- [x] app.rs: filter, selection, input-collection state, run lifecycle
- [x] ui.rs: two-pane layout + input forms in the design language
- [x] Build warning-free + tmux smoke test; README

- [x] Add download_and_locate helper to lib/music-core.sh
- [x] Auto-select downloaded track (music arm 1) + select_file helper
- [x] Make Deconstruct and Download accept a pasted URL
- [x] Guide dead-end errors and handle blank Enter in the menu
- [x] Fix Logic launch app name + fail-fast (config.py, build.py)

- [x] Fix BPM decimal truncation in music-core.sh deconstruct()
- [x] Add tests/record_baseline.py and commit the frozen baseline TSV
- [x] Add tests/test-analysis.py asserting the baseline reproduces exactly
- [x] Refactor analyze_track.py to a single spectral pass (Spec dataclass)
- [x] Fix tempo octave errors via harmonic scoring, prior, and grid support
      (shipped as best-of-three measured variants: exact 5->6, octave 2->1,
      at the cost of 3:2 errors 1->3. Refinement without scoring was WORSE
      than the original. Revisit once tapped labels exist.)
- [x] Detect Stems track folders and analyze them as one track
- [x] Vectorize chroma and reduce percussive smear in detect_key
- [x] Replace section boundaries with beat-synchronous SSM + checkerboard novelty
- [x] Collect ~10 ground-truth BPM/key labels into tests/fixtures-analysis.tsv
      (13 labels via the chosen published-BPM lookup; provenance documented,
      3 suspect rows flagged `?` and excluded from strict scoring. Labels are
      Echo Nest-derived and therefore correlated, not independent — recorded
      in STATUS.md. Optional tap-tempo refinement tracked there, not here.)
- [x] Add scoring mode comparing new vs baseline accuracy
- [x] Add synthetic unit tests for octave logic, key, and stem-folder detection
- [x] Cut 3:2 tempo errors via triple-grid penalty in _grid_support
      (3:2 errors 3->2, exact 6->7; dropping the 3x harmonic term was tried
      and reverted as redundant. Not yet settled by ear.)

<!-- resume-footer -->
---
Plan approved 2026-09-03 21:45.

Sessions start in "plan" (permissions.defaultMode in
~/.claude/settings.json). Bypass is reachable in the Shift+Tab cycle only
when launched via `cb` (--allow-dangerously-skip-permissions); `yolo`
(--dangerously-skip-permissions) starts in bypass outright.

Only if Claude Code actually closed:

    claude --resume 8cc1b1a3-989d-40ee-a8e4-d7a12bfc0048

(`-c` resumes the most recent session; bare `--resume` opens a searchable picker.)
<!-- /resume-footer -->
