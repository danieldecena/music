# Chord-Progression Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estimate a bar-by-bar chord progression for a track or Stems folder, reusing `analyze_track.py`'s chroma/tempo/key machinery, delivered as a printed chart + `chords.txt` reachable from the `music` menu.

**Architecture:** New standalone `Scripts/chords.py` that *imports* `analyze_track.py` (no DSP duplication): reuse its `decode_mono`, `spectra`, `detect_tempo`, `detect_key`, `_key_from_chroma`, `stem_track_dir`, `_KEEP`, `_PROJ`, `PITCHES`, `SR`. Chords are 60 z-scored binary templates (triads + 7ths) matched per bar with the same z-score-Pearson-dot trick as key detection, nudged by a soft diatonic prior from the detected key. Shell wiring mirrors the existing analyze pattern (core fn + wrapper + menu entry).

**Tech Stack:** Python 3 (numpy only, via `.venv/bin/python`), zsh (`lib/music-core.sh`, `music`). Hand-rolled test assertions in the style of `tests/test-analysis.py` — no pytest.

## Global Constraints

- Run all Python via `.venv/bin/python` (numpy required). Activate `.venv` before Python in shell code.
- `chords.py` is numpy-only; import from `analyze_track` for all DSP — never re-derive chroma/tempo/key math (DRY: the per-bar chroma recipe already lives in `analyze_track._beat_features`).
- On analysis failure (no tempo / too short / undecodable), print a message containing `chord analysis failed` and **exit non-zero** — matches the `analyze_track.py` exit-code contract shipped 2026-07-22 that the TUIs and `deconstruct` gate on.
- 4/4 assumed (`BEATS_PER_BAR = 4`), consistent with the rest of the toolkit's bar grid.
- `chords.txt` is written read-only alongside the input (in the folder for a folder input, in the file's parent for a file) — no audio re-encode, same contract as `analysis.txt`.
- No emoji anywhere (output, comments, commits). Use ASCII (`·`, `--`, `-`).
- Match existing file style: module docstring like `analyze_track.py`, comments only for non-obvious reasoning.
- Commit messages end with `Co-Authored-By: Claude <noreply@anthropic.com>`. Never `--no-verify`.

---

### Task 1: Chord templates, diatonic set, and per-bar labeler

Pure functions over chroma vectors — no audio, no I/O. This is the harmonic core.

**Files:**
- Create: `Scripts/chords.py`
- Test: `tests/test-chords.py`

**Interfaces:**
- Consumes (from `analyze_track`): `PITCHES: list[str]` (12 names, sharps), `_KEEP`, `_PROJ` (imported here so the module loads; used in Task 2).
- Produces:
  - `_QUALITIES: tuple[tuple[str, tuple[int, ...]], ...]` — (name-suffix, semitone offsets).
  - `_TEMPLATES: np.ndarray` (60, 12) z-scored; `_CHORD_NAMES: list[str]` (60).
  - `_diatonic_names(key: str) -> set[str]`
  - `_diatonic_mask(key: str) -> np.ndarray | None` — (60,) float 0/1, or None when key unknown.
  - `PRIOR: float` — module-level diatonic bonus.
  - `label_bar(chroma: np.ndarray | None, diatonic_mask: np.ndarray | None, prior: float | None = None) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test-chords.py`:

```python
#!/usr/bin/env python3
"""
Tests for Scripts/chords.py. Hand-rolled assertions in the style of
tests/test-analysis.py. Run with the venv python (numpy required):

    .venv/bin/python tests/test-chords.py [all|unit|exitcode]
"""

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import chords as ch  # noqa: E402

_passed = 0
_failed = 0


def check(cond: bool, label: str) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"ok: {label}")
    else:
        _failed += 1
        print(f"FAIL: {label}")


def _chroma(*pcs: int) -> np.ndarray:
    """L1-normalized chroma with unit energy on the given pitch classes."""
    v = np.zeros(12)
    for p in pcs:
        v[p] = 1.0
    return v / v.sum()


def unit() -> None:
    # Triad + 7th recovery at root C (pitch classes: C=0 E=4 G=7 A=9 Bb=10 B=11).
    check(ch.label_bar(_chroma(0, 4, 7), None) == "C", "C major triad -> C")
    check(ch.label_bar(_chroma(0, 3, 7), None) == "Cm", "C minor triad -> Cm")
    check(ch.label_bar(_chroma(0, 4, 7, 10), None) == "C7", "C dom7 -> C7")
    check(ch.label_bar(_chroma(0, 4, 7, 11), None) == "Cmaj7", "C maj7 -> Cmaj7")
    check(ch.label_bar(_chroma(0, 3, 7, 10), None) == "Cm7", "C min7 -> Cm7")

    # Root coverage: a rolled triad must resolve to its own root.
    check(ch.label_bar(_chroma(2, 6, 9), None) == "D", "D major triad -> D")

    # Empty / flat bar -> placeholder, never a crash.
    check(ch.label_bar(np.zeros(12), None) == "-", "flat chroma -> '-'")
    check(ch.label_bar(None, None) == "-", "None chroma -> '-'")

    # Diatonic set correctness (C major: I ii iii IV V vi as triads + 7ths).
    dia = ch._diatonic_names("C")
    check({"C", "Dm", "Em", "F", "G", "Am"} <= dia, "C major diatonic triads present")
    check({"G7", "Fmaj7", "Cmaj7", "Dm7"} <= dia, "C major diatonic 7ths present")
    check("C#" not in dia and "C#m" not in dia, "C# not diatonic to C major")
    check(ch._diatonic_names("unknown") == set(), "unknown key -> empty diatonic set")

    # A minor (natural minor: i III iv v VI VII).
    diam = ch._diatonic_names("Am")
    check({"Am", "C", "Dm", "Em", "F", "G"} <= diam, "A minor diatonic triads present")

    # Soft prior discrimination. Blend is 55% C# (out of C major) + 45% C (in key):
    # pure match picks C# (more energy), a strong prior flips it to the in-key C,
    # and the prior must NOT fire when the key is unknown.
    blend = 0.55 * _chroma(1, 5, 8) + 0.45 * _chroma(0, 4, 7)
    check(ch.label_bar(blend, None) == "C#", "blend, no prior -> C# (pure match)")
    mask_c = ch._diatonic_mask("C")
    check(ch.label_bar(blend, mask_c, prior=5.0) == "C", "blend, strong C prior -> C")
    check(ch.label_bar(blend, None, prior=5.0) == "C#", "no mask -> prior inert")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("all", "unit"):
        unit()
    if mode not in ("all", "unit", "exitcode"):
        print(f"unknown mode: {mode}")
        sys.exit(2)
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python tests/test-chords.py unit`
Expected: FAIL — `ModuleNotFoundError: No module named 'chords'` (file not created yet).

- [ ] **Step 3: Write the minimal implementation**

Create `Scripts/chords.py`:

```python
#!/usr/bin/env python3
"""Estimate a bar-by-bar chord progression for a track or Stems folder.

Reuses the chroma / tempo / key machinery in analyze_track.py: the same
55-2000 Hz pitch-class projection, the same per-bar log1p chroma recipe as
_beat_features, and the same z-score-makes-Pearson-a-dot-product trick as
_key_from_chroma. Estimates only -- chroma-based labeling, not transcription.

Run with the venv python (numpy required):
    .venv/bin/python Scripts/chords.py <audio file | Stems folder>
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_track as at  # noqa: E402

BEATS_PER_BAR = 4
PRIOR = 0.15  # diatonic bonus added to z-scored template scores; see the plan's
# settle note. Small enough that a clearly out-of-key chord still wins on chroma.

# (name suffix, semitone offsets from the root)
_QUALITIES = (
    ("", (0, 4, 7)),  # major triad
    ("m", (0, 3, 7)),  # minor triad
    ("7", (0, 4, 7, 10)),  # dominant 7th
    ("maj7", (0, 4, 7, 11)),  # major 7th
    ("m7", (0, 3, 7, 10)),  # minor 7th
)


def _chord_templates() -> tuple[np.ndarray, list[str]]:
    """60 z-scored binary chord templates and their names.

    Mirrors analyze_track._key_profiles: one binary vector per (root, quality),
    z-scored so a Pearson correlation against a bar chroma is a plain dot product.
    """
    rows: list[np.ndarray] = []
    names: list[str] = []
    for root in range(12):
        for suffix, offs in _QUALITIES:
            v = np.zeros(12)
            for o in offs:
                v[(root + o) % 12] = 1.0
            rows.append(v)
            names.append(f"{at.PITCHES[root]}{suffix}")
    p = np.array(rows)
    p = (p - p.mean(axis=1, keepdims=True)) / p.std(axis=1, keepdims=True)
    return p, names


_TEMPLATES, _CHORD_NAMES = _chord_templates()

# Diatonic scale degrees -> the chord-name suffixes built on them, in our
# vocabulary. Diminished degrees (vii of major, ii of minor) are omitted -- no
# diminished template exists, and they are the least load-bearing chords anyway.
_MAJOR_DEGREES = {0: ("", "maj7"), 2: ("m", "m7"), 4: ("m", "m7"),
                  5: ("", "maj7"), 7: ("", "7"), 9: ("m", "m7")}
_MINOR_DEGREES = {0: ("m", "m7"), 3: ("", "maj7"), 5: ("m", "m7"),
                  7: ("m", "m7"), 8: ("", "maj7"), 10: ("", "7")}


def _diatonic_names(key: str) -> set[str]:
    """Chord names diatonic to `key` (label like 'F' or 'Am'). Empty if unknown."""
    if not key or key == "unknown":
        return set()
    minor = key.endswith("m")
    root_name = key[:-1] if minor else key
    if root_name not in at.PITCHES:
        return set()
    root = at.PITCHES.index(root_name)
    degrees = _MINOR_DEGREES if minor else _MAJOR_DEGREES
    out: set[str] = set()
    for deg, suffixes in degrees.items():
        pitch = at.PITCHES[(root + deg) % 12]
        for s in suffixes:
            out.add(f"{pitch}{s}")
    return out


def _diatonic_mask(key: str) -> np.ndarray | None:
    """(60,) float mask, 1.0 on diatonic chords. None when the key is unknown."""
    names = _diatonic_names(key)
    if not names:
        return None
    return np.array([1.0 if n in names else 0.0 for n in _CHORD_NAMES])


def label_bar(
    chroma: np.ndarray | None,
    diatonic_mask: np.ndarray | None,
    prior: float | None = None,
) -> str:
    """Best chord name for one bar's chroma. '-' for a silent / flat bar.

    diatonic_mask (or None to disable the prior) receives a `prior` bonus before
    the argmax, so an ambiguous bar resolves in-key while a strongly-supported
    out-of-key chord still wins on chroma alone.
    """
    if chroma is None or chroma.sum() == 0:
        return "-"
    std = chroma.std()
    if std == 0:
        return "-"
    z = (chroma - chroma.mean()) / std
    scores = _TEMPLATES @ z
    if diatonic_mask is not None:
        p = PRIOR if prior is None else prior
        scores = scores + p * diatonic_mask
    return _CHORD_NAMES[int(np.argmax(scores))]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python tests/test-chords.py unit`
Expected: PASS — all `ok:` lines, `N passed, 0 failed`.

- [ ] **Step 5: Commit**

```bash
git add Scripts/chords.py tests/test-chords.py
git commit -m "chords: chord templates, diatonic set, per-bar labeler

60 z-scored triad+7th templates matched with the same z-score-Pearson dot
trick as key detection. Soft diatonic prior from the detected key nudges
ambiguous bars in-key without overriding clear out-of-key chords.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Per-bar chroma extraction and progression assembly

Turn a `Spec` into a list of chord labels. Reuses the exact per-bar chroma recipe from `analyze_track._beat_features`.

**Files:**
- Modify: `Scripts/chords.py` (append)
- Test: `tests/test-chords.py` (add `audio()` mode)

**Interfaces:**
- Consumes (from `analyze_track`): `Spec` (attrs `mag`, `fps`, `n_frames`), `_KEEP`, `_PROJ`, `SR`, `spectra`, `decode_mono`, `detect_tempo`, `detect_key`, `_key_from_chroma`, `stem_track_dir`. From Task 1: `label_bar`, `_diatonic_mask`.
- Produces:
  - `bar_chroma(sp: at.Spec, bpm: float) -> np.ndarray | None` — (n_bars, 12) L1-normalized, or None if unbarrable.
  - `_bars_from_stems(stems: dict[str, Path], bpm: float) -> np.ndarray | None`
  - `analyze_chords(p: Path) -> tuple[float, str, list[str]]` — (bpm, key, per-bar labels); raises `ValueError` if unbarrable.

- [ ] **Step 1: Write the failing test**

Add to `tests/test-chords.py` — a helper and an `audio()` function, and call it from `main`:

```python
def _tone(freqs, secs: float) -> np.ndarray:
    t = np.arange(int(secs * ch.at.SR)) / ch.at.SR
    return sum(np.sin(2 * np.pi * f * t) for f in freqs).astype(np.float32) / len(freqs)


def audio() -> None:
    # 8 bars of a sustained C major triad at 120 BPM: 8 bars * 4 beats * 0.5 s.
    # detect_tempo is unreliable on a beatless drone, so drive bar_chroma with a
    # known BPM -- this isolates the chroma/label path, not tempo detection.
    audio_sig = _tone([261.63, 329.63, 392.00], secs=8 * 4 * 0.5)
    sp = ch.at.spectra(audio_sig)
    bars = ch.bar_chroma(sp, 120.0)
    check(bars is not None and len(bars) >= 6, f"C drone -> >=6 bars (got {None if bars is None else len(bars)})")
    if bars is not None:
        labels = [ch.label_bar(b, None) for b in bars]
        c_count = sum(1 for x in labels if x == "C")
        check(c_count >= len(labels) - 1, f"C drone bars label C ({c_count}/{len(labels)})")

    # Too short to bar -> None.
    check(ch.bar_chroma(ch.at.spectra(_tone([440.0], secs=0.2)), 120.0) is None, "0.2s -> None bars")
```

And extend `main`:

```python
    if mode in ("all", "audio"):
        audio()
```
(add `"audio"` to the allowed-modes tuple in the `unknown mode` guard.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python tests/test-chords.py audio`
Expected: FAIL — `AttributeError: module 'chords' has no attribute 'bar_chroma'`.

- [ ] **Step 3: Write the minimal implementation**

Append to `Scripts/chords.py`:

```python
def bar_chroma(sp: at.Spec, bpm: float) -> np.ndarray | None:
    """One L1-normalized 12-dim chroma vector per bar, or None if too short.

    Same recipe as analyze_track._beat_features: aggregate frames into bars at
    the detected tempo, log1p-compress (so one loud hit cannot dominate), then
    project to pitch classes over the 55-2000 Hz band.
    """
    if bpm <= 0 or sp.n_frames < 16:
        return None
    period = sp.fps * 60.0 / bpm * BEATS_PER_BAR
    n = int(sp.n_frames / period)
    if n < 2:
        return None
    while n > 2000:  # a pathological tempo must not blow up the row count
        period *= 2.0
        n = int(sp.n_frames / period)
    edges = np.rint(np.arange(n + 1) * period).astype(int).clip(0, sp.n_frames)
    logmag = np.log1p(sp.mag)
    rows: list[np.ndarray] = []
    for a, b in zip(edges[:-1], edges[1:]):
        if b <= a:
            rows.append(np.zeros(12))
            continue
        c = logmag[a:b, at._KEEP].mean(axis=0) @ at._PROJ
        s = c.sum()
        rows.append(c / s if s > 0 else np.zeros(12))
    return np.array(rows)


def _bars_from_stems(stems: dict[str, Path], bpm: float) -> np.ndarray | None:
    """Combined per-bar chroma from the harmonic stems.

    `other` (and guitar/piano on a 6-stem split) carry the chords; bass pins the
    root but is weighted below them so a strong bass note cannot swamp the third.
    """
    weights = {"other": 1.0, "guitar": 1.0, "piano": 1.0, "bass": 0.5}
    acc = None
    for name, w in weights.items():
        if name not in stems:
            continue
        b = bar_chroma(at.spectra(at.decode_mono(stems[name], at.SR)), bpm)
        if b is None:
            continue
        acc = w * b if acc is None else acc + w * b
    if acc is None:
        return None
    s = acc.sum(axis=1, keepdims=True)
    return np.divide(acc, s, out=np.zeros_like(acc), where=s > 0)


def analyze_chords(p: Path) -> tuple[float, str, list[str]]:
    """Return (bpm, key, per-bar chord labels). Raises ValueError if unbarrable.

    A Stems track folder reads tempo from drums and chords from the harmonic
    stems (matching analyze_track). A single file uses itself for all three.
    """
    stems = at.stem_track_dir(p)
    if stems is not None:
        bpm = at.detect_tempo(at.spectra(at.decode_mono(stems["drums"], at.SR)))
        bars = _bars_from_stems(stems, bpm)
        key = at._key_from_chroma(bars.mean(axis=0)) if bars is not None else "unknown"
    else:
        sp = at.spectra(at.decode_mono(p, at.SR))
        bpm = at.detect_tempo(sp)
        key = at.detect_key(sp)
        bars = bar_chroma(sp, bpm)
    if bars is None or len(bars) < 2:
        raise ValueError("no tempo or too short to form bars")
    mask = _diatonic_mask(key)
    return bpm, key, [label_bar(b, mask) for b in bars]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python tests/test-chords.py audio`
Expected: PASS. Then confirm the whole suite: `.venv/bin/python tests/test-chords.py` -> `N passed, 0 failed`.

- [ ] **Step 5: Commit**

```bash
git add Scripts/chords.py tests/test-chords.py
git commit -m "chords: per-bar chroma extraction and progression assembly

bar_chroma reuses _beat_features' log1p bar-aggregation recipe; analyze_chords
reads tempo from drums and chords from the harmonic stems for a Stems folder,
or the file itself otherwise.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: CLI — chart printing, chords.txt, exit-code contract

Make `chords.py` runnable and honest about failure.

**Files:**
- Modify: `Scripts/chords.py` (append)
- Test: `tests/test-chords.py` (add `exitcode` mode + `_write_wav`/click helper)

**Interfaces:**
- Consumes: Task 2's `analyze_chords`.
- Produces:
  - `format_chart(name: str, bpm: float, key: str, labels: list[str]) -> str`
  - `chords_txt(name: str, bpm: float, key: str, labels: list[str]) -> str`
  - `main() -> None` — prints the chart, writes `chords.txt`, exits non-zero on failure.

- [ ] **Step 1: Write the failing test**

Add to `tests/test-chords.py`:

```python
def _write_wav(path: Path, audio_sig: np.ndarray) -> None:
    pcm = (np.clip(audio_sig, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(ch.at.SR)
        w.writeframes(pcm.tobytes())


def _clicks_over_tone(bpm: float, secs: float) -> np.ndarray:
    """A tonal C-major bed with periodic clicks, so both tempo and chroma exist."""
    bed = _tone([261.63, 329.63, 392.00], secs=secs)
    period = int(ch.at.SR * 60.0 / bpm)
    for i in range(0, len(bed), period):
        bed[i : i + 200] += 0.8  # a short broadband tick on each beat
    return bed


def exitcode() -> None:
    script = REPO / "Scripts" / "chords.py"
    with tempfile.TemporaryDirectory() as d:
        bad = Path(d) / "garbage.wav"
        bad.write_bytes(b"not audio, just bytes " * 64)
        r = subprocess.run([sys.executable, str(script), str(bad)], capture_output=True, text=True)
        check(r.returncode != 0, f"bad file -> non-zero exit (got {r.returncode})")
        check("chord analysis failed" in r.stdout, "bad file -> prints 'chord analysis failed'")

        good = Path(d) / "good.wav"
        _write_wav(good, _clicks_over_tone(120.0, secs=12.0))
        r = subprocess.run([sys.executable, str(script), str(good)], capture_output=True, text=True)
        check(r.returncode == 0, f"good file -> zero exit (got {r.returncode})")
        check((Path(d) / "chords.txt").is_file(), "good file -> writes chords.txt beside it")
        check("BPM" in r.stdout, "good file -> prints a chart header")
```

And extend `main`: add `if mode in ("all", "exitcode"): exitcode()` and add `"exitcode"` is already in the allowed tuple — ensure `"audio"` and `"unit"` are too.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python tests/test-chords.py exitcode`
Expected: FAIL — `chords.py` has no `main` output / `AttributeError` or a usage/print mismatch (no chart, no chords.txt).

- [ ] **Step 3: Write the minimal implementation**

Append to `Scripts/chords.py`:

```python
def format_chart(name: str, bpm: float, key: str, labels: list[str]) -> str:
    """Bar-by-bar chart, 4 bars per line, repeats collapsed to a mid-dot."""
    cells: list[str] = []
    prev = None
    for lab in labels:
        cells.append("·" if lab == prev else lab)
        prev = lab
    width = max((len(c) for c in cells), default=1)
    lines = [f"Chords -- {name}", f"key {key} · {bpm} BPM · {len(labels)} bars", ""]
    for i in range(0, len(cells), BEATS_PER_BAR):
        body = "  ".join(c.ljust(width) for c in cells[i : i + BEATS_PER_BAR])
        lines.append(f"{i + 1:>3} | {body} |")
    return "\n".join(lines)


def chords_txt(name: str, bpm: float, key: str, labels: list[str]) -> str:
    """Full, uncollapsed bar list for the sidecar file: 'bar<TAB>chord' per line."""
    head = [f"# Chords -- {name}", f"# key {key}  {bpm} BPM  {len(labels)} bars"]
    body = [f"{i + 1}\t{lab}" for i, lab in enumerate(labels)]
    return "\n".join(head + body) + "\n"


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: chords.py <audio file | Stems folder>")
        sys.exit(1)
    p = Path(sys.argv[1])
    try:
        bpm, key, labels = analyze_chords(p)
    except Exception as exc:  # noqa: BLE001
        print(f"chord analysis failed -- {exc}")
        sys.exit(1)
    print(format_chart(p.name, bpm, key, labels))
    dest = (p if p.is_dir() else p.parent) / "chords.txt"
    try:
        dest.write_text(chords_txt(p.name, bpm, key, labels))
        print(f"\n  Chart: {dest}")
    except OSError:
        pass  # a chart printed to stdout is still the primary output


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python tests/test-chords.py exitcode`
Expected: PASS. Then the full suite: `.venv/bin/python tests/test-chords.py` -> `N passed, 0 failed`.

- [ ] **Step 5: Commit**

```bash
git add Scripts/chords.py tests/test-chords.py
git commit -m "chords: CLI chart, chords.txt sidecar, exit-code contract

Prints a 4-bars-per-line chart with repeats collapsed, writes an uncollapsed
chords.txt beside the input, and exits non-zero on analysis failure -- matching
analyze_track.py so the menu/TUI callers are not fooled by a self-reported fail.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Shell wiring — core function, wrapper, menu entry

Reach the analyzer the toolkit's standard way. Not unit-tested (thin shell over Python); verified end-to-end against real repo data.

**Files:**
- Modify: `lib/music-core.sh` (add `chord_progression()` after `analyze_track()`, ~line 252)
- Create: `chords.sh`
- Modify: `music` (Tools submenu legend ~line 96 + a new `H|h)` case in the menu `case` block, alongside `A|a)` ~line 197)

**Interfaces:**
- Consumes: `Scripts/chords.py`, `$MUSIC_DIR` / `$SCRIPT_DIR`, `resolve_stems`, `read_path`.
- Produces: `chord_progression <file|folder>` core fn; `H` menu entry; `./chords.sh`.

- [ ] **Step 1: Add the core function**

In `lib/music-core.sh`, immediately after the `analyze_track()` function (the 3-line one ending `}` near line 252), add:

```sh
chord_progression() {
  # $1 = an audio file or a Stems/<model>/<track> folder. Prints a bar-by-bar
  # chord chart and writes <input>/chords.txt (read-only; never re-encodes).
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/chords.py" "$1"
}
```

- [ ] **Step 2: Create the wrapper**

Create `chords.sh` (mirror `analyze-stems.sh`'s shape — same shebang and core-sourcing pattern; check that file for the exact preamble and match it):

```sh
#!/bin/zsh
# Interactive front end for chord_progression: prompt for input, then call the
# core function. Mirrors analyze-stems.sh.
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Drag an audio file or a Stems track folder:"
INPUT=$(read_path)
[[ ! -e "$INPUT" ]] && { echo "Invalid path."; exit 1; }
chord_progression "$INPUT"
```

Then: `chmod +x chords.sh`. If `analyze-stems.sh` sets `MUSIC_DIR` or sources differently, match it exactly instead of the above.

- [ ] **Step 3: Add the menu entry**

In `music`, in the Tools submenu legend block (near the `A  Stem levels` line ~96), add a line:

```sh
    echo "    H  Chords                bar-by-bar progression"
