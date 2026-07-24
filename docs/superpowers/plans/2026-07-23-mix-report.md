# Seed-Pivot Mix Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `catalog.py mix` from a flat library-wide pair dump into a seed-pivoted report that names one winner, explains why in plain language, lists the rarest shared lyric words, explains near-misses, and can render the pair as a tempo-matched audio preview.

**Architecture:** Three new pure modules plus targeted edits to two existing ones. `lyrics.py` gains local `.lrc` reading and IDF word ranking (retiring its hand-maintained stopword list). `mix_report.py` renders text and JSON from ranked pairs. `mix_preview.py` builds an ffmpeg command and plays the result. `catalog.py` gains `--seed`/`--preview` and delegates all rendering. Every new function is pure and testable except two thin subprocess wrappers.

**Tech Stack:** Python 3.14 (stdlib only for these modules — no numpy, no third-party), sqlite3, ffmpeg + afplay via subprocess, zsh wrappers.

## Global Constraints

- **Stdlib only** in `lyrics.py`, `mix_report.py`, `mix_preview.py`. These join `chop.py`, `catalog.py`, `find_track.py` as the stdlib-only scripts; do not import numpy.
- **Python** is `/opt/homebrew/bin/python3`; project scripts run via `.venv/bin/python` from the repo root.
- **Tests** are hand-rolled `check(cond, label)` assertions in the style of `tests/test-harmonic-mix.py`. No pytest, no framework. Run with `.venv/bin/python tests/<file>.py`.
- **Lint** with `/opt/homebrew/bin/ruff check` and `/opt/homebrew/bin/ruff format --check`. Pre-commit hooks run ruff and ruff-format; never pass `--no-verify`.
- **No emoji** anywhere — code, comments, output, commit messages. Use ASCII (`->`, `[ok]`, `[x]`).
- **Commits** use imperative subject lines, explain reasoning in the body, and end with:
  `Co-Authored-By: Claude <noreply@anthropic.com>`
- **Core/wrapper split:** all non-interactive logic goes in `lib/music-core.sh`; `*.sh` wrappers only prompt and call a core function. Never duplicate logic into a wrapper.
- **Comment discipline:** comment only to explain non-obvious reasoning, never to restate what the code does.
- **Degrade-safe:** every lyric path returns `None`/`0.0` on failure and never raises. This is `lyrics.py`'s existing contract and must hold.
- `--limit` caps the ranked list only; near-misses are capped at 3 regardless.

## Existing interfaces this plan binds to

Copied verbatim so no task has to go looking:

```python
# Scripts/harmonic_mix.py
key_to_camelot(key: str | None) -> str | None
key_compatible(k1: str | None, k2: str | None) -> str | None   # 'perfect'|'relative'|'adjacent'|None
tempo_compatible(b1: float, b2: float, tol: float = 0.06) -> tuple[bool, bool]   # (ok, is_half_double)
rank_pairs(tracks: list[dict], tol: float = 0.06) -> list[dict]
# each pair dict: {"a": trackdict, "b": trackdict, "tier": "strong"|"key-only"|"tempo-only",
#                  "key_rel": str|None, "tempo_gap": float, "half_double": bool, "lyric_sim": float|None}
# each trackdict has at least: name, artist, bpm, key

# Scripts/catalog.py
song_title(name) -> str            # '1-01 SPEED DEMON' -> 'SPEED DEMON'
_search_rows(con, query) -> list[dict]
# row keys: name, source_path, artist, album, bpm, key, model, deconstructed_at, stems/kit/...

# Scripts/lyrics.py
ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "Samples" / "Lyrics"
_WORD = re.compile(r"[a-z']+")
fetch_lyrics(artist: str | None, title: str, timeout: float = 5.0) -> str | None
theme_signature(text: str | None, top_n: int = 40) -> set[str]
lyric_similarity(a: str | None, b: str | None) -> float
```

## File Structure

| File | Responsibility |
|---|---|
| `Scripts/lyrics.py` (modify) | Lyric sourcing + word statistics. Gains `.lrc` reading and the IDF index; loses `_STOPWORDS`. |
| `Scripts/mix_report.py` (create) | Render ranked pairs to text and to a JSON-ready dict. No I/O, no DB. |
| `Scripts/mix_preview.py` (create) | Build the ffmpeg command, render, play. Only two functions touch subprocess. |
| `Scripts/catalog.py` (modify) | Seed resolution + CLI wiring. Delegates all rendering. |
| `lib/music-core.sh` (modify) | `mix_report()` core function. |
| `mix-report.sh` (create) | Interactive wrapper: prompt for a seed, call the core function. |
| `music` (modify) | Menu entry. |
| `tests/test-mix-report.py` (create) | All new pure functions. |
| `tests/test-harmonic-mix.py` (modify) | Extend for the changed `lyric_similarity`. |

---

### Task 1: Read lyrics from `.lrc` sidecars

