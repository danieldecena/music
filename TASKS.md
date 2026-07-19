## Tasks

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
Plan approved 2026-07-18 18:11.

Sessions start in "plan" (permissions.defaultMode in
~/.claude/settings.json). Bypass is reachable in the Shift+Tab cycle only
when launched via `cb` (--allow-dangerously-skip-permissions); `yolo`
(--dangerously-skip-permissions) starts in bypass outright.

Only if Claude Code actually closed:

    claude --resume 761b2ae4-c2a9-4630-af88-852938028d8c

(`-c` resumes the most recent session; bare `--resume` opens a searchable picker.)
<!-- /resume-footer -->