```

Then in the menu `case "$choice"` block, next to the `A|a)` case (~line 197), add:

```sh
    H|h)
      INPUT=$(resolve_stems)
      [[ -z "$INPUT" ]] && continue
      [[ ! -e "$INPUT" ]] && { echo "Invalid path."; continue; }
      chord_progression "$INPUT"
      ;;
```

(`H` is free; `C` is already "clear current track".)

- [ ] **Step 4: Verify end-to-end against real data**

Confirm a real Stems folder exists, then run the core function directly:

```bash
source .venv/bin/activate
ls -d "Stems/htdemucs_6s/02 Let Em' Know" 2>/dev/null || ls -d Stems/*/*/ | head
.venv/bin/python Scripts/chords.py "Stems/htdemucs_6s/02 Let Em' Know"
```

Expected: a printed chart with a `key ... BPM ... bars` header and `NN | ... |` lines; a `chords.txt` written inside the folder. Verify: `cat "Stems/htdemucs_6s/02 Let Em' Know/chords.txt" | head`.

Then exercise the wrapper and confirm the menu wiring parses:

```bash
zsh -n chords.sh && echo "chords.sh OK"
zsh -n music && echo "music OK"
```

Expected: both print `OK` (no syntax errors). If no real Stems folder exists in this checkout, note it and verify with a single audio file instead (`.venv/bin/python Scripts/chords.py <some.m4a>`).

- [ ] **Step 5: Commit**

```bash
git add lib/music-core.sh chords.sh music
git commit -m "chords: wire chord_progression into music-core, wrapper, and menu

