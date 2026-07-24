# Seed-pivot mix report — design

Date: 2026-07-23

## Problem

`catalog.py mix` ranks every compatible pair in the library and prints them as a
flat list. Two things are wrong with that for the way the tool actually gets used.

**It answers the wrong question.** The real query is seed-shaped — "which Frank
Ocean song would mix well with this Justin Bieber song?" — but the command takes
no seed. You get an arbitrary top slice of the whole catalog with no way to say
which track you want to play next. At 55 analyzed tracks that is 1,485 possible
pairs; the problem grows quadratically as the library does.

**It reports numbers where it should report reasons.** The shipped output gives a
tier, a key relation, a tempo delta and (optionally) a lyric similarity float. A
hand-written report over the same data proved markedly more useful because it
named one winner, explained in plain language *why* the pair works, listed the
actual shared lyric words instead of a score, and explained why an obvious
candidate was absent.

A third defect surfaced while designing this. `lyrics.py` fetches from LRCLIB and
caches under `Samples/Lyrics/`, but never reads the `.lrc` sidecar files that sit
next to the audio — 56 of them, shipped with the downloads and authoritative. The
feature goes to the network for lyrics already on disk.

## What this delivers

A deterministic, seed-pivoted report. No model in the loop; structured JSON is a
first-class output so a narration layer can be added later without touching the
core.

### Verified finding that shaped the design

The most valuable line in the hand-written report was a qualitative observation:
Bieber's `SPEED DEMON` and Frank Ocean's `Skyline To` are both about going fast.
That looked like it needed a language model.

It does not. Ranking the shared words by **inverse document frequency across the
library's own lyrics** surfaces it mechanically. Measured over 56 lyric files:

```
SPEED DEMON x Skyline To — shared words, rarest first:
  stronger     2/56 songs   idf 3.33
  speed        4/56 songs   idf 2.64
  fast         4/56 songs   idf 2.64
  than         8/56 songs   idf 1.95
  every       12/56 songs   idf 1.54
  call        15/56 songs   idf 1.32
  ...commonest of the shared: your, i'm, and, the, you
```

`speed` and `fast` land at #2 and #3. Function words sink on their own, so the
hand-maintained stopword list becomes unnecessary — the corpus decides what is
generic. This is why the design is deterministic rather than model-narrated: the
gap between the two is much smaller than it appeared.

The same measurement exposes a scoring bug. Flat Jaccard scored the *winning*
pair 0.040 and a worse pair 0.054, because common words count as much as rare
ones. IDF weighting corrects the ordering.

## Components

### 1. CLI surface — `Scripts/catalog.py`

`mix` gains `--seed <query>`. The query fuzzy-resolves against catalog names
through the existing `_search_rows`, then every other analyzed track is ranked
against that one track.

- Omitting `--seed` keeps today's library-wide behavior byte-for-byte.
- `--json`, `--limit`, `--tempo-tol`, `--lyrics` continue to apply.
- Seed matches nothing → message naming the query, exit 1.
- Seed matches more than one → list the candidates, exit 1. No guessing.

Wrapper and menu follow the established split: the core function lives in
`lib/music-core.sh`, the wrapper only prompts. No logic in a wrapper.

### 2. Lyric sourcing — `Scripts/lyrics.py`

New `local_lyrics(source_path)`: look for a `.lrc` beside the audio file, strip
`[mm:ss.xx]` timestamps, return the text or `None`.

`fetch_lyrics` consults it before the cache and before the network. Faster, works
offline, and covers tracks LRCLIB does not have. Keeps the module's existing
contract: every failure path returns `None` and never raises.

### 3. Word ranking — `Scripts/lyrics.py`

- `word_index(docs)` → `{word: document_frequency}` over every lyric the catalog
  can see, plus the document count.
- `shared_words(a, b, index, limit)` → the overlap, rarest first, each with its
  document frequency.
- `lyric_similarity` becomes IDF-weighted rather than flat Jaccard.

This retires `_STOPWORDS` and `theme_signature`'s `top_n` cutoff. Words shorter
than three characters are still dropped; everything else is decided by frequency.

### 4. Report renderer — `Scripts/mix_report.py` (new)

A separate module so `catalog.py` does not grow another display concern. Given a
seed and ranked pairs it emits:

- **Verdict line** — names one winner.
- **Why line** — leads with tempo, because tempo is the trustworthy half of the
  analysis: `"0.7 BPM apart — straight beatmatch, no pitch-fader work"`. Key
  follows as supporting evidence, explicitly hedged: `"keys read as relative
  major/minor (confirm by ear)"`. Key detection scores 2/13 exact against
  published labels, so a report that led with it would project confidence the
  data does not support.
- **Shared words** — rarest first, with the tie-in that made them worth printing.
- **Near-miss section** — for a seed with no tempo match, say so plainly and name
  what it would pair with if pitched, rather than silently returning nothing.
  `--limit` caps the ranked list only; near-misses are capped at 3 regardless, so
  a low limit never hides the explanation for an empty result.

### 5. JSON output

Mirrors the text exactly: verdict, the parts of the why-line as separate fields,
shared words with their document frequencies, and near-misses. A future
`--narrate` consumer reads this; the core never learns about narration.

### 6. Tests — `tests/test-mix-report.py` (new)

Hand-rolled `check()` assertions matching the repo's existing style. All pure
functions — no network, no audio decode, no database.

- IDF ranking over a synthetic corpus, including that a word appearing in every
  document ranks last.
- `.lrc` timestamp stripping, including a file with no timestamps.
- Seed resolution: exact hit, fuzzy hit, no match, ambiguous match.
- Near-miss selection when no pair clears the tempo tolerance.
- Renderer output against a fixed pair, asserting the tempo fact precedes the key
  claim and that the key claim carries its hedge.

## Out of scope

Named so they do not creep in:

- Set or tracklist chaining (a path search over pairs — a separate project).
- The `--narrate` layer.
- Any change to `rank_pairs`' tier logic or the Camelot compatibility rules.
- Fixing key-detection accuracy. Tracked separately; this design works around it
  by how it words the report, not by improving the estimate.

## Risks

- **Key relations remain unreliable.** The report's hedging makes this visible
  rather than fixing it. If key accuracy improves later, the hedge should be
  revisited — it is deliberately conservative wording, not a permanent verdict.
- **IDF over a small corpus is noisy.** 56 documents is few; a word appearing in
  2 songs versus 4 is not a strong distinction. It is good enough to sort the
  overlap, and should not be presented as a confidence score.
- **Lyric coverage is uneven.** Tracks with no `.lrc` and no LRCLIB entry produce
  no shared words. The report must say the lyrics were unavailable rather than
  implying the songs share no vocabulary.
