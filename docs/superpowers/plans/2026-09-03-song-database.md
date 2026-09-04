# Song Database Implementation Plan (Phases 0-2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a queryable per-song database from Apple's MusicUnderstanding
framework, and prove its structure and instrument-activity output is good enough
to build a product on.

**Architecture:** A macOS Swift CLI dumps MusicUnderstanding's full analysis as
JSON. Python ingests that JSON into the existing `catalog.sqlite`, extended with
time-series tables and a single `regions` table that serves loop-finding, mixing,
and clip extraction alike. Per-track JSON is the durable record; SQLite is a
derived, rebuildable index.

**Tech Stack:** Swift 6 / `swiftc` (no Xcode project), MusicUnderstanding,
AVFoundation, Python 3 stdlib `sqlite3`, existing `Scripts/catalog.py` and
`Scripts/harmonic_mix.py`.

**Spec:** `docs/superpowers/specs/2026-09-03-song-database-design.md`

## Global Constraints

- macOS 27.0+ and Xcode 27 required. `MusicUnderstanding.framework` is present
  in `MacOSX27.0.sdk`; it does not exist on earlier SDKs.
- Python is the repo venv, invoked as an absolute path:
  `"$MUSIC_DIR/.venv/bin/python"`. Never `source activate`, never bare `python3`.
  This matches `lib/music-core.sh:249-252`.
- `deconstruct()` at `lib/music-core.sh:404` re-parses `analyze_track` stdout
  with two `sed -nE` regexes (`:426`, `:429`). The format
  `{name}:  {bpm} BPM   key {key}   transitions [...]` is a load-bearing
  contract. No task in this plan changes it.
- `Scripts/catalog.py` tables `tracks` / `assets` / `runs`
  (`Scripts/catalog.py:85-107`) are extended, never replaced. The existing
  `bpm` / `key` columns stay alongside the new Apple ones so Phase 1 can compare.
- `zsh tests/test-core.sh` and `.venv/bin/python tests/test-analysis.py all`
  must stay green after every task.
- No emoji in any file, commit message, or output.

---

### Task 1: The analysis CLI

**Files:**
- Create: `Tools/mu-analyze.swift`
- Test: `tests/test-mu-analyze.sh`

**Interfaces:**
- Produces: a binary `Tools/mu-analyze <audio> [-o out.json]` writing an
  envelope `{path, durationSeconds, analysisSeconds, result}` where `result` is
  an encoded `MusicUnderstandingSession.SessionResult` carrying keys `rhythm`,
  `key`, `structure`, `loudness`, `pace`, `instrumentActivity`.

- [x] **Step 1: Write the tool**

Done. `Tools/mu-analyze.swift` exists and compiles. Two findings already
recorded, both of which the rest of this plan depends on:

1. `SessionResult` is `Encodable`, so the whole analysis serializes with a
   plain `JSONEncoder` and no hand-written mapping.
2. Loudness reports `-inf` LUFS for digital silence, which JSON cannot
   represent. `JSONEncoder` throws `EncodingError.invalidValue` on it. The tool
   sets `nonConformingFloatEncodingStrategy = .convertToString(...)`, so
   **loudness values arrive downstream as either a number or one of the strings
   `"inf"` / `"-inf"` / `"nan"`.** Task 4's ingest must handle both.

- [ ] **Step 2: Write the failing smoke test**

```bash
# tests/test-mu-analyze.sh — run: zsh tests/test-mu-analyze.sh
set -u
ROOT="${0:A:h}/.."
BIN="$ROOT/Tools/mu-analyze"
fails=0
check() { if [ "$1" = 0 ]; then print "  ok   $2"; else print "  FAIL $2"; fails=$((fails+1)); fi }

[ -x "$BIN" ]; check $? "binary exists and is executable"

"$BIN" >/dev/null 2>&1; [ $? -eq 2 ]; check $? "no args exits 2"
"$BIN" /nonexistent.m4a >/dev/null 2>&1; [ $? -eq 1 ]; check $? "missing file exits 1"

exit $(( fails > 0 ))
```

- [ ] **Step 3: Run it to verify it fails before the binary is built**

Run: `rm -f Tools/mu-analyze && zsh tests/test-mu-analyze.sh`
Expected: FAIL on "binary exists and is executable".

This step matters. A smoke test whose only recorded runs are passes has not been
observed to work (`~/.claude/rules/silent-failure.md`, rule 9). Prove it can
fail before trusting that it passed.

- [ ] **Step 4: Build and re-run**

Run: `swiftc -parse-as-library -O -o Tools/mu-analyze Tools/mu-analyze.swift && zsh tests/test-mu-analyze.sh`
Expected: all three ok.

- [ ] **Step 5: Gitignore the binary, commit the source**

