# Flip — a song-understanding database, and the products built on it

## Context

`~/developer/music` is a zsh + Python toolkit for flipping samples. Its analysis
layer is its weakest part and STATUS says so at length: `detect_tempo` is 8/13
exact against published labels with two rows still blocked on Daniel's ear,
`detect_key` is 4/10 exact against the Ultimate Guitar oracle, and the chord and
section detectors are unverified.

Apple shipped `MusicUnderstanding` in the 27 cycle: rhythm (beats, bars, BPM),
key over time ranges, structure (sections, segments, phrases), loudness, pace,
and instrument activity. On-device, free, unlimited, from an `AVAsset`. Every
result type is `Codable`.

Daniel wants this to become an app, on his phone, eventually sold.

**The architecture follows from one observation of his:** the features are not
the product. A rich per-song database is the product, and every feature is a
query over it. Three he has named already:

| Product | The query underneath |
|---|---|
| Find a sample to flip | Bar-aligned regions ranked by cleanliness |
| Mix two songs perfectly | Compatible pairs, plus regions safe to cut on |
| Social-media snippet | The highest-energy bar-aligned 15 or 30 seconds |

All three are *ranked, musically-aligned spans of a track*. That is one engine,
one schema, three views. Building the datastore well means each new feature is a
query, not a rewrite.

**Verified on this machine, not assumed:**

- macOS 27.0 (26A5425a), Xcode 27 (27A5218g)
- `MusicUnderstanding.framework` present in both `iPhoneOS27.0.sdk` and
  `MacOSX27.0.sdk`
- iOS 27.0 simulator runtimes installed; **no physical iPhone connected**
- Paid Developer Program, team **877MLS29T9**. A second team `FU9H8VF2PN` exists
  on the icloud.com address; do not use it.
- iCloud Drive active

## Decisions taken

- **Audience:** beatmakers and sample flippers.
- **v1 scope:** import stems from the Mac, analyze, surface ranked loop
  candidates, audition them. No chopping, no export, no AUv3.
- **Money:** free to find, one-time IAP to export. No subscription. The Mac
  companion ships free or bundled.
- **Stem separation stays on the Mac.** demucs is PyTorch; a CoreML port is its
  own multi-week project with real risk on model size, memory, and speed.

## The risk that gates everything

The product thesis rests on two API outputs nobody has measured:
`StructureResult` and `InstrumentActivityResult`. If they are solid on the dusty
soul and funk records this audience actually samples, there is a product. If
they only work on modern, clearly-sectioned pop, what remains is a BPM detector
competing with free ones.

This is cheap to settle and **must be settled before any app code**. It is
Phase 0.

Second constraint, unfixable: the app cannot ingest DRM-protected Apple Music
or Spotify streams. `AVAsset` will not decode them and no entitlement changes
that, a paid Developer Program membership included. MusicKit plays catalog
content through a sealed player and never yields decodable audio.

**But ingest on iOS is better than Files-only import.** `MPMediaItem.assetURL`
(MediaPlayer) returns a URL an `AVAsset` can be built from, for items in the
user's own library. It is optional precisely because protected content returns
`nil`. So the app enumerates `MPMediaQuery.songs()`, analyzes every item whose
`assetURL` is non-nil — purchased, matched, imported, ripped — and marks the
rest unavailable. No sideloading required for the material this audience owns.

MusicKit is then useful for metadata rather than audio: catalog search, artwork,
genre, release date, and **ISRC, which gives a stable global track identity.**
That is the real fix for the filename-stem collision recorded in STATUS, where
two files sharing a name collapse into one row. Key on ISRC, fall back to a
ShazamKit signature for material not in the catalog.

## Data architecture

**Per-track JSON in the iCloud container is the durable record. SQLite is a
derived, rebuildable index.**

Not SQLite-in-iCloud: a single database file with concurrent Mac and phone
writers is a known corruption hazard. One JSON per track avoids write conflicts
by construction, stays portable and diffable, and matches the pattern
`catalog.py scan` already uses, where `assets` is rebuilt every run and the DB is
treated as derived.

### Schema

Extend `Scripts/catalog.py`'s existing `tracks` / `assets` / `runs`
(`Scripts/catalog.py:85-107`) rather than competing with them, so the Mac
pipeline keeps working throughout.