**Files:**
- Modify: `Scripts/lyrics.py`
- Test: `tests/test-mix-report.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `strip_lrc(text: str) -> str`, `local_lyrics(source_path: str | Path | None) -> str | None`, and `fetch_lyrics(artist, title, timeout=5.0, source_path=None)` with the new trailing parameter.

- [ ] **Step 1: Write the failing test**

Create `tests/test-mix-report.py`:

```python
#!/usr/bin/env python3
"""
Tests for the seed-pivot mix report -- lyric sourcing, IDF word ranking, the
report renderer, and the preview command builder. Hand-rolled assertions in the
style of tests/test-harmonic-mix.py. Pure stdlib; run with any python3:

    python3 tests/test-mix-report.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import lyrics as ly  # noqa: E402

_passed = 0
_failed = 0


def check(cond: bool, label: str) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        print(f"FAIL: {label}")


LRC = """[ar:Justin Bieber]
[ti:SPEED DEMON]
[00:12.34]And I go speed racing
[00:14.50]Speed demon, speed demon
[00:16.00]
[01:02.5]Faster than the rest
"""

plain = ly.strip_lrc(LRC)
check("speed racing" in plain, "strip_lrc keeps the lyric text")
check("[00:12.34]" not in plain, "strip_lrc removes timestamps")
check("[ar:" not in plain and "Justin Bieber" not in plain, "strip_lrc drops metadata lines")
check("" not in plain.splitlines(), "strip_lrc drops blank lines")
check(len(plain.splitlines()) == 3, f"strip_lrc keeps 3 lyric lines, got {plain.splitlines()}")

# A file with no timestamps at all is already plain text -- pass it through.
check(ly.strip_lrc("just a line\nand another") == "just a line\nand another",
      "strip_lrc passes through untimestamped text")
check(ly.strip_lrc("") == "", "strip_lrc handles empty input")

# local_lyrics: reads the sidecar beside the audio file, None when absent.
check(ly.local_lyrics(None) is None, "local_lyrics(None) is None")
check(ly.local_lyrics("Apple Music/Nope/Does Not Exist.m4a") is None,
      "local_lyrics returns None for a missing sidecar")

print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python tests/test-mix-report.py`
Expected: FAIL — `AttributeError: module 'lyrics' has no attribute 'strip_lrc'`

- [ ] **Step 3: Write minimal implementation**

In `Scripts/lyrics.py`, add after the `_WORD` definition:

```python
# An .lrc line is either a metadata tag ([ar:...], [ti:...]) or a timestamped
# lyric line. Timestamps can carry 2 or 3 decimal places depending on the source.
_LRC_TS = re.compile(r"\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]")
_LRC_META = re.compile(r"^\[[a-z]+:[^\]]*\]$", re.IGNORECASE)


def strip_lrc(text: str) -> str:
    """Plain lyric text from .lrc content: metadata lines and timestamps removed."""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if _LRC_META.match(line):
            continue
        line = _LRC_TS.sub("", line).strip()
        if line:
            out.append(line)
    return "\n".join(out)


def local_lyrics(source_path) -> str | None:
    """Lyrics from a .lrc sidecar beside the audio file, or None.

    Apple Music downloads ship these, so they beat both the cache and the
    network: authoritative, offline, and present for tracks LRCLIB lacks.
    """
    if not source_path:
        return None
    p = Path(source_path)
    if not p.is_absolute():
        p = ROOT / p
    try:
        lrc = p.with_suffix(".lrc")
        if lrc.is_file():
            return strip_lrc(lrc.read_text(encoding="utf-8", errors="ignore")).strip() or None
    except OSError:
        pass
    return None
```

Then change `fetch_lyrics`'s signature and prepend the local check:

```python
def fetch_lyrics(
    artist: str | None, title: str, timeout: float = 5.0, source_path=None
) -> str | None:
    """Plain lyrics for a track, or None. Prefers a .lrc sidecar, then a
    cached/hand-dropped file; otherwise queries LRCLIB once and caches the
    result. Never raises."""
    local = local_lyrics(source_path)
    if local:
        return local

    cache = CACHE_DIR / f"{_slug(title)}.txt"
```

(the rest of the function body is unchanged)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python tests/test-mix-report.py`
Expected: `9 passed, 0 failed`

Also confirm nothing regressed: `.venv/bin/python tests/test-harmonic-mix.py`
Expected: `45 passed, 0 failed`

- [ ] **Step 5: Lint**

Run: `/opt/homebrew/bin/ruff check Scripts/lyrics.py tests/test-mix-report.py && /opt/homebrew/bin/ruff format Scripts/lyrics.py tests/test-mix-report.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add Scripts/lyrics.py tests/test-mix-report.py
git commit -m "lyrics: read .lrc sidecars before the cache and the network

56 .lrc files ship beside the Apple Music downloads and were being ignored --
the mix feature went to LRCLIB for lyrics already on disk. Sidecars are
authoritative, work offline, and cover tracks LRCLIB does not have.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Rank shared words by rarity, retire the stopword list

**Files:**
- Modify: `Scripts/lyrics.py`
- Modify: `tests/test-mix-report.py`

**Interfaces:**
- Consumes: `strip_lrc`, `local_lyrics` from Task 1.
- Produces: `doc_words(text) -> set[str]`, `word_index(docs) -> tuple[dict[str, int], int]`, `shared_words(a, b, df, n_docs, limit=8) -> list[tuple[str, int]]`, and `lyric_similarity(a, b, df=None, n_docs=0) -> float`.

**Why this replaces the stopword list:** measured over the repo's own 56 lyric files, ranking the words two songs share by document frequency puts `speed` (4/56) and `fast` (4/56) at positions 2 and 3, while `you`, `the`, `and`, `i'm` fall to the bottom on their own. The corpus decides what is generic, so a hand-maintained list is dead weight. The same measurement showed flat Jaccard scoring the winning pair 0.040 below a worse pair at 0.054 — IDF weighting fixes that ordering.

- [ ] **Step 1: Write the failing test**

Append to `tests/test-mix-report.py`, before the final `print`:

```python
# --- IDF word ranking -------------------------------------------------------

DOCS = [
    "speed racing faster than the rest you know",
    "the speed boat and you",
    "love you baby the",
    "love the night you",
    "hello the you",
]
df, n = ly.word_index(DOCS)
check(n == 5, f"word_index counts 5 documents, got {n}")
check(df["the"] == 5, f"'the' appears in every doc, got {df.get('the')}")
check(df["speed"] == 2, f"'speed' appears in 2 docs, got {df.get('speed')}")
check("of" not in df, "words under 3 chars are dropped")

# Shared words come back rarest-first, so a word appearing everywhere sorts last.
sw = ly.shared_words(DOCS[0], DOCS[1], df, n)
words = [w for w, _ in sw]
check(words[0] == "speed", f"rarest shared word first, got {words}")
check(words[-1] == "the", f"commonest shared word last, got {words}")
check(all(isinstance(c, int) for _, c in sw), "shared_words carries doc frequencies")
check(len(ly.shared_words(DOCS[0], DOCS[1], df, n, limit=1)) == 1, "shared_words honors limit")
check(ly.shared_words("", DOCS[1], df, n) == [], "shared_words on empty lyrics is empty")

# IDF similarity: sharing a rare word beats sharing a common one.
rare = ly.lyric_similarity("speed racing", "speed boat", df, n)
common = ly.lyric_similarity("the night", "the rest", df, n)
check(rare > common, f"rare overlap outranks common overlap ({rare:.3f} vs {common:.3f})")
check(ly.lyric_similarity(None, "x", df, n) == 0.0, "similarity with no lyrics is 0.0")
check(ly.lyric_similarity("a b c", "d e f", df, n) == 0.0, "no overlap scores 0.0")

# Called without an index it must still work -- _lyric_rerank has no corpus.
check(0.0 <= ly.lyric_similarity("love you baby", "love you") <= 1.0,
      "similarity without an index stays in range")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python tests/test-mix-report.py`
Expected: FAIL — `AttributeError: module 'lyrics' has no attribute 'word_index'`

- [ ] **Step 3: Write minimal implementation**

Add `import math` to the imports in `Scripts/lyrics.py`. Delete the entire `_STOPWORDS` set (roughly lines 25-110) and replace `theme_signature` / `lyric_similarity` with:

```python
def doc_words(text: str | None) -> set[str]:
    """Content words in a lyric: 3+ chars, surrounding apostrophes trimmed.

    No stopword list -- document frequency demotes function words on its own,
    and a hand-maintained list goes stale against a growing library.
    """
    if not text:
        return set()
    return {w for w in (m.strip("'") for m in _WORD.findall(text.lower())) if len(w) >= 3}


def word_index(docs) -> tuple[dict[str, int], int]:
    """(document frequency per word, number of non-empty documents)."""
    df: dict[str, int] = {}
    n = 0
    for text in docs:
        ws = doc_words(text)
        if not ws:
            continue
        n += 1
        for w in ws:
            df[w] = df.get(w, 0) + 1
    return df, n


def _idf(word: str, df: dict[str, int], n_docs: int) -> float:
    return math.log(n_docs / df.get(word, 1)) if n_docs > 0 else 0.0


def shared_words(
    a: str | None, b: str | None, df: dict[str, int], n_docs: int, limit: int = 8
) -> list[tuple[str, int]]:
    """Words in both lyrics, rarest in the library first, with their doc counts."""
    common = doc_words(a) & doc_words(b)
    ranked = sorted(common, key=lambda w: (df.get(w, 1), w))
    return [(w, df.get(w, 1)) for w in ranked[:limit]]


def lyric_similarity(
    a: str | None, b: str | None, df: dict[str, int] | None = None, n_docs: int = 0
) -> float:
    """IDF-weighted overlap of two lyrics; 0.0 if either is empty.

    Weighting by rarity matters: unweighted, two songs that merely share 'you'
    and 'the' outscore two that share a genuine theme word. Without an index
    (no corpus available) it degrades to a plain unweighted overlap.
    """
    sa, sb = doc_words(a), doc_words(b)
    if not sa or not sb:
        return 0.0
    if not df or n_docs <= 0:
        return len(sa & sb) / len(sa | sb)
    inter = sum(_idf(w, df, n_docs) for w in sa & sb)
    union = sum(_idf(w, df, n_docs) for w in sa | sb)
    return inter / union if union > 0 else 0.0
```

- [ ] **Step 4: Fix the one caller of `theme_signature`**

`theme_signature` is now gone. Confirm nothing else references it:

Run: `grep -rn "theme_signature\|_STOPWORDS" Scripts/ tests/`
Expected: only hits in `tests/test-harmonic-mix.py`. Delete those assertions and replace them with:

```python
check(ly.doc_words("Love you, baby") == {"love", "you", "baby"}, "doc_words splits and lowercases")
check(ly.doc_words(None) == set(), "doc_words(None) is empty")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python tests/test-mix-report.py && .venv/bin/python tests/test-harmonic-mix.py`
Expected: both report `0 failed`

- [ ] **Step 6: Lint and commit**

```bash
/opt/homebrew/bin/ruff check Scripts/lyrics.py tests/ && /opt/homebrew/bin/ruff format Scripts/lyrics.py tests/
git add Scripts/lyrics.py tests/test-mix-report.py tests/test-harmonic-mix.py
git commit -m "lyrics: rank shared words by rarity instead of a stopword list

Measured over the repo's 56 lyric files, ranking two songs' shared words by
document frequency surfaces the thematic tie mechanically -- 'speed' and 'fast'
(4/56 each) rank 2nd and 3rd for SPEED DEMON x Skyline To, while 'you', 'the'
and 'and' sink on their own. The hand-maintained stopword list was doing a worse
version of the same job and would go stale as the library grows.

Flat Jaccard also mis-ordered pairs: it scored the winning pair 0.040 against a
worse pair's 0.054, because a shared 'you' counted as much as a shared 'speed'.
Similarity is now IDF-weighted, degrading to unweighted when no corpus is given.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Resolve a seed track by fuzzy title

**Files:**
- Modify: `Scripts/catalog.py`
- Modify: `tests/test-catalog.py`

**Interfaces:**
- Consumes: `song_title`, `_search_rows` (both already in `catalog.py`).
- Produces: `resolve_seed(con, query) -> tuple[dict | None, str]` where status is `"ok"`, `"nomatch"`, or `"ambiguous"`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test-catalog.py`, before its final `print`:

```python
con.execute(
    "INSERT INTO tracks(name,source_path,artist,bpm,key,first_seen) VALUES(?,?,?,?,?,?)",
    ("03 YUKON", "Apple Music/JB/SWAG/03 YUKON.m4a", "Justin Bieber", 128, "Dm", "2026-07-11T00:00:00"),
)
con.execute(
    "INSERT INTO tracks(name,source_path,artist,bpm,key,first_seen) VALUES(?,?,?,?,?,?)",
    ("06 Skyline To", "Apple Music/FO/Blonde/06 Skyline To.m4a", "Frank Ocean", 129, "F", "2026-07-11T00:00:00"),
)
con.commit()

seed, status = catalog.resolve_seed(con, "YUKON")
assert status == "ok" and seed["name"] == "03 YUKON", (status, seed)

# Case-insensitive and tolerant of the track number the user won't type.
seed, status = catalog.resolve_seed(con, "yukon")
assert status == "ok", (status, seed)

# An unanalyzed track cannot seed a mix -- it has no bpm/key to match on.
seed, status = catalog.resolve_seed(con, "Random Track")
assert status == "nomatch", (status, seed)

seed, status = catalog.resolve_seed(con, "zzzznope")
assert status == "nomatch" and seed is None, (status, seed)

# Substring hitting two analyzed tracks must refuse to guess.
seed, status = catalog.resolve_seed(con, "o")
assert status == "ambiguous" and seed is None, (status, seed)

print("ok: catalog resolve_seed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python tests/test-catalog.py`
Expected: FAIL — `AttributeError: module 'catalog' has no attribute 'resolve_seed'`

- [ ] **Step 3: Write minimal implementation**

Add to `Scripts/catalog.py`, immediately after `_search_rows`:

```python
def resolve_seed(con, query):
    """Find the one analyzed track a seed query names: (row, status).

    status is 'ok', 'nomatch', or 'ambiguous'. Only tracks carrying both bpm and
    key can seed a mix -- an unanalyzed track has nothing to match against, so it
    reads as nomatch rather than a match that returns no pairs.

    An exact title hit wins over a longer substring match, so seeding "Solo" is
    not blocked by "Solo (Reprise)". Anything still ambiguous refuses to guess.
    """
    rows = [r for r in _search_rows(con, query) if r["bpm"] and r["key"]]
    if not rows:
        return None, "nomatch"
    if len(rows) == 1:
        return rows[0], "ok"
    q = (query or "").strip().lower()
    exact = [r for r in rows if song_title(r["name"]).lower() == q]
    if len(exact) == 1:
        return exact[0], "ok"
    return None, "ambiguous"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python tests/test-catalog.py`
Expected: ends with `ok: catalog resolve_seed`

- [ ] **Step 5: Lint and commit**

```bash
/opt/homebrew/bin/ruff check Scripts/catalog.py tests/test-catalog.py && /opt/homebrew/bin/ruff format Scripts/catalog.py tests/test-catalog.py
git add Scripts/catalog.py tests/test-catalog.py
git commit -m "catalog: resolve a seed track by fuzzy title

Only tracks with both bpm and key can seed a mix, so an unanalyzed match reads
as nomatch rather than succeeding and returning nothing. An exact title hit
beats a longer substring so 'Solo' is not blocked by 'Solo (Reprise)'; anything
still ambiguous refuses to guess rather than picking one.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Render the report

**Files:**
- Create: `Scripts/mix_report.py`
- Modify: `tests/test-mix-report.py`

**Interfaces:**
- Consumes: `harmonic_mix.key_to_camelot`, `catalog.song_title`, pair dicts from `rank_pairs`.
- Produces: `why_line(pair) -> str`, `track_label(track) -> str`, `near_misses(seed, tracks, tol, limit=3) -> list[dict]`, `build_report(seed, pairs, words_by_pair, misses) -> dict`, `render_text(report) -> str`.

**Why tempo leads the why-line:** key detection scores 2/13 exact against published labels while tempo is reliable. A verdict that led with key would project confidence the data does not support, so the sentence states the tempo fact first and marks the key claim as needing the ear.

- [ ] **Step 1: Write the failing test**

Append to `tests/test-mix-report.py`, before the final `print`:

```python
# --- report rendering -------------------------------------------------------

import mix_report as mr  # noqa: E402

SEED = {"name": "03 YUKON", "artist": "Justin Bieber", "bpm": 128, "key": "Dm"}
OTHER = {"name": "06 Skyline To", "artist": "Frank Ocean", "bpm": 129, "key": "F"}
PAIR = {"a": SEED, "b": OTHER, "tier": "strong", "key_rel": "relative",
        "tempo_gap": 1, "half_double": False, "lyric_sim": 0.04}

check(mr.track_label(SEED) == "Justin Bieber — YUKON (Dm/128)",
      f"track_label drops the track number, got {mr.track_label(SEED)!r}")

why = mr.why_line(PAIR)
check(why.index("BPM") < why.index("key"), f"tempo fact precedes the key claim: {why!r}")
check("confirm by ear" in why, f"key claim carries its hedge: {why!r}")
check("relative" in why, f"key relation is named: {why!r}")

# A half/double pair must say so rather than reporting a huge tempo gap.
HALF = dict(PAIR, half_double=True, tempo_gap=64,
            b={"name": "x", "artist": "y", "bpm": 64, "key": "F"})
check("half" in mr.why_line(HALF).lower(), f"half/double is named: {mr.why_line(HALF)!r}")

# Near-misses explain an empty result instead of returning nothing.
LONE = {"name": "1-01 SPEED DEMON", "artist": "Justin Bieber", "bpm": 92.7, "key": "Dm"}
misses = mr.near_misses(LONE, [OTHER], tol=0.06)
check(len(misses) == 1, f"a key-compatible but tempo-far track is a near miss, got {misses}")
check(misses[0]["track"]["name"] == "06 Skyline To", "near miss names the track")
check(mr.near_misses(LONE, [], tol=0.06) == [], "no candidates -> no near misses")
check(len(mr.near_misses(LONE, [OTHER] * 9, tol=0.06)) == 3, "near misses cap at 3")

report = mr.build_report(SEED, [PAIR], {id(PAIR): [("speed", 4), ("fast", 4)]}, [])
check(report["seed"]["name"] == "03 YUKON", "report carries the seed")
check(report["verdict"]["b"]["name"] == "06 Skyline To", "verdict names the winner")
check(report["pairs"][0]["shared_words"] == [["speed", 4], ["fast", 4]],
      f"shared words are JSON-ready lists, got {report['pairs'][0]['shared_words']}")

text = mr.render_text(report)
check("Best mix:" in text, f"text names a winner: {text!r}")
check("speed" in text, "text lists the shared words")

# No pairs at all must still produce readable output, not an empty string.
empty = mr.render_text(mr.build_report(SEED, [], {}, []))
check("no" in empty.lower() and len(empty) > 10, f"empty report explains itself: {empty!r}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python tests/test-mix-report.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'mix_report'`

- [ ] **Step 3: Write minimal implementation**

Create `Scripts/mix_report.py`:

```python
#!/usr/bin/env python3
"""Render ranked mix pairs as a report -- text for a human, a dict for JSON.