```bash
printf 'Tools/mu-analyze\n' >> .gitignore
git add .gitignore Tools/mu-analyze.swift tests/test-mu-analyze.sh
git commit -m "Add mu-analyze, a MusicUnderstanding probe CLI"
```

---

### Task 2: The Phase 0 verdict

This is the gate. The product thesis is that `StructureResult` and
`InstrumentActivityResult` are good on the material this audience samples. That
is unmeasured. Measure it before building on it.

**Files:**
- Create: `docs/superpowers/specs/2026-09-03-phase0-verdict.md`

**Interfaces:**
- Consumes: `Tools/mu-analyze` from Task 1.
- Produces: a go / no-go verdict the later tasks depend on.

- [ ] **Step 1: Analyze a deliberately mixed spread**

Run at least eight tracks, and **include old, lo-fi, and sample-source material,
not only clean modern pop.** The fixture set in `tests/fixtures-analysis.tsv` is
all contemporary R&B and skews the answer optimistic.

```bash
mkdir -p /tmp/mu
while IFS=$'\t' read -r path bpm key; do
  case "$path" in \#*|"") continue;; esac
  out="/tmp/mu/$(basename "${path%.*}").json"
  Tools/mu-analyze "$path" -o "$out"
done < tests/fixtures-analysis.tsv
```

- [ ] **Step 2: Read structure boundaries against the ear**

For three tracks, play the audio and check whether the reported section
boundaries land where the song actually changes. Note bar-alignment too:
boundaries that are musically right but land mid-bar are a different (and
easier) problem than boundaries in the wrong place.

- [ ] **Step 3: Check instrument activity against known content**

Pick a track with an obvious instrumental break and an obvious vocal section.
Confirm the `activity` signal for vocals actually drops in the break. A detector
that reports the same thing everywhere passes a spot-check on one section and
fails the product.

- [ ] **Step 4: Write the verdict, with tracks named**

The document states, per track examined, what was right and what was wrong. Not
a pass/fail. If structure is weak, say so and stop: Tasks 5 and 6 are built on
it and should be re-planned rather than written against bad data.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-09-03-phase0-verdict.md
git commit -m "Record the Phase 0 verdict on structure and instrument activity"
```

---

### Task 3: Score Apple against the existing labels

**Files:**
- Create: `tests/score_apple.py`
- Read: `tests/fixtures-analysis.tsv`, `tests/fixtures-keys-ug.tsv`

**Interfaces:**
- Consumes: the JSON files from Task 2 step 1.
- Reuses, rather than reimplementing: `_bpm_class` (`tests/test-analysis.py:213`)
  and `verdict` / `harmonic_mix.key_compatible` (`Scripts/key_oracle.py:123`).
- Produces: `python tests/score_apple.py <json-dir>` printing a three-way table.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_score_apple.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import score_apple

def test_bpm_class_is_reused_not_reimplemented():
    # 116 vs a 116 label is exact; 232 is the octave error.
    assert score_apple.bpm_class(116.0, 116.0) == "exact"
    assert score_apple.bpm_class(232.0, 116.0) == "double"

def test_loudness_string_infinity_parses():
    # mu-analyze encodes -inf LUFS as the string "-inf".
    assert score_apple.as_float("-inf") == float("-inf")
    assert score_apple.as_float(-7.25) == -7.25
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_score_apple.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'score_apple'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# tests/score_apple.py
"""Score MusicUnderstanding output against the repo's existing labels.

Deliberately imports the established classifiers instead of writing new ones:
a second implementation of "is this an octave error" that disagrees with the
first would make the comparison meaningless.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from test_analysis import _bpm_class            # noqa: E402
from key_oracle import verdict                  # noqa: E402


def bpm_class(got: float, want: float) -> str:
    return _bpm_class(got, want)


def as_float(v) -> float:
    """mu-analyze encodes non-finite loudness as a string; everything else is
    a JSON number."""
    if isinstance(v, str):
        return float(v)
    return float(v)


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())
```