`tracks` gains: `duration_s`, `apple_bpm`, `apple_key`, `pace`,
`lufs_integrated`, `true_peak`, `analyzed_at`, `analysis_version`. Keeping the
existing `bpm` / `key` columns alongside the Apple ones is deliberate: Phase 1
compares them, and nothing is replaced before that comparison exists.

New time-series tables, one row per event, all keyed by track:

- `beats(track, idx, t, bar, beat_in_bar)`
- `bars(track, idx, t)`
- `sections(track, idx, label, start_s, end_s)`
- `key_ranges(track, idx, tonic, mode, start_s, end_s)`
- `loudness(track, t, momentary, short_term)`
- `instrument_activity(track, instrument, start_s, end_s, level)`
- `lyrics(track, start_s, end_s, text)` — from `SpeechTranscriber` over the
  vocals stem, not from `.lrc` files

`InstrumentActivityResult` carries both `activity`, a continuous 0.0-1.0 signal
per instrument, and `ranges`, discrete windows. The continuous signal is what
makes the loop ranker principled rather than heuristic: mean vocal activity over
a candidate span *is* its cleanliness score. `StructureResult` is a three-level
hierarchy, sections containing segments containing phrases, and phrase
boundaries are the natural loop cut points, finer than sections.

And the table the products are actually built on:

```
regions(track, kind, start_s, end_s, start_bar, n_bars, score, meta_json)
```

`kind` discriminates `loop` / `hook` / `clean` / `transition`. This is the
central design move: a loop candidate, a social-clip hook, a vocal-free span and
a safe cut point are all *a scored, musically-aligned span*. One table, one
ranker interface, three products. A fourth product is a new `kind` and a new
scorer, not a schema change.

Cross-track, backing the mixing feature:

```
pairs(a, b, tempo_ok, tempo_ratio, key_relation, score)
```

### Reuse, not reinvention

- `Scripts/harmonic_mix.py` already has `key_to_camelot:62`,
  `key_compatible:87`, `tempo_compatible:108`, `rank_pairs:169`. These populate
  `pairs` directly.
- `Scripts/mix_preview.py` already renders tempo-matched crossfades.
- `Scripts/catalog.py` already has `set-analysis`, `search`, `mix`, `backfill`
  subcommands to extend.
- `Scripts/sort_drums.py` already classifies one-shots for kit building.

## Other Apple frameworks worth using

All confirmed present in the installed `iPhoneOS27.0.sdk`.

| Framework | Use | When |
|---|---|---|
| `Speech` — `SpeechAnalyzer` + `SpeechTranscriber` (iOS 26+) | On-device timed transcription of the **vocals stem**. Replaces the `.lrc` dependency in `Scripts/lyrics.py`, and because it carries timestamps it aligns to the beat grid: lyric search across the crate, captions for social clips | Phase 2, feeds the `lyrics` table |
| `FoundationModels` | Natural-language crate search translated to a structured query over the database. On-device, free | After crate search exists |
| `ShazamKit` — `SHCustomCatalog` (iOS 15+) | Reference catalog built from your own audio. "Have I flipped this," identifying an unknown vinyl rip, and true dedupe by signature — which is a real fix for the filename-stem collision in STATUS, since signatures ignore filenames | Later |
| `MusicKit` | Metadata enrichment: artwork, genre, release year, and ISRC as a stable track key. DRM still blocks it as an audio source | Phase 2 |
| `MediaPlayer` — `MPMediaQuery` + `MPMediaItem.assetURL` | On-device ingest of the user's own library. `assetURL` is nil for protected content, non-nil for anything DRM-free | Phase 3 |

Checked and ruled out, recorded so it is not re-investigated: `MediaIntelligence`
looks apt because `HighlightAnalysisRequest` finds "the most engaging segments",
but it is **video-only** with no audio path. `SoundAnalysis` is largely redundant
with `instrumentActivity`.

## Phases

Each ends in an observation, never in the absence of an error.

### Phase 0 — Does the data justify the product

A macOS command-line tool built with `swiftc`, not an Xcode app: no project, no
signing, no simulator, and it runs against the real library immediately.

1. `Tools/mu-analyze.swift` — takes an audio path, runs
   `MusicUnderstandingSession(asset:).analyze(for:)` over all six types, writes
   the `Codable` result as JSON. `SessionResult` is `Encodable`, so this is a
   `JSONEncoder` call, not hand-written serialization.