Standard core/wrapper pattern: chord_progression() in music-core.sh, a thin
chords.sh, and an H) Chords entry in the Tools submenu. Reaches the analyzer
the same way the other analysis steps are reached.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Post-implementation

- [ ] Run the full suite once more: `.venv/bin/python tests/test-chords.py` and `.venv/bin/python tests/test-analysis.py` (confirm the import-time changes to nothing in `analyze_track.py` left it green).
- [ ] Update `STATUS.md`: add a `## Confirmed working` bullet for the chord analyzer (what it does, that it is synthetic-tested and estimate-only, `PRIOR=0.15` as the tuning knob), and a `## Known broken / unverified` note that real-track chord accuracy is unverified by ear (same caveat as tempo/key). Add a decision-log entry.
- [ ] `PRIOR` settle note: `0.15` is a first guess. If real-track charts look noisy with out-of-key labels, raise it; if they look flattened onto the diatonic set, lower it. It is one module constant in `Scripts/chords.py`.

## Self-review notes

- **Spec coverage:** per-bar (Task 2 `bar_chroma`), triads+7ths (Task 1 `_QUALITIES`, 60 templates), soft diatonic prior (Task 1 `label_bar`/`_diatonic_mask`), printed chart + `chords.txt` (Task 3), stem-folder aware (Task 2 `_bars_from_stems` + `analyze_chords`), menu+wrapper+core fn (Task 4), synthetic tests incl. prior discrimination and exit code (Tasks 1-3). All spec sections mapped.
- **Type consistency:** `label_bar(chroma, diatonic_mask, prior=None)`, `bar_chroma(sp, bpm)`, `analyze_chords(p) -> (float, str, list[str])`, `format_chart`/`chords_txt(name, bpm, key, labels)` are used identically wherever referenced across tasks.
- **No DSP duplication:** all chroma/tempo/key math is imported from `analyze_track`; only the bar-aggregation loop (short, and deliberately parallel to `_beat_features` for one caller) is written here.