Note: `tests/test-analysis.py` has a hyphen and is not importable as
`test_analysis`. Add a step to import it via `importlib.util.spec_from_file_location`
rather than renaming the file, which would break `music-core.sh` callers.

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_score_apple.py -v`
Expected: 2 passed.

- [ ] **Step 5: Produce the three-way table**

Extend `score_apple.py` with a `main()` that, per fixture row, prints the label,
our analyzer's reading, and Apple's, plus the classification of each. Tally
exact / half / double / two-thirds / three-halves for BPM on the 10 trusted
rows, and exact / relative / adjacent / unrelated for key.

**This is the payoff:** it also gives Apple's independent reading of Nikes and
Rambo, the two `?` rows STATUS says were blocked after independent BPM sources,
`beat_this`, and Logic Smart Tempo were all exhausted. It is evidence, not a
verdict over the ear.

- [ ] **Step 6: Commit**

```bash
git add tests/score_apple.py tests/test_score_apple.py
git commit -m "Score MusicUnderstanding against the existing BPM and key labels"
```

---

### Task 4: Schema migration

**Files:**
- Modify: `Scripts/catalog.py:85-107` (the schema block)
- Test: `tests/test_catalog_schema.py`

**Interfaces:**
- Produces: `catalog.py migrate` creating the new tables idempotently, and
  `tracks` gaining `duration_s`, `apple_bpm`, `apple_key`, `pace`,
  `lufs_integrated`, `true_peak`, `analyzed_at`, `analysis_version`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_catalog_schema.py
import sqlite3, subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = ROOT / ".venv/bin/python"

def test_migrate_creates_region_table(tmp_path):
    db = tmp_path / "c.sqlite"
    subprocess.run([str(PY), str(ROOT / "Scripts/catalog.py"), "migrate"],
                   env={"MUSIC_CATALOG": str(db)}, check=True)
    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(regions)")}
    assert {"track", "kind", "start_s", "end_s", "start_bar", "n_bars",
            "score", "meta_json"} <= cols

def test_migrate_is_idempotent(tmp_path):
    db = tmp_path / "c.sqlite"
    for _ in range(2):
        subprocess.run([str(PY), str(ROOT / "Scripts/catalog.py"), "migrate"],
                       env={"MUSIC_CATALOG": str(db)}, check=True)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_catalog_schema.py -v`
Expected: FAIL, `catalog.py: invalid choice: 'migrate'`.

- [ ] **Step 3: Add the schema and the subcommand**

```sql
CREATE TABLE IF NOT EXISTS beats (
  track TEXT, idx INTEGER, t REAL, bar INTEGER, beat_in_bar INTEGER);
CREATE TABLE IF NOT EXISTS bars (track TEXT, idx INTEGER, t REAL);
CREATE TABLE IF NOT EXISTS sections (
  track TEXT, idx INTEGER, label TEXT, start_s REAL, end_s REAL);
CREATE TABLE IF NOT EXISTS key_ranges (
  track TEXT, idx INTEGER, tonic TEXT, mode TEXT, start_s REAL, end_s REAL);
CREATE TABLE IF NOT EXISTS loudness (
  track TEXT, t REAL, momentary REAL, short_term REAL);
CREATE TABLE IF NOT EXISTS instrument_activity (
  track TEXT, instrument TEXT, start_s REAL, end_s REAL, level REAL);
CREATE TABLE IF NOT EXISTS lyrics (
  track TEXT, start_s REAL, end_s REAL, text TEXT);
CREATE TABLE IF NOT EXISTS regions (
  track TEXT, kind TEXT, start_s REAL, end_s REAL,
  start_bar INTEGER, n_bars INTEGER, score REAL, meta_json TEXT);
CREATE TABLE IF NOT EXISTS pairs (
  a TEXT, b TEXT, tempo_ok INTEGER, tempo_ratio REAL,
  key_relation TEXT, score REAL);
CREATE INDEX IF NOT EXISTS regions_track_kind ON regions(track, kind);
CREATE INDEX IF NOT EXISTS beats_track ON beats(track);
```

Add the `tracks` columns with `ALTER TABLE ... ADD COLUMN` guarded by a
`PRAGMA table_info(tracks)` check, since SQLite has no `ADD COLUMN IF NOT EXISTS`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_catalog_schema.py -v`
Expected: 2 passed.

- [ ] **Step 5: Confirm nothing regressed**

Run: `zsh tests/test-core.sh && .venv/bin/python tests/test-analysis.py all`
Expected: both green.

- [ ] **Step 6: Commit**

```bash
git add Scripts/catalog.py tests/test_catalog_schema.py
git commit -m "Extend the catalog schema with time-series and regions tables"
```

---

### Task 5: Ingest analysis JSON into the database

**Files:**
- Modify: `Scripts/catalog.py` (add an `ingest` subcommand)
- Test: `tests/test_catalog_ingest.py`

**Interfaces:**
- Consumes: Task 1's JSON envelope, Task 4's schema.
- Produces: `catalog.py ingest <track> <analysis.json>`, idempotent — running it
  twice leaves the same row counts, not doubled ones.

- [ ] **Step 1: Write the failing test**

```python
def test_ingest_is_idempotent(tmp_path, sample_json):
    db = tmp_path / "c.sqlite"
    for _ in range(2):
        run_catalog(db, "ingest", "Ivy", str(sample_json))
    n = sqlite3.connect(db).execute("SELECT count(*) FROM beats").fetchone()[0]
    assert n == EXPECTED_BEATS   # not 2 * EXPECTED_BEATS

