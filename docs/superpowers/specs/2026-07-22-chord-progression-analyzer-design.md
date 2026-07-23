# Chord-progression analyzer — design

Date: 2026-07-22

## Purpose

Estimate a bar-by-bar chord progression for a track (or a Stems folder), so a
flip can be charted and replayed without transcribing by ear. Builds directly on
the chroma, tempo, and key machinery already in `Scripts/analyze_track.py`.

Estimates only — chroma-based labeling, not a transcription oracle. Same honesty
caveat as tempo/key: it is a strong starting chart, not ground truth.

## Scope

In scope:
- One chord label per bar, over the whole track, at the detected tempo's bar grid.
- Chord vocabulary: major triad, minor triad, dominant 7th, major 7th, minor 7th
  in all 12 roots (60 templates total).
- A soft diatonic prior from the detected key.
- A printed chart plus a `chords.txt` written beside the track.
- Stem-folder aware (chords read from bass+other, matching how key is read).

Out of scope (YAGNI):
- 9ths, sus, dim, aug, half-dim, slash chords, inversions.
- Downbeat / pickup detection — bar 0 is assumed to be the downbeat, same
  assumption `_pick_boundaries` already makes.
- Catalog persistence of the progression.
- Per-section (rather than per-bar) reporting.

## Architecture

New `Scripts/chords.py`, a standalone module invoked via `.venv/bin/python`
(needs numpy, like the other analysis scripts). It **imports from**
`analyze_track.py` rather than copying DSP:

- `decode_mono(path, sr)` — decode
- `SR`, `FRAME` — sample rate / FFT size constants
- `spectra(audio) -> Spec` — one spectral pass (`mag`, `flux`, `fps`, `n_frames`)
- `detect_tempo(sp) -> float` — BPM
- `detect_key(sp) -> str` — key label (e.g. `"Am"`, `"F"`)
- `_KEEP`, `_PROJ` — the 55-2000 Hz bin mask and (n_bins, 12) pitch-class
  projection matrix
- `stem_track_dir(p)` — detect a Stems track folder and return its stem paths

Wired the codebase's standard core/wrapper way:
- `chord_progression(file_or_folder)` in `lib/music-core.sh` — non-interactive,
  activates `.venv` and calls `Scripts/chords.py` (mirrors `analyze_track`).
- `chords.sh` — thin interactive wrapper that prompts for input then calls
  `chord_progression` (mirrors `analyze-stems.sh`).
- A menu entry in `music` (a `C) Chords` entry, current-track aware via the
  existing `resolve_stems`/current-track helper the `A) Analyze stems` entry uses).

Input resolution mirrors `analyze_track` / `analyze_stems`:
- A Stems track folder → use bass + other stems (the harmonic stems), summed,
  for chroma. Fall back to whatever stems exist.
- A single audio file → use it directly.

## Per-bar chroma

Reuse the exact per-bar recipe from `_beat_features`, extracted so both callers
agree:

1. `period = fps * 60 / bpm` (frames per beat); bar period = `period * 4`.
2. `n = int(n_frames / bar_period)` bars. If `n < 2`, bail (too short to chart).
   Cap bars the way `_beat_features` caps beats so a pathological tempo cannot
   blow up memory.
3. For each bar `[a, b)`: `chroma = log1p(mag[a:b, _KEEP]).mean(axis=0) @ _PROJ`,
   then L1-normalize.

This yields one (12,) chroma vector per bar. Using `log1p` + averaging matches
the percussive-smear defenses already justified in `_chroma_vector`.

Note: bar period uses 4 beats/bar (4/4 assumed). Non-4/4 is out of scope and
would mislabel bar boundaries — acceptable, the whole toolkit assumes 4/4 for
the bar grid already (see `_pick_boundaries`).

## Chord matching

60 binary chord templates, each a 12-vector with 1.0 on member pitch classes:

- Triads: root, +4 or +3 (major/minor third), +7 (fifth).
- Dominant 7th: major triad + 10 (minor seventh).
- Major 7th: major triad + 11.
- Minor 7th: minor triad + 10.