2. Run it across a spread of Daniel's crate, deliberately including old and
   lo-fi material, not just clean modern tracks.
3. Read the structure and instrument-activity output against what the ear says.

**DoD:** a written verdict on whether structure and instrument activity are good
enough on real sampled material, backed by named tracks. If they are not, stop
and re-plan rather than building the app on top.

### Phase 1 — Measure it before trusting it

No analyzer in this repo is trusted on reputation, and Apple's gets the same
treatment.

- Run the Phase 0 tool over the 13 tracks in `tests/fixtures-analysis.tsv`.
- `tests/score_apple.py`, reusing the existing classifiers rather than writing
  new ones: `_bpm_class` (`tests/test-analysis.py:213`) and `verdict` /
  `harmonic_mix.key_compatible` (`Scripts/key_oracle.py:123`).

**DoD:** a three-way table, Apple vs ours vs label. Exact/octave/two-thirds
counts on the 10 trusted rows, exact/relative for key against
`tests/fixtures-keys-ug.tsv`, plus Apple's independent reading of Nikes and
Rambo. STATUS records that independent BPM sources were tried and exhausted;
this is a genuinely new one, uncorrelated with the Echo Nest-derived labels. It
is evidence, not a verdict over Daniel's ear.

### Phase 2 — The database

- Schema migration in `Scripts/catalog.py` for the tables above.
- Ingest: JSON from the Phase 0 tool into SQLite, idempotent and re-runnable.
- The first region scorer, `kind='loop'`: bar-aligned candidates ranked by
  instrument cleanliness and section membership.

**DoD:** `catalog.py regions <track> --kind loop` prints ranked candidates, and
spot-checking the top one by ear confirms it is a usable loop.

### Phase 3 — The app

SwiftUI, iOS 27, in `App/` inside the existing repo.

- iCloud Documents container; the Mac writes stems and analysis JSON into it.
- Library browser over the container.
- Track detail: beat and bar markers, sections, key over time, loudness,
  instrument activity, in Swift Charts.
- Loop candidates as a ranked list, tap to audition.

**DoD:** loop candidates for a real track, on the phone, audible.

### Later, each its own brainstorm

Chopping and export via AVFoundation with the one-time unlock. Crate search
(`every four-bar vocal-free loop 84-92 BPM in A minor`). The mixing view over
`pairs`. Social-clip export over `kind='hook'`. AUv3. demucs to CoreML, the only
thing standing between this design and a self-sufficient phone.

Note an unresolved tension to revisit, not now: social clips serve a different
audience than beatmakers. It is a fine second product; it is not a v1 feature.

## Mac-side change

One function in `lib/music-core.sh`: `publish_to_icloud()`, copying a finished
`Stems/<model>/<track>/` plus its analysis JSON into the ubiquity container,
called at the end of `deconstruct()`. Match the existing style there: absolute
`.venv/bin/python`, never `source activate`.

**Do not disturb** `deconstruct()` at `lib/music-core.sh:404`. It captures
`analyze_track`'s stdout and re-parses it with two `sed -nE` regexes (`:426`,
`:429`), so the exact format
`{name}:  {bpm} BPM   key {key}   transitions [...]` is a load-bearing contract,
not human-facing text. Nothing before Phase 2 replaces the Python analyzer, and
that decision waits on Phase 1's numbers.

## Verification

- Phase 0: read the JSON, compare structure boundaries against the ear on named
  tracks. A verdict with tracks named, not a pass/fail.
- Phase 1: `python3 tests/score_apple.py` prints the three-way table.
  Cross-check one track by hand against `T) Tempo lock` so the harness itself is
  trusted before its numbers are.
- Phase 2: `catalog.py regions` output auditioned by ear.
- Phase 3: run in the iOS 27 Simulator. If MusicUnderstanding returns empty
  there, it may need on-device models the Simulator lacks; say so and get a
  physical iPhone on iOS 27 rather than working around it.
- Regression throughout: `zsh tests/test-core.sh` and
  `python3 tests/test-analysis.py all` stay green. The shell pipeline keeps
  working while the app is built beside it.
- Signing: team 877MLS29T9. On "No Account for Team", the `ios-build` skill
  covers it.

## Open, not blocking

- App name. `Flip` is a placeholder.
- Whether the phone ever writes back into `Samples/`, or stays read-mostly with
  an explicit export. Decide when export is built.
