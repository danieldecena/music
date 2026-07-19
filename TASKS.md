## Tasks

- [x] Fix BPM decimal truncation in music-core.sh deconstruct()
- [x] Add tests/record_baseline.py and commit the frozen baseline TSV
- [x] Add tests/test-analysis.py asserting the baseline reproduces exactly
- [x] Refactor analyze_track.py to a single spectral pass (Spec dataclass)
- [ ] Fix tempo octave errors via harmonic scoring, prior, and grid support
- [x] Detect Stems track folders and analyze them as one track
- [x] Vectorize chroma and reduce percussive smear in detect_key
- [x] Replace section boundaries with beat-synchronous SSM + checkerboard novelty
- [ ] Collect ~10 ground-truth BPM/key labels into tests/fixtures-analysis.tsv
- [ ] Add scoring mode comparing new vs baseline accuracy
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