Pure: no database, no filesystem, no network. Takes the pair dicts rank_pairs
already produces and turns them into something you can act on.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402
import harmonic_mix  # noqa: E402

MAX_NEAR_MISSES = 3


def track_label(t: dict) -> str:
    who = f"{t['artist']} — " if t.get("artist") else ""
    return f"{who}{catalog.song_title(t['name'])} ({t['key']}/{t['bpm']:g})"


def why_line(pair: dict) -> str:
    """Why the pair works, tempo first.

    Tempo is the trustworthy half of the analysis; key detection scores 2/13
    exact against published labels. Leading with key would project confidence
    the estimate does not earn, so the key claim trails and is hedged.
    """
    if pair["half_double"]:
        tempo = "half/double time — one plays at twice the other's pulse"
    else:
        gap = pair["tempo_gap"]
        tempo = (
            f"{gap:g} BPM apart — straight beatmatch, no pitch-fader work"
            if gap <= 1
            else f"{gap:g} BPM apart — inside pitch-fader range"
        )
    rel = pair["key_rel"]
    if not rel:
        return f"{tempo}. Keys are unrelated, so mix on the drums."
    ca = harmonic_mix.key_to_camelot(pair["a"]["key"])
    cb = harmonic_mix.key_to_camelot(pair["b"]["key"])
    wheel = f" ({ca} -> {cb})" if ca and cb else ""
    return f"{tempo}. Keys read as {rel}{wheel} — confirm by ear."


