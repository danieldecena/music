## Tasks

## Completed

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

<!-- resume-footer -->
---
Plan approved 2026-07-21 12:48.

Sessions start in "plan" (permissions.defaultMode in
~/.claude/settings.json). Bypass is reachable in the Shift+Tab cycle only
when launched via `cb` (--allow-dangerously-skip-permissions); `yolo`
(--dangerously-skip-permissions) starts in bypass outright.

Only if Claude Code actually closed:

    claude --resume eb6d96e7-7e28-4cf0-af52-1f9c4f3ccbca

(`-c` resumes the most recent session; bare `--resume` opens a searchable picker.)
<!-- /resume-footer -->
