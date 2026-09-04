# Mix engine — design

## Context

`catalog.py mix` already ranks compatible pairs and renders a preview, and it
works. But it approximates in a way that caps how good it can get, and the song
database built this week removes the reason it had to.

**What exists** (`Scripts/harmonic_mix.py`, `mix_preview.py`, `mix_report.py`,
`lyrics.py`, `catalog.py cmd_mix`): Camelot key compatibility, octave-folding
tempo compatibility, a deliberate ranking order that puts tempo first because
key detection is the weak half, IDF-weighted shared-lyric scoring, and a
20-second `acrossfade` preview with one `atempo` ratio applied to track B.

**What caps it, and what this design fixes:**

1. **No downbeat alignment.** `mix_preview.preview_args` starts each track at a
   section boundary and crossfades. The bars do not coincide, so the result
   blends but does not lock. This is the single biggest gap and the database now
   holds a persisted bar grid that closes it.
2. **`pairs` is declared and never written.** `catalog.py:145` carries the
   comment "populated from `harmonic_mix.rank_pairs`"; a repo-wide grep finds
   zero statements against it. Rankings exist in memory for one invocation.
3. **`regions(kind='transition')` has no scorer.** `Scripts/regions.py` says so
   itself: it implements `loop` only. `compute_regions` passes `--kind` through
   as a label on loop-scored rows, which is worse than not supporting it.
4. **Preview boundaries come from the old detector.** `catalog._excerpt_start`
   calls `analyze_track.estimate_boundaries` live, per preview, and discards the
   result. Meanwhile `sections` and `bars` sit populated in the database from
   Apple's analysis, unused by the mix path.
5. **The `lyrics` table is orphaned.** Ingest writes timed rows from
   `SpeechTranscriber`-ready analysis; `lyrics.py` reads `.lrc` sidecars, a cache
   directory, then LRCLIB over the network, and never the table.

## The idea

**A mix is two cut points and an alignment.** Everything else is ranking and
rendering. Stating it that way makes the two modes one feature:

| | DJ transition | Mashup |
|---|---|---|
| Sources | two full tracks | A's vocal stem, B's instrumental |
| Cut points | exit A, enter B | where A's vocal starts, where B's loop starts |
| Alignment | downbeats coincide | downbeats coincide |
| Ranking | identical | identical |

So one compatibility engine, one cut-point scorer, one aligner, two renderers.

## Scope

Both modes, per the decision taken. Ranking selectable by axis (tempo, key or
lyrics), manual pairing as well as ranked suggestions, and a stem view. Export
of tempo-matched stems is in scope; the in-app audible preview is the primary
output.

## Design

### 1. Downbeat alignment — the piece that makes it "perfect"

`bars(track, idx, t)` is persisted per track from Apple's analysis. To align:

- Pick a cut bar in A (`a_bar`) and an entry bar in B (`b_bar`).
- Stretch B by `atempo_ratio(a_bpm, b_bpm)`, reusing
  `mix_preview.atempo_ratio:22` unchanged — it already folds to the octave
  nearest no stretch and stays inside ffmpeg's `[0.5, 2.0]`.
- Offset B so `bars[b_bar] * ratio` lands exactly on `bars[a_bar]`.

The existing preview does step two and skips steps one and three. Adding them is
arithmetic over a table that already exists.

**Caveat to design around, not ignore:** Apple's bar grid tracks tempo rather
than laying a fixed ruler. On Ivy, bars run 2.08s through bar 109 and 2.95s
after, because the outro slows. A single `atempo` ratio cannot hold alignment
across a tempo change, so alignment is guaranteed only within a
constant-tempo stretch. The cut-point scorer must therefore prefer bars whose
local spacing is stable, and the design records that a 20-second preview is
short enough for this to hold in practice.

### 2. Cut points — `regions(kind='transition')`

A new scorer in `Scripts/regions.py`, alongside `score_loops`, reusing the same
`(beats, bars, sections, activity)` input quadruple and returning the same shape,
so `compute_regions` needs only a dispatch on `kind`.

A bar is a good place to cut when:

- it starts a section (`sections` where `label='section'`), because that is where
  the music itself changes;