def near_misses(seed: dict, tracks: list[dict], tol: float, limit: int = MAX_NEAR_MISSES):
    """Key-compatible tracks the tempo rules out, with what it would take.

    A seed with no compatible partner should say why nothing came back, not
    return an empty list and leave the user guessing.
    """
    out = []
    for t in tracks:
        if t.get("name") == seed.get("name"):
            continue
        rel = harmonic_mix.key_compatible(seed.get("key"), t.get("key"))
        ok, _ = harmonic_mix.tempo_compatible(seed.get("bpm") or 0, t.get("bpm") or 0, tol)
        if rel and not ok:
            out.append({"track": t, "key_rel": rel,
                        "tempo_gap": abs((seed.get("bpm") or 0) - (t.get("bpm") or 0))})
    out.sort(key=lambda m: m["tempo_gap"])
    return out[:limit]


def build_report(seed: dict, pairs: list[dict], words_by_pair: dict, misses: list[dict]) -> dict:
    """The report as plain data -- render_text and --json both read this."""
    return {
        "seed": seed,
        "verdict": pairs[0] if pairs else None,
        "pairs": [
            {
                "a": p["a"], "b": p["b"], "tier": p["tier"], "key_rel": p["key_rel"],
                "tempo_gap": p["tempo_gap"], "half_double": p["half_double"],
                "why": why_line(p),
                "shared_words": [list(w) for w in words_by_pair.get(id(p), [])],
            }
            for p in pairs
        ],
        "near_misses": [
            {"track": m["track"], "key_rel": m["key_rel"], "tempo_gap": m["tempo_gap"]}
            for m in misses
        ],
    }


