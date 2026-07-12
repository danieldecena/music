# Per-stem analysis — design

**Date:** 2026-07-12
**Status:** Approved (autonomous defaults under `/goal finish all todos`), pending implementation plan
**Predecessor:** stem separation quality profiles (shipped, commit 014bad9)

## Problem

After `separate_stems` runs — especially the new `hq`/`6stem` profiles that add
`guitar.wav`/`piano.wav` — some stems come out effectively empty (the track had no
piano, or demucs found nothing to isolate). Nothing surfaces this: the user has to open
each stem in a DAW to learn that `piano.wav` is silence, and the chop steps happily slice
empty stems into empty one-shots. There is no at-a-glance "which stems actually contain
audio, and how loud" readout.

## Goal

After separation, report per-stem **presence** and **loudness** so empty/faint stems are
obvious, printed to the terminal and saved beside the stems. Wire it into the menu (Tools),
a standalone wrapper, and the end of `deconstruct`.

## Design

### 1. Metric — ffmpeg `volumedetect`

No new Python deps. `ffmpeg -i <stem> -af volumedetect -f null -` prints
`mean_volume: <N> dB` and `max_volume: <N> dB` on stderr. Parse both. This matches the
codebase's existing reliance on ffmpeg (chop.py silencedetect, chop_stems segmenting).

### 2. Presence classification — pure helper

Add `stem_presence_label <mean_dbfs> <max_dbfs>` to `lib/music-core.sh` (a pure,
testable arg-mapping helper in the same style as `stem_profile_args`):

| Condition | Label |
|---|---|
| `max_volume < -50` dB | `silent` |
| else `mean_volume < -45` dB | `faint` |
| else | `present` |

Rationale from real data: htdemucs_6s `piano.wav` on a pianoless track measured
mean -77.3 / max -26.2 dB -> `faint` (transients but essentially empty); `vocals.wav`
measured mean -23.5 / max -1.7 dB -> `present`. Float comparison via `awk` (zsh has no
native float `<`). Thresholds are constants in the helper; no config knob (YAGNI).

### 3. Core function — `analyze_stems <track_folder_or_stem>`

Mirrors `chop_stems`' input handling (a `Stems/<model>/<track>` folder, or a single
`.wav`). For each `*.wav` stem: run volumedetect, parse mean/max, classify, and both
print an aligned table and write it to `<track_folder>/analysis.txt`. The `.wav` glob
never matches `analysis.txt`, so re-runs are safe. Prints the report path to stderr.

Table shape:

```
stem         mean     peak  presence
vocals    -23.5 dB  -1.7 dB  present
piano     -77.3 dB -26.2 dB  faint
drums      -8.2 dB  -0.4 dB  present
```

### 4. Wiring

- **New wrapper `analyze-stems.sh`** — thin interactive shell (drag a Stems track folder)
  over `analyze_stems`, matching `stems.sh`/`download.sh`.
- **Menu Tools group** — add `A) Analyze stems (loudness/presence)`; the `A|a)` case arm
  uses the existing `resolve_stems` resolver (current-track aware, falls back to a dragged
  path), so a picked library track analyzes with one keypress.
- **`deconstruct`** — after the separation step, call `analyze_stems "$stemdir"` so every
  deconstructed track gets an `analysis.txt` automatically.

### 5. Testing

- `tests/test-core.sh`: assert `stem_presence_label` for each band —
  `(-30, -2) -> present`, `(-77.3, -26.2) -> faint`, `(-60, -55) -> silent`, and a
  boundary (`max = -50` exactly is not `< -50`, so `-46 -50 -> faint`).
- Manual: run `A` on a real `Stems/htdemucs_6s/<track>` folder; confirm the table prints,
  `analysis.txt` is written beside the stems, and faint stems (guitar/piano on a track
  lacking them) are labeled `faint`/`silent`.

## Out of scope (YAGNI / later)

- **Catalog columns for per-stem loudness.** `catalog.py scan` rebuilds the `assets` table
  every run, so per-asset loudness would be recomputed or lost each scan — real complexity
  for little gain over the beside-stems `analysis.txt`. Deferred; revisit if a digest ever
  needs it.
- Integrated LUFS / true loudness normalization (ffmpeg `ebur128`) — mean/peak dBFS is
  enough to flag empty stems. No normalization or gain changes; analysis is read-only.
- Per-stem spectral/onset stats, key/BPM per stem.
- Configurable thresholds.

## Affected files

- `lib/music-core.sh` — add `stem_presence_label` + `analyze_stems`; call `analyze_stems`
  at the end of `deconstruct`.
- `music` — add the `A)` Tools line + `A|a)` case arm.
- `analyze-stems.sh` — new wrapper.
- `tests/test-core.sh` — add `stem_presence_label` assertions.