- vocal activity is low around it, from the continuous `instrument_activity`
  signal — mixing over a vocal is what makes a blend sound wrong;
- drum activity is present, since the drums are what a listener locks onto;
- local bar spacing is stable, per the caveat above.

Score is the product of those terms, mirroring `score_loops`' shape so the two
are legible side by side. `STRADDLE_PENALTY` has no analogue here and is not
reused.

### 3. `pairs` gets written

`compute_pairs(con, tol)` runs `rank_pairs` over every track with a bpm and key
and persists the result, extending the declared columns:

```
pairs(a, b, tempo_ok, tempo_ratio, key_relation, score,
      tier, tempo_gap, half_double, lyric_sim,
      a_cut_bar, b_cut_bar, mode)
```

Two reasons this stops being optional. The phone cannot recompute rankings over
a library it does not hold in full, and manual pairing needs to answer "how do
these two go together" for a pair no ranking surfaced.

`rank_pairs` itself is unchanged. Its ordering is deliberate and pinned by
`tests/test-harmonic-mix.py`: tier, then tempo gap bucketed to whole BPM, then
lyric similarity, then key relation — with tempo leading precisely because key
detection is weak. **Selectable ranking axis re-sorts the stored rows; it does
not touch `_sort_key`.**

### 4. Ranking by axis

Three orderings over the same stored pairs:

- **beats** — the existing `_sort_key`, unchanged, as the default
- **key** — `key_relation` first, then tempo gap
- **lyrics** — `lyric_sim` first, tempo gap as tie-break

Only the default carries the reasoning already argued in `harmonic_mix.py:139`.
The other two are user overrides and the UI should say so rather than implying
all three are equally sound.

### 5. Lyrics: read the table

`lyrics.py` gains a source ahead of the sidecar: the `lyrics` table, when the
track has rows. Ordering stays cheapest-and-most-local-first, and the network
call stays last. This also gives the mix path **timed** lyrics for the first
time, so a future version can cut where a vocal phrase starts rather than where
a section does.

### 6. Seeing the music and the stems

The stem view needs no separated audio. `instrument_activity` holds a continuous
0-1 level for `bass`, `drum`, `other` and `vocal` at 20 Hz, which draws directly
as four lanes:

- x axis is the bar grid from `bars`, not wall-clock seconds, so the picture is
  musical
- section boundaries as vertical rules from `sections`
- loop and transition candidates as shaded spans from `regions`
- the four activity lanes stacked, so "where do the vocals stop" is visible at a
  glance

This is the feature that makes the analysis legible instead of numerical, and it
is pure SwiftUI over Swift Charts against data already in the database. Where
real stem audio exists (the Mac's `Stems/` folder, 69 assets today) a lane
becomes playable; where it does not, the lane still draws.

### 7. Rendering

`mix_preview.preview_args` gains explicit `a_start`/`b_start` derived from the
chosen bars rather than from `excerpt_start`'s heuristic, and keeps everything
else — including the load-bearing `-vn`, which exists because Apple Music `.m4a`
files carry an embedded cover-art stream that breaks the wav muxer.

Mashup mode maps each side to a stem path instead of the source, and replaces
`acrossfade` with `amix`, since layering a vocal over an instrumental is not a
crossfade. Both modes share the alignment and the ratio.

## What this does not do

- No pitch correction beyond what `atempo` gives. Key-shifting to force
  compatibility is a different feature.
- No alignment across a tempo change, per the caveat in section 1.
- No stem separation on the phone. Mashup previews need stems the Mac produced.

## Verification

- Alignment, measured not eyeballed: render a preview of a track against itself
  offset by a known number of bars; the aligned output must be phase-coherent,
  and a deliberately misaligned control must not be. A rendering that sounds
  fine is not evidence until the misaligned control sounds worse.
- Cut points by ear: top-scored transition bars for a known track should land on
  section changes; check three.
- `pairs`: row count equals `rank_pairs` output length for the same tolerance,
  and re-running replaces rather than appends.
- Regression: `tests/test-harmonic-mix.py` and `tests/test-mix-report.py` pin
  the ranking order, the `why_line` wording and the preview arguments. All of it
  must stay green — this design adds paths, it does not alter the existing one.