def render_text(report: dict) -> str:
    seed = report["seed"]
    lines = [f"Seed: {track_label(seed)}", ""]
    if not report["pairs"]:
        lines.append("No compatible partner in the catalog — nothing matched on key or tempo.")
    else:
        top = report["pairs"][0]
        lines += [f"Best mix: {track_label(top['a'])}  x  {track_label(top['b'])}",
                  f"  {top['why']}"]
        if top["shared_words"]:
            lines.append("  Shared words (rarest first): "
                         + ", ".join(w for w, _ in top["shared_words"]))
        if len(report["pairs"]) > 1:
            lines += ["", "Also compatible:"]
            for p in report["pairs"][1:]:
                lines.append(f"  {track_label(p['b'])}  —  {p['why']}")
    if report["near_misses"]:
        lines += ["", "Near misses (key works, tempo does not):"]
        for m in report["near_misses"]:
            lines.append(f"  {track_label(m['track'])}  —  {m['key_rel']} key, "
                         f"{m['tempo_gap']:g} BPM away")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python tests/test-mix-report.py`
Expected: `0 failed`

- [ ] **Step 5: Lint and commit**

```bash
/opt/homebrew/bin/ruff check Scripts/mix_report.py tests/test-mix-report.py && /opt/homebrew/bin/ruff format Scripts/mix_report.py tests/test-mix-report.py
git add Scripts/mix_report.py tests/test-mix-report.py
git commit -m "mix_report: render ranked pairs as a verdict, not a table

Names one winner and says why in plain language. The why-line leads with the
tempo fact and hedges the key claim, because tempo is the reliable half of the
analysis and key detection scores 2/13 exact against published labels -- leading
with key would project confidence the estimate has not earned.

Near misses explain an empty result rather than returning nothing.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Build and play the audio preview

**Files:**
- Create: `Scripts/mix_preview.py`
- Modify: `tests/test-mix-report.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `atempo_ratio(a_bpm, b_bpm) -> float`, `excerpt_start(transitions, duration) -> float`, `preview_args(a_path, b_path, ratio, out_path, a_start, b_start, seconds=20, fade=8) -> list[str]`, `render(args) -> bool`, `play(path) -> None`.

**Verified before speccing:** the command below produced a correct 32.1s file from a 20+20 excerpt with an 8s crossfade (YUKON 128 x Skyline To 129). `-vn` is mandatory — every Apple Music `.m4a` carries embedded mjpeg cover art, and without it ffmpeg pulls that stream into the output and the wav muxer fails with `does not support more than one stream of type audio`, a message that does not name the cause.

- [ ] **Step 1: Write the failing test**

Append to `tests/test-mix-report.py`, before the final `print`:

```python
# --- preview command builder ------------------------------------------------

