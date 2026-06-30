# Chop.py Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Scripts/chop.py` correct and tested — fix the trailing-silence bug, guarantee sample-accurate cuts, and pin the segment logic with unit tests.

**Architecture:** Extract the pure segment-math out of `detect_segments` into a standalone `compute_segments()` function that takes parsed numbers (not subprocess output), so it can be unit-tested without invoking ffmpeg. Fix the silence-pairing bug in that pure function. Switch the slicing call from stream-copy to PCM re-encode for sample-accurate cuts.

**Tech Stack:** Python 3.14, pytest, ffmpeg/ffprobe (external), ruff (lint/format, pre-commit enforced).

## Global Constraints

- Python interpreter: `/opt/homebrew/bin/python3`; activate `.venv` before running anything.
- Lint/format: ruff + ruff-format via pre-commit. Never pass `--no-verify`.
- No new dependencies — stdlib + pytest only (pytest already in `.venv`).
- Preserve the existing public CLI: `chop.py <input> <output_dir> [--noise-db] [--min-silence] [--min-clip]`. `chop.sh` calls this contract.

---

### Task 1: Extract and fix the pure segment function

**Files:**
- Modify: `Scripts/chop.py:31-71` (split `detect_segments`)
- Test: `Scripts/tests/test_chop.py` (create)

**Interfaces:**
- Produces: `compute_segments(starts: list[float], ends: list[float], duration: float, min_clip: float) -> list[tuple[float, float]]` — returns sound (non-silent) segments as `(start, end)` second pairs, each `>= min_clip` long.
- Consumes: nothing from other tasks.

- [ ] **Step 1: Write the failing tests**

Create `Scripts/tests/test_chop.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chop import compute_segments


def test_no_silence_returns_whole_file():
    # ffmpeg found no silence at all → one clip spanning the file
    assert compute_segments([], [], 10.0, 0.5) == [(0.0, 10.0)]


def test_single_middle_silence_splits_in_two():
    # silence from 4.0–5.0 → clips [0–4] and [5–10]
    assert compute_segments([4.0], [5.0], 10.0, 0.5) == [(0.0, 4.0), (5.0, 10.0)]


def test_leading_silence_is_dropped():
    # file starts silent: ffmpeg emits an end with no preceding start
    # silence 0–2 → only clip [2–10]
    assert compute_segments([], [2.0], 10.0, 0.5) == [(2.0, 10.0)]


def test_trailing_silence_is_dropped():
    # file ends silent: ffmpeg emits a start with no following end
    # silence 8–end → only clip [0–8], NO tail glued on
    assert compute_segments([8.0], [], 10.0, 0.5) == [(0.0, 8.0)]


def test_short_segments_filtered_by_min_clip():
    # gap 4.0–4.2 is only 0.2s of sound → dropped at min_clip=0.5
    assert compute_segments([4.0, 4.2], [4.2, 5.0], 10.0, 0.5) == [
        (0.0, 4.0),
        (5.0, 10.0),
    ]


def test_all_silence_returns_nothing():
    assert compute_segments([0.0], [10.0], 10.0, 0.5) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest Scripts/tests/test_chop.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_segments'`

- [ ] **Step 3: Implement `compute_segments` and rewire `detect_segments`**

In `Scripts/chop.py`, replace the body of `detect_segments` (lines 31–71) with a thin wrapper plus the new pure function:

```python
def compute_segments(
    starts: list[float], ends: list[float], duration: float, min_clip: float
) -> list[tuple[float, float]]:
    # Pair silence regions. ffmpeg emits a leading end with no start when the
    # file opens in silence, and a trailing start with no end when it closes in
    # silence — normalize both so zip() never drops an unpaired boundary.
    starts = list(starts)
    ends = list(ends)
    if len(ends) > len(starts):
        starts = [0.0] + starts
    if len(starts) > len(ends):
        ends = ends + [duration]

    segments = []
    cursor = 0.0
    for s_start, s_end in zip(starts, ends):
        if s_start - cursor >= min_clip:
            segments.append((cursor, s_start))
        cursor = s_end

    if duration - cursor >= min_clip:
        segments.append((cursor, duration))

    return segments


def detect_segments(
    path: Path, noise_db: int, min_silence: float, min_clip: float
) -> list[tuple[float, float]]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )

    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", result.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", result.stderr)]
    duration = get_duration(path)

    return compute_segments(starts, ends, duration, min_clip)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest Scripts/tests/test_chop.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add Scripts/chop.py Scripts/tests/test_chop.py
git commit -m "fix: handle trailing silence in chop segment logic

Extract pure compute_segments() from detect_segments so the pairing math
is unit-testable without ffmpeg. Trailing silence (unpaired silence_start)
was silently dropped by zip(), gluing the tail onto the last clip.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Sample-accurate cuts (drop stream-copy)

**Files:**
- Modify: `Scripts/chop.py:91-106` (the slicing `subprocess.run` in `slice_file`)

**Interfaces:**
- Consumes: `compute_segments`/`detect_segments` from Task 1 (unchanged signatures).
- Produces: nothing new — same `slice_file(input_path, output_dir, noise_db, min_silence, min_clip) -> int`.

- [ ] **Step 1: Replace `-c copy` with PCM re-encode**

`-c copy` cuts only at existing chunk boundaries, so `-ss`/`-t` offsets land imprecisely. Re-encoding to PCM makes each cut sample-accurate and normalizes any non-WAV input. In `slice_file`, change the ffmpeg arg list:

```python
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-ss",
                str(start),
                "-t",
                str(dur),
                "-c:a",
                "pcm_s16le",
                str(out),
            ],
            capture_output=True,
        )
```

- [ ] **Step 2: Fix the f-string lint (F541) at the no-clips message**

Line ~85 has an f-string with no placeholder. Change:

```python
        print(f"  No clips found — try adjusting silence threshold")
```

to:

```python
        print("  No clips found — try adjusting silence threshold")
```

- [ ] **Step 3: Lint and verify nothing regressed**

Run: `source .venv/bin/activate && ruff check Scripts/chop.py && pytest Scripts/tests/test_chop.py -v`
Expected: ruff reports `All checks passed!`; pytest 6 passed.

- [ ] **Step 4: End-to-end smoke test on one real stem**

Pick any finished stem and confirm clips are produced and non-empty:

```bash
source .venv/bin/activate
S=$(find Stems/htdemucs -name vocals.wav | head -1)
/opt/homebrew/bin/python3 Scripts/chop.py "$S" /tmp/chop-smoke --min-silence 0.35 --min-clip 0.8
ls -la /tmp/chop-smoke/*/ | head
```
Expected: several `vocals_NNN.wav` files listed, each non-zero size.

- [ ] **Step 5: Commit**

```bash
git add Scripts/chop.py
git commit -m "fix: sample-accurate clip cuts via PCM re-encode

Replace -c copy (cuts on chunk boundaries only) with pcm_s16le so -ss/-t
offsets are exact. Also drop a placeholder-less f-string (ruff F541).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Trailing-silence bug → Task 1 (`test_trailing_silence_is_dropped` + normalization fix). ✓
- Leading-silence handling preserved → Task 1 (`test_leading_silence_is_dropped`). ✓
- Untested segment logic → Task 1 (6 unit tests, ffmpeg-free). ✓
- Imprecise `-c copy` cuts → Task 2. ✓
- Lint cleanliness (pre-commit gate) → Task 2 Step 2–3. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `compute_segments(starts, ends, duration, min_clip)` defined in Task 1 and called identically by `detect_segments`. `slice_file` signature unchanged in Task 2. ✓