Built once at module load by rolling a base shape across all 12 roots, exactly
like `_key_profiles` builds the 24 key profiles. Store templates z-scored and a
parallel `names` list (`"C"`, `"Cm"`, `"C7"`, `"Cmaj7"`, `"Cm7"`, ...).

Per bar: z-score the bar chroma (skip if `std == 0` → label `"—"`), dot against
all 60 templates in one `(60,12) @ (12,)`, take argmax. This is the same
z-score-makes-Pearson-a-dot-product trick as `_key_from_chroma`.

## Soft diatonic prior

From the detected key, compute its 7 diatonic triads/7ths (the chords built on
each scale degree). Concretely, for a major key the diatonic seventh chords are
`I maj7, ii m7, iii m7, IV maj7, V 7, vi m7, vii...` — reduce to the labels in
our 60-name vocabulary that fall in-key (their triad-or-7th form). For a minor
key, the natural-minor diatonic set.

Add a small fixed bonus `PRIOR` to the score of each in-key template before
argmax. `PRIOR` is tuned so:
- an ambiguous bar (two templates within noise) resolves to the in-key one, but
- a bar whose chroma clearly supports an out-of-key chord (borrowed chord,
  secondary dominant) still wins on chroma alone.

Start at `PRIOR = 0.5 * (per-bar score std)` and settle by the synthetic test
below; expose it as a module constant so it is one line to retune. If
`detect_key` returns `"unknown"`, skip the prior entirely (pure template match).

## Output

Printed chart, 4 bars per line, key + BPM header, repeats collapsed to a
mid-dot so the eye tracks changes:

```
Chords — 02 Let Em' Know
key Am · 92 BPM · 48 bars

  1 | Am7   ·     ·     ·     |
  5 | Dm7   ·     ·     ·     |
  9 | Fmaj7 ·     G     ·     |
 13 | Am7   ·     ·     ·     |
 ...
```

- Leading number = starting bar of the line (1-indexed).
- `·` = same chord as the previous bar (a held chord).
- `—` = a bar with no confident chord (silent / all-percussion bar).

Also write `chords.txt` beside the track (in the Stems track folder for a
folder input, next to the file for a file input), containing the same header and
the full bar list one per line (`bar<TAB>chord`), read-only — no re-encode, same
contract as `analysis.txt` from `analyze_stems`.

## Error handling

- Tempo unknown / `bpm <= 0` → cannot form a bar grid → print
  `"chord analysis failed: no tempo"` and **exit non-zero** (matching the
  `analyze_track.py` exit-code contract shipped 2026-07-22, so callers that gate
  on exit code are not fooled).
- Fewer than 2 bars of audio → same failure path.
- A bar with `std == 0` chroma → label `"—"`, not a crash (does not fail the run).
- `detect_key` unknown → skip the diatonic prior, still produce a chart.

## Testing

`tests/test-chords.py`, hand-rolled synthetic assertions in the style of
`tests/test-analysis.py`:

1. **Triad recovery** — render a bar of additive sine partials for a known
   major triad (e.g. C-E-G) and assert the labeler returns `"C"`; repeat for a
   minor triad and each 7th type.
2. **Root coverage** — assert a rolled triad (D major) returns `"D"`, so the
   template-rolling is correct across roots, not just at C.
3. **Prior discrimination** — construct one genuinely ambiguous bar (two
   templates within noise) in a known key and assert the in-key label wins;
   construct one clear out-of-key bar and assert the prior does **not** override
   it. This is the test that keeps `PRIOR` honest.
4. **Failure exit code** — a `subprocess` test (like the analyze `exitcode`
   test) that feeds a tempo-less / too-short input and asserts a non-zero exit.

Synthetic-only. Real-track accuracy is a by-ear question, out of scope for the
automated suite — the chart is an estimate, stated as such in the output.

## Files touched

- `Scripts/chords.py` — new.
- `lib/music-core.sh` — add `chord_progression()`.
- `chords.sh` — new wrapper.
- `music` — add the `C) Chords` menu entry.
- `tests/test-chords.py` — new.
- (No change to `analyze_track.py` beyond being imported — the per-bar chroma
  recipe may be lifted into a small shared helper there if the import is cleaner
  as a function than as duplicated inline math; decide during implementation, but
  do not duplicate the chroma math.)