import mix_preview as mp  # noqa: E402

check(abs(mp.atempo_ratio(128, 129) - 0.99224) < 0.0001,
      f"ratio is a_bpm/b_bpm, got {mp.atempo_ratio(128, 129)}")
check(mp.atempo_ratio(128, 64) == 1.0, "a double-time partner folds to 1.0")
check(0.5 <= mp.atempo_ratio(160, 40) <= 2.0, "extreme ratios fold into atempo's range")
check(0.5 <= mp.atempo_ratio(40, 160) <= 2.0, "extreme ratios fold from below too")
check(mp.atempo_ratio(0, 128) == 1.0, "a zero BPM degrades to no stretch")

# Start at a section boundary when the analyzer found one, else 25% in.
check(mp.excerpt_start([30.0, 60.0, 90.0], 200.0) == 30.0, "first usable transition wins")
check(mp.excerpt_start([], 200.0) == 50.0, "no transitions -> 25% into the track")
check(mp.excerpt_start([190.0], 200.0) == 50.0, "a transition too close to the end is skipped")

args = mp.preview_args("A.m4a", "B.m4a", 0.99224, "/tmp/p.wav", 40.0, 30.0)
check("-vn" in args, "preview_args passes -vn (Apple Music files carry cover art)")
check(args[0] == "ffmpeg", "preview_args builds an ffmpeg command")
check("atempo=0.992240" in " ".join(args), f"atempo ratio is in the filter: {args}")
check("acrossfade=d=8" in " ".join(args), "crossfade duration is set")
check(args[-1] == "/tmp/p.wav", "output path is last")
check(args.count("-i") == 2, "two inputs")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python tests/test-mix-report.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'mix_preview'`

- [ ] **Step 3: Write minimal implementation**

Create `Scripts/mix_preview.py`:

```python
#!/usr/bin/env python3
"""Render a mix pair as a tempo-matched crossfade and play it.

The report recommends mixes on estimated BPM and key; key detection is the weak
half. A ten-second listen is the only oracle that does not share the estimator's
blind spots, so the preview exists to make the verdict checkable rather than
taken on faith.

Everything except render() and play() is pure and unit-tested without ffmpeg.
"""

from __future__ import annotations

import shutil
import subprocess

SECONDS = 20
FADE = 8


def atempo_ratio(a_bpm: float, b_bpm: float) -> float:
    """Rate to stretch B onto A's grid, folded into atempo's 0.5-2.0 range.

    A half/double pair (128 vs 64) needs no stretch at all once folded -- the
    tracks already share a pulse, one just counts it twice.
    """
    if not a_bpm or not b_bpm or a_bpm <= 0 or b_bpm <= 0:
        return 1.0
    r = a_bpm / b_bpm
    while r > 2.0:
        r /= 2.0
    while r < 0.5:
        r *= 2.0
    return r


def excerpt_start(transitions, duration: float) -> float:
    """Where to start the excerpt: the first section boundary with room to run.

    Starting at a musical boundary beats an arbitrary offset -- a preview that
    begins mid-phrase sounds broken whether or not the pair actually works.
    """
    for t in transitions or []:
        if 0 < t <= max(0.0, duration - SECONDS):
            return float(t)
    return duration * 0.25


def preview_args(a_path, b_path, ratio: float, out_path, a_start: float,
                 b_start: float, seconds: int = SECONDS, fade: int = FADE) -> list[str]:
    """The ffmpeg command for a tempo-matched crossfade.

    -vn is mandatory: Apple Music .m4a files carry an embedded mjpeg cover art
    stream, and without it ffmpeg maps that into the output and the wav muxer
    fails with a message that never mentions cover art.
    """
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{a_start:g}", "-t", f"{seconds:g}", "-i", str(a_path),
        "-ss", f"{b_start:g}", "-t", f"{seconds:g}", "-i", str(b_path),
        "-filter_complex",
        "[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a];"
        f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,atempo={ratio:.6f}[b];"
        f"[a][b]acrossfade=d={fade:g}:c1=tri:c2=tri[out]",
        "-map", "[out]", "-vn", "-ac", "2", str(out_path),
    ]


def render(args: list[str]) -> bool:
    """Run the ffmpeg command. False if ffmpeg is missing or the render failed."""
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found on PATH -- install it with: brew install ffmpeg")
        return False
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"preview render failed: {proc.stderr.strip()}")
        return False
    return True


def play(path) -> None:
    if not shutil.which("afplay"):
        print(f"afplay not found; preview written to {path}")
        return
    subprocess.run(["afplay", str(path)])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python tests/test-mix-report.py`
Expected: `0 failed`

- [ ] **Step 5: Verify against real audio**

Run:
```bash
.venv/bin/python -c "
import sys; sys.path.insert(0, 'Scripts')
import mix_preview as mp
a='Apple Music/Justin Bieber/SWAG/03 YUKON.m4a'
b='Apple Music/Frank Ocean/Blonde/06 Skyline To.m4a'
args=mp.preview_args(a,b,mp.atempo_ratio(128,129),'/tmp/preview.wav',40,30)
print('rendered:', mp.render(args))
"
/opt/homebrew/bin/ffprobe -v error -show_entries format=duration -of csv=p=0 /tmp/preview.wav
```
Expected: `rendered: True` then a duration of about `32.1`

- [ ] **Step 6: Lint and commit**

```bash
/opt/homebrew/bin/ruff check Scripts/mix_preview.py tests/test-mix-report.py && /opt/homebrew/bin/ruff format Scripts/mix_preview.py tests/test-mix-report.py
git add Scripts/mix_preview.py tests/test-mix-report.py
git commit -m "mix_preview: render a mix pair as a tempo-matched crossfade

