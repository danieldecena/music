# Separation quality profiles — design

**Date:** 2026-07-12
**Status:** Approved, pending implementation plan
**Follow-on spec:** per-stem analysis (presence/loudness report) — separate spec, built after this.

## Problem

`separate_stems` exposes three modes (`instrumental`, `4stem`, `6stem`) mapped to demucs
args by `stem_mode_args` (`lib/music-core.sh:7`). All run the fast base `htdemucs` model at
default settings. The user wants **cleaner stems, especially isolated guitar and piano**,
and is willing to trade runtime for quality.

Key facts that constrain the design:
- **Guitar and piano stems only exist in the 6-stem model** (`htdemucs_6s`). The
  higher-quality fine-tuned model (`htdemucs_ft`) is 4-stem only and cannot produce them,
  so it is NOT useful for this goal and is excluded.
- Separation cleanliness on any model improves with `--shifts N` (test-time augmentation)
  and higher `--overlap`, at roughly linear runtime cost. On `htdemucs_6s` this is the
  lever that cleans up the otherwise-weak guitar/piano stems.

## Goal

Replace the three raw modes with a small set of **quality profiles** at the Separate
prompt, defaulting to the cleanest 6-stem output, so guitar/piano come out by default and
as clean as the toolchain allows.

## Design

### 1. Profiles

| Profile key | demucs args | Model dir | Stems | Speed | Use |
|---|---|---|---|---|---|
| `acapella` | `--two-stems=vocals` | `htdemucs` | 2 | fast | vocal / instrumental only |
| `fast` | *(none)* | `htdemucs` | 4 | 1× | quick audition |
| `6stem` | `-n htdemucs_6s` | `htdemucs_6s` | 6 | ~1× | guitar/piano, normal |
| `hq` *(default)* | `-n htdemucs_6s --shifts 2 --overlap 0.5` | `htdemucs_6s` | 6 | ~3–4× | keeper tracks, cleanest guitar/piano |

`acapella` and `fast` preserve today's `instrumental` and `4stem` behavior verbatim (same
demucs args, same output dir) — they are renames for a consistent profile vocabulary, not
behavior changes. `6stem` equals today's `6stem`. `hq` is new.

### 2. Mapping functions (replace `stem_mode_args`)

Add to `lib/music-core.sh`, replacing `stem_mode_args`:

- `stem_profile_args <profile>` — echoes the demucs args for a profile (the middle column),
  `return 1` on an unknown profile.
- `stem_profile_model <profile>` — echoes the output model directory name (`htdemucs` or
  `htdemucs_6s`) for a profile.

`separate_stems` uses both: it runs `demucs ${=args} --out "$out" "$file"` and derives the
vocals path from `stem_profile_model` instead of the current inline
`model_dir=htdemucs; [[ "$mode" == 6stem ]] && model_dir=htdemucs_6s` block
(`lib/music-core.sh:107-108`).

Because `hq` and `6stem` both write to `Stems/htdemucs_6s/`, the existing `stems_dir_for`
(`lib/music-core.sh:33`) and the current-track integration continue to work unchanged.

### 3. Menu wiring

- **Separate (menu `2)`)**: replace the current `Mode: 1) instrumental 2) 4stem 3) 6stem`
  prompt with a profile prompt:
  ```
  Quality: 1) fast (4-stem)  2) 6-stem  3) 6-stem HQ [recommended, slow]  4) acapella
  ```
  Default (empty input) = `hq`. Map the numeric choice to a profile key and pass it to
  `separate_stems`.
- **Deconstruct (menu `8)` / `deconstruct()`):** stays on the `fast` profile
  (4-stem, `htdemucs`) — it is the one-command quick-prep path and hardcodes
  `Stems/htdemucs/$track` (`lib/music-core.sh:240`). Making it slow-by-default would
  surprise. Profile choice for keeper tracks lives in Separate. `deconstruct()` passes
  `fast` explicitly where it currently passes `4stem` (`lib/music-core.sh:244`). (A future
  spec may let deconstruct take a profile and derive `stemdir` from `stem_profile_model`;
  out of scope here.)

### 4. Runtime expectation

The `hq` profile is ~3–4× slower than `fast`. The Separate prompt labels it `slow` so the
cost is visible at the point of choice. No progress bar work in this spec (demucs prints
its own progress to stderr).

## Out of scope (YAGNI / later specs)

- **Per-stem analysis** (presence/silence, loudness) — the announced follow-on spec.
- `htdemucs_ft` and any 4-stem quality tier — excluded; can't produce guitar/piano.
- HPSS / heuristic splitting of `other` into harmonic/percussive — not pursued.
- Per-stem key/BPM.
- Recording the profile/quality in the catalog for plain Separate runs (catalog is only
  updated on `deconstruct`, which stays `fast`; unchanged here).
- Any change to `deconstruct`'s profile.

## Affected files

- `lib/music-core.sh` — replace `stem_mode_args` with `stem_profile_args` +
  `stem_profile_model`; update `separate_stems` model-dir derivation; update `deconstruct`
  to pass `fast`.
- `music` — rewrite the `2)` arm's mode prompt into the profile prompt; map choices to
  profile keys.
- `tests/test-core.sh` — replace the three `stem_mode_args` assertions with
  `stem_profile_args` + `stem_profile_model` assertions covering all four profiles and the
  unknown-profile error.

## Testing

- `tests/test-core.sh`: assert `stem_profile_args`/`stem_profile_model` for each of
  `acapella`, `fast`, `6stem`, `hq`, plus an unknown key returning non-zero.
- Manual: run Separate on a short track with `fast` and confirm `Stems/htdemucs/<t>/` has 4
  stems; run `6stem`/`hq` and confirm `Stems/htdemucs_6s/<t>/` has 6 stems including
  `guitar.wav` and `piano.wav`; confirm the current-track flow (pick in `L`, then Split
  drums) still resolves stems for a `hq`-separated track.