def test_ingest_handles_infinite_loudness(tmp_path, sample_json):
    # mu-analyze writes "-inf" as a string for digital silence.
    db = tmp_path / "c.sqlite"
    run_catalog(db, "ingest", "Ivy", str(sample_json))
    vals = [r[0] for r in sqlite3.connect(db).execute(
        "SELECT momentary FROM loudness WHERE momentary IS NOT NULL")]
    assert all(v == v for v in vals)   # no NaN smuggled in
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_catalog_ingest.py -v`
Expected: FAIL, `invalid choice: 'ingest'`.

- [ ] **Step 3: Implement ingest**

Delete the track's existing rows in each time-series table before inserting, so
re-ingest replaces rather than appends. Parse loudness with `score_apple.as_float`
from Task 3 so `"-inf"` becomes a float, and store `None` where the value is not
finite rather than writing `-inf` into SQLite.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_catalog_ingest.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add Scripts/catalog.py tests/test_catalog_ingest.py
git commit -m "Ingest MusicUnderstanding analysis JSON into the catalog"
```

---

### Task 6: The loop region scorer

**Depends on Task 2's verdict being go.** If structure or instrument activity
proved weak, stop and re-plan.

**Files:**
- Create: `Scripts/regions.py`
- Modify: `Scripts/catalog.py` (add a `regions` subcommand)
- Test: `tests/test_regions.py`

**Interfaces:**
- Consumes: `beats`, `bars`, `sections`, `instrument_activity` from Task 5.
- Produces: `score_loops(beats, bars, sections, activity, n_bars=4) -> list[dict]`
  with keys `start_s`, `end_s`, `start_bar`, `n_bars`, `score`, `instruments`;
  and `catalog.py regions <track> --kind loop`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_regions.py
from regions import score_loops

def test_vocal_free_span_outranks_a_vocal_one():
    bars = [{"idx": i, "t": i * 2.0} for i in range(16)]
    beats = [{"idx": i, "t": i * 0.5, "bar": i // 4} for i in range(64)]
    sections = [{"label": "verse", "start_s": 0.0, "end_s": 32.0}]
    # Vocals loud in bars 0-7, silent in bars 8-15.
    activity = [{"instrument": "vocals", "start_s": 0.0, "end_s": 16.0, "level": 0.9},
                {"instrument": "vocals", "start_s": 16.0, "end_s": 32.0, "level": 0.0}]
    loops = score_loops(beats, bars, sections, activity, n_bars=4)
    best = max(loops, key=lambda r: r["score"])
    assert best["start_s"] >= 16.0

def test_candidates_start_on_a_bar():
    bars = [{"idx": i, "t": i * 2.0} for i in range(16)]
    beats = [{"idx": i, "t": i * 0.5, "bar": i // 4} for i in range(64)]
    loops = score_loops(beats, bars, [], [], n_bars=4)
    starts = {r["start_s"] for r in loops}
    assert starts <= {b["t"] for b in bars}
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_regions.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'regions'`.

- [ ] **Step 3: Implement the scorer**

Slide an `n_bars` window over the bar list. For each window, mean vocal
`activity` over the span is the cleanliness term — the continuous 0.0-1.0 signal
`InstrumentActivityResult.activity` provides, which is why this is principled
rather than a hand-tuned heuristic. Add a bonus for windows contained in a single
section, since a loop crossing a section boundary usually changes underneath.
Score is `(1 - mean_vocal_activity) * section_bonus`.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_regions.py -v`
Expected: 2 passed.

- [ ] **Step 5: Verify by ear, not by exit code**

Run `catalog.py regions <a real track> --kind loop`, take the top candidate,
cut it with ffmpeg, and listen. A green test proves the ranking function does
what the synthetic fixtures say; only the ear proves it found a usable loop.

- [ ] **Step 6: Commit**

```bash
git add Scripts/regions.py Scripts/catalog.py tests/test_regions.py
git commit -m "Add the loop region scorer over the beat grid"
```

---

## What this plan deliberately excludes

- **Phase 3, the iOS app.** It gets its own plan once Task 2 returns a verdict.
  Writing bite-sized steps now for SwiftUI views against unmeasured data would
  be fabricating detail.
- **Lyrics via `SpeechTranscriber`,** the `pairs` population, crate search,
  `MediaPlayer` ingest, and demucs to CoreML. All in the spec, none in this plan.

## Self-review

- **Spec coverage:** Phases 0, 1, and 2 of the spec map to Tasks 1-6. Phase 3
  and the "Later" section are explicitly deferred above, not silently dropped.
- **Type consistency:** `bpm_class` and `as_float` defined in Task 3 are the
  names Task 5 imports. `score_loops`' returned keys in Task 6 match what the
  `regions` columns in Task 4 expect.
- **Known gap, stated rather than hidden:** Task 3 step 3 notes that
  `tests/test-analysis.py` is not importable under that name and must be loaded
  via `importlib`. Renaming it would break `lib/music-core.sh` callers.