The report recommends pairs on estimated BPM and key, and key is the weak half
at 2/13 exact. A ten-second listen is the only oracle that does not share the
estimator's blind spots, so the preview makes the verdict checkable instead of
something to take on faith.

-vn is mandatory: Apple Music .m4a files carry embedded mjpeg cover art, and
without it ffmpeg maps that stream into the output and the wav muxer fails with
an error that never mentions cover art.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Wire `--seed` and `--preview` into the CLI

**Files:**
- Modify: `Scripts/catalog.py` (`cmd_mix`, `_lyric_rerank`, argument parser)

**Interfaces:**
- Consumes: `resolve_seed` (Task 3), `mix_report.*` (Task 4), `mix_preview.*` (Task 5), `lyrics.word_index`/`shared_words`/`fetch_lyrics` (Tasks 1-2).
- Produces: the `mix --seed <query> [--preview]` CLI surface.

- [ ] **Step 1: Add the flags to the parser**

In `main()`, the `mix` subparser currently reads:

```python
    p = sub.add_parser("mix")
```

Add beneath its existing arguments:

```python
    p.add_argument("--seed", help="rank partners for one track instead of the whole library")
    p.add_argument(
        "--preview",
        action="store_true",
        help="render and play a tempo-matched crossfade of the top pair (implies --seed)",
    )
```

And update the dispatch call to pass them through:

```python
        elif ns.cmd == "mix":
            rc = cmd_mix(con, ns.tempo_tol, ns.limit, ns.json, ns.lyrics, ns.seed, ns.preview)
```

- [ ] **Step 2: Change `cmd_mix`'s signature and add the seed branch**

Replace `cmd_mix`'s signature and insert the seed handling right after the `tracks` list is built:

```python
def cmd_mix(con, tol, limit, as_json, use_lyrics=False, seed=None, preview=False):
```

After the `if len(tracks) < 2:` guard, add:

```python
    if preview and not seed:
        print("--preview needs --seed (there is no single pair to preview otherwise)")
        return 1

    if seed:
        return _seeded_mix(con, tracks, seed, tol, limit, as_json, use_lyrics, preview)
```

- [ ] **Step 3: Implement the seeded path**

Add above `cmd_mix`:

```python
def _seeded_mix(con, tracks, seed_query, tol, limit, as_json, use_lyrics, preview):
    """Rank one track against the rest, render, and optionally play the top pair."""
    row, status = resolve_seed(con, seed_query)
    if status == "nomatch":
        print(f"no analyzed track matches {seed_query!r} — try: catalog.py search {seed_query!r}")
        return 1
    if status == "ambiguous":
        print(f"{seed_query!r} matches more than one analyzed track:")
        for r in _search_rows(con, seed_query):
            if r["bpm"] and r["key"]:
                print(f"  {song_title(r['name'])}")
        return 1

    seed_name = row["name"]
    pairs = [
        p
        for p in harmonic_mix.rank_pairs(tracks, tol)
        if p["a"]["name"] == seed_name or p["b"]["name"] == seed_name
    ]
    # Orient every pair seed-first so the report reads "seed x partner".
    for p in pairs:
        if p["b"]["name"] == seed_name:
            p["a"], p["b"] = p["b"], p["a"]

    words_by_pair = {}
    if use_lyrics:
        texts = {t["name"]: _lyrics_for(con, t) for t in tracks}
        df, n = lyrics.word_index(texts.values())
        for p in pairs:
            p["lyric_sim"] = lyrics.lyric_similarity(
                texts.get(p["a"]["name"]), texts.get(p["b"]["name"]), df, n
            )
            words_by_pair[id(p)] = lyrics.shared_words(
                texts.get(p["a"]["name"]), texts.get(p["b"]["name"]), df, n
            )
        harmonic_mix.sort_pairs(pairs)

    seed_track = {"name": row["name"], "artist": row["artist"], "bpm": row["bpm"], "key": row["key"]}
    misses = mix_report.near_misses(seed_track, tracks, tol)
    shown = pairs[:limit] if limit else pairs
    report = mix_report.build_report(seed_track, shown, words_by_pair, misses)

    if as_json:
        print(json.dumps(report, ensure_ascii=False, default=str))
    else:
        print(mix_report.render_text(report))

    if preview and shown:
        _play_preview(con, shown[0])
    elif preview:
        print("\nnothing to preview — no compatible pair")
    return 0


def _lyrics_for(con, track):
    row = con.execute("SELECT source_path FROM tracks WHERE name=?", (track["name"],)).fetchone()
    return lyrics.fetch_lyrics(
        track.get("artist"), track["name"], source_path=row["source_path"] if row else None
    )


def _play_preview(con, pair):
    """Render the pair to a temp wav and play it. Never fails the whole report."""
    paths = {}
    for side in ("a", "b"):
        row = con.execute(
            "SELECT source_path FROM tracks WHERE name=?", (pair[side]["name"],)
        ).fetchone()
        if not row or not row["source_path"]:
            print(f"\nno source file for {pair[side]['name']} — cannot preview")
            return
        paths[side] = ROOT / row["source_path"]

    ratio = mix_preview.atempo_ratio(pair["a"]["bpm"], pair["b"]["bpm"])
    out = Path(tempfile.gettempdir()) / "music-mix-preview.wav"
    args = mix_preview.preview_args(paths["a"], paths["b"], ratio, out, 40.0, 30.0)
    print(f"\nrendering preview -> {out}")
    if mix_preview.render(args):
        mix_preview.play(out)
```

Add the imports at the top of `catalog.py` alongside the existing `import harmonic_mix`:

```python
import lyrics  # noqa: E402  (local module, same Scripts/ dir)
import mix_preview  # noqa: E402
import mix_report  # noqa: E402
```

and `import tempfile` to the stdlib import block.

- [ ] **Step 4: Verify against the real catalog**

Run: `.venv/bin/python Scripts/catalog.py mix --seed YUKON --limit 5`
Expected: a `Seed:` line, a `Best mix:` line naming Skyline To, a why-line starting with the BPM gap and ending in `confirm by ear`.

Run: `.venv/bin/python Scripts/catalog.py mix --seed "SPEED DEMON" --limit 5`
Expected: near misses listed (this track has no tempo match in the catalog).

Run: `.venv/bin/python Scripts/catalog.py mix --seed zzzz`
Expected: the nomatch message, exit code 1. Check with `echo $?`.

Run: `.venv/bin/python Scripts/catalog.py mix --preview`
Expected: `--preview needs --seed`, exit code 1.

Run: `.venv/bin/python Scripts/catalog.py mix --limit 5`
Expected: unchanged library-wide output — the existing behavior must not have moved.

Run: `.venv/bin/python Scripts/catalog.py mix --seed YUKON --json | python3 -m json.tool | head -20`
Expected: valid JSON with `seed`, `verdict`, `pairs`, `near_misses` keys.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python tests/test-mix-report.py && .venv/bin/python tests/test-catalog.py && .venv/bin/python tests/test-harmonic-mix.py && zsh tests/test-core.sh`
Expected: all report 0 failures.

- [ ] **Step 6: Lint and commit**

```bash
/opt/homebrew/bin/ruff check Scripts/ && /opt/homebrew/bin/ruff format Scripts/
git add Scripts/catalog.py
git commit -m "catalog: add mix --seed and --preview

A whole-library pair dump answers the wrong question -- the real query names a
track ('what mixes with YUKON'), and at 55 analyzed tracks the flat list is an
arbitrary slice of 1485 possible pairs. --seed pivots on one track; omitting it
leaves the library-wide behavior untouched.

--preview renders the top pair as a tempo-matched crossfade and plays it, so a
recommendation built on a weak key estimate can be checked by ear.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Wrapper and menu entry

**Files:**
- Modify: `lib/music-core.sh`
- Create: `mix-report.sh`
- Modify: `music`

**Interfaces:**
- Consumes: the `mix --seed` CLI from Task 6.
- Produces: `mix_report()` in `music-core.sh`; a `mix-report.sh` wrapper; a menu entry.

- [ ] **Step 1: Add the core function**

In `lib/music-core.sh`, beside the existing `mix_match()` (around line 262):

```bash
mix_report() {
  # Seed-pivoted mix report: which tracks mix well with one named track.
  # Takes a track title (fuzzy) plus optional flags passed to catalog.py mix.
  local seed="$1"; shift
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/catalog.py" mix --seed "$seed" "$@"
}
```

- [ ] **Step 2: Create the wrapper**

Create `mix-report.sh`, matching the style of the existing wrappers:

```bash
#!/usr/bin/env zsh
# Seed-pivoted mix report -- which tracks mix well with one you name.
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

print -n "Track title: "
read -r seed
[[ -z "$seed" ]] && { print "No track given."; exit 1; }

print -n "Play a preview of the top pair? [y/N] "
read -r ans
if [[ "$ans" == [yY]* ]]; then
  mix_report "$seed" --lyrics --preview
else
  mix_report "$seed" --lyrics
fi
```

Then: `chmod +x mix-report.sh`

- [ ] **Step 3: Add the menu entry**

In `music`, add an entry alongside the existing mix-match option, following the surrounding pattern exactly (read the neighbouring cases first — do not invent a new style).

- [ ] **Step 4: Verify**

Run: `zsh -c 'source lib/music-core.sh && mix_report YUKON --limit 3'`
Expected: the same report Task 6 produced.

Run: `printf 'YUKON\nn\n' | ./mix-report.sh`
Expected: the report, no preview.

Run: `zsh tests/test-core.sh`
Expected: existing assertions still pass.

- [ ] **Step 5: Commit**

```bash
git add lib/music-core.sh mix-report.sh music
git commit -m "mix report: add core function, wrapper, and menu entry

Follows the established split -- all logic in music-core.sh, the wrapper only
prompts, so the standalone script and the unified menu cannot drift.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Update project docs

**Files:**
- Modify: `CLAUDE.md`, `STATUS.md`, `TASKS.md`

- [ ] **Step 1: Document the new commands in CLAUDE.md**

Add `mix_report(seed, ...)` to the core-functions list, and add `mix_report.py` / `mix_preview.py` to the Scripts inventory, noting they are stdlib-only (the list of stdlib-only scripts currently reads "all except `chop.py`, `catalog.py`, and `find_track.py`" — extend it).

- [ ] **Step 2: Update STATUS.md**

Under `## Confirmed working`, describe the seeded report in present tense. Add a `- Decided:` entry recording that the report leads with tempo and hedges key because key detection is the weak input, and that the IDF ranking replaced the stopword list on measured evidence.

- [ ] **Step 3: Update TASKS.md**

Flip `- [ ] Brainstorm + improve the mix-match report output` to `- [x] ... — <sha>`. Titles only; put any reasoning in STATUS.md.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md STATUS.md TASKS.md
git commit -m "STATUS/TASKS/CLAUDE: record the seed-pivot mix report

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-review notes

**Spec coverage:** CLI surface -> Task 3 + 6. Lyric sourcing -> Task 1. Word ranking -> Task 2. Report renderer -> Task 4. Mix preview -> Task 5. JSON output -> Task 4 (`build_report`) + Task 6 (`--json`). Tests -> distributed through Tasks 1-5 with a full-suite gate in Task 6 Step 5. Wrapper/menu, which the spec implies via the core/wrapper rule -> Task 7.

**Type consistency:** `resolve_seed` returns `(row, status)` in Task 3 and is destructured that way in Task 6. `shared_words` returns `list[tuple[str, int]]` in Task 2 and `build_report` converts to lists for JSON in Task 4, which the Task 4 test asserts. `words_by_pair` is keyed by `id(pair)` in both Task 4 and Task 6.

**Known deviation from the spec:** Task 6 passes fixed excerpt offsets (40.0/30.0) to `preview_args` rather than deriving them from `analyze_track`'s section transitions, because the catalog does not store transitions — reading them would mean re-running analysis on both tracks for every preview. `excerpt_start` is implemented and tested in Task 5 and is ready for whenever transitions get persisted. Flag this to the user rather than silently storing transitions.
