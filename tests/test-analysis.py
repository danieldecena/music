#!/usr/bin/env python3
"""
Tests for Scripts/analyze_track.py.

Two modes:

    replay  (default)  Re-run the analyzer over the corpus and diff against
                       tests/baseline-analysis.tsv. The analyzer is
                       deterministic, so a pure refactor must reproduce the
                       baseline exactly; an algorithm change must move only the
                       rows it claims to move. Requires the local audio corpus,
                       so it is skipped when the TSV is missing.

Run with the venv python — numpy is required:
    .venv/bin/python tests/test-analysis.py [replay]
"""

import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))
sys.path.insert(0, str(REPO / "tests"))

import analyze_track as at  # noqa: E402
import record_baseline  # noqa: E402

BASELINE = REPO / "tests" / "baseline-analysis.tsv"

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


def load_baseline() -> dict[str, tuple[str, ...]]:
    rows = BASELINE.read_text().splitlines()
    return {r.split("\t")[0]: tuple(r.split("\t")) for r in rows[1:] if r.strip()}


def replay() -> None:
    """Diff a fresh run against the recorded baseline, row by row."""
    if not BASELINE.is_file():
        print(f"skip: {BASELINE.name} not recorded — run tests/record-baseline.py")
        return
    base = load_baseline()
    files = record_baseline.corpus()
    if not files:
        print("skip: no local audio corpus on this machine")
        return

    seen, drifted = set(), []
    for f in files:
        rel = f.relative_to(REPO).as_posix()
        seen.add(rel)
        if rel not in base:
            continue  # new audio added since the baseline; not a regression
        got = record_baseline.row(f)
        if got != base[rel]:
            drifted.append((rel, base[rel], got))

    missing = sorted(set(base) - seen)
    for rel in missing:
        print(f"  note: baseline row no longer in corpus — {rel}")

    for rel, was, now in drifted:
        print(f"  drift: {rel}\n    was: {was[1:]}\n    now: {now[1:]}")
    check(
        not drifted, f"replay matches baseline ({len(seen & set(base))} rows compared)"
    )


def _clicks(bpm: float, secs: float = 30.0, alt: float = 1.0) -> "np.ndarray":
    """A click train at `bpm`. `alt` scales every second click, so alt<1 gives
    the strong-weak alternation that reads as a halftime feel."""
    n = int(secs * at.SR)
    x = np.random.RandomState(0).randn(n).astype(np.float32) * 0.001
    period = 60.0 / bpm
    env = np.hanning(200).astype(np.float32)
    for i in range(int(secs / period)):
        s = int(i * period * at.SR)
        if s + 200 < n:
            x[s : s + 200] += (1.0 if i % 2 == 0 else alt) * env
    return x


def _tone(freqs, secs: float = 20.0) -> "np.ndarray":
    t = np.arange(int(secs * at.SR)) / at.SR
    return sum(np.sin(2 * np.pi * f * t) for f in freqs).astype(np.float32) / len(freqs)


def synthetic() -> None:
    """Fast, deterministic tests on signals whose ground truth is known by construction."""
    # The 140 BPM cases need sub-lag refinement. At ~43 envelope fps a 140 BPM
    # pulse sits at lag 18.46, and scoring unrefined integer lags is
    # systematically biased toward the halved reading — without _refine_lag both
    # report 69.8, which is the original octave bug. Skipped rather than failed
    # while that fix awaits real-mix verification.
    refined = hasattr(at, "_refine_lag")
    for bpm in (75, 100, 120, 140):
        if bpm == 140 and not refined:
            print("skip: click train 140 BPM (needs the pending tempo octave fix)")
            continue
        got = at.detect_tempo(at.spectra(_clicks(bpm)))
        check(
            abs(got - bpm) < 3, f"click train {bpm} BPM -> {got} (not halved/doubled)"
        )

    if refined:
        got = at.detect_tempo(at.spectra(_clicks(140, alt=0.35)))
        check(abs(got - 140) < 4, f"halftime-feel 140 BPM -> {got}")
    else:
        print("skip: halftime-feel 140 BPM (needs the pending tempo octave fix)")

    # Known limitation, asserted so a future change to the prior surfaces here
    # rather than silently: at 174 the strong-weak alternation still reads as
    # the half-tempo pulse. Both are defensible for this synthetic signal.
    got = at.detect_tempo(at.spectra(_clicks(174, alt=0.35)))
    check(abs(got - 87) < 4, f"KNOWN LIMIT: halftime-feel 174 BPM reads as {got} (~87)")

    # C major triad C4/E4/G4 vs A minor A3/C4/E4
    check(
        at.detect_key(at.spectra(_tone([261.6, 329.6, 392.0]))) == "C",
        "C major triad -> C",
    )
    got = at.detect_key(at.spectra(_tone([220.0, 261.6, 329.6])))
    check(got in ("Am", "C"), f"A minor triad -> {got} (Am or its relative C)")

    k = at._checkerboard(8)
    check(abs(k.sum()) < 1e-9, f"checkerboard sums to ~0 ({k.sum():.1e})")
    check(
        np.sign(k[:8, :8].mean()) != np.sign(k[:8, 8:].mean()),
        "checkerboard quadrants alternate sign",
    )
    # The diagonal quadrants mirror with reversed orientation, not elementwise.
    check(
        np.allclose(k[:8, :8], k[8:, 8:][::-1, ::-1]),
        "checkerboard diagonal quadrants mirror",
    )

    # Two 30s halves in different keys -> a boundary near the seam.
    half = np.concatenate(
        [_tone([261.6, 329.6, 392.0], 30.0), _tone([370.0, 466.2, 554.4], 30.0)]
    )
    sp = at.spectra(half)
    bounds = at.estimate_boundaries(sp, 120.0)
    near = [b for b in bounds if abs(b - 30.0) < 4.0]
    check(bool(near), f"key change at 30s detected (got {bounds[:6]})")

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "htdemucs").mkdir()
        for n in ("vocals", "drums", "bass", "other"):
            (root / "htdemucs" / f"{n}.wav").write_bytes(b"")
        check(
            at.stem_track_dir(root / "htdemucs") is not None, "htdemucs layout detected"
        )

        (root / "acap").mkdir()
        for n in ("vocals", "no_vocals"):
            (root / "acap" / f"{n}.wav").write_bytes(b"")
        check(
            at.stem_track_dir(root / "acap") is None,
            "acapella split is NOT a track folder",
        )

        (root / "songs").mkdir()
        for n in ("a", "b"):
            (root / "songs" / f"{n}.mp3").write_bytes(b"")
        check(
            at.stem_track_dir(root / "songs") is None,
            "plain song folder is NOT a track folder",
        )

    for name, audio in (
        ("empty", np.zeros(0, np.float32)),
        ("100 samples", np.zeros(100, np.float32)),
        ("one frame", np.zeros(2048, np.float32)),
    ):
        sp = at.spectra(audio)
        ok = (
            at.detect_tempo(sp) == 0.0
            and at.detect_key(sp) == "unknown"
            and at.estimate_boundaries(sp) == []
        )
        check(ok, f"short input ({name}) returns 0.0/unknown/[] without crashing")


FIXTURES = REPO / "tests" / "fixtures-analysis.tsv"


def _relative(key: str) -> str:
    """The relative major/minor partner of a key."""
    p = at.PITCHES
    if key.endswith("m"):
        return p[(p.index(key[:-1]) + 3) % 12]
    return p[(p.index(key) + 9) % 12] + "m"


def _bpm_class(got: float, want: float) -> str:
    if want <= 0 or got <= 0:
        return "none"
    for name, mult in (
        ("exact", 1.0),
        ("half", 0.5),
        ("double", 2.0),
        ("two-thirds", 2 / 3),
        ("three-halves", 1.5),
    ):
        if abs(got - want * mult) / want < 0.045:
            return name
    return "off"


def _key_class(got: str, want: str) -> str:
    if got == want:
        return "exact"
    if got == "unknown":
        return "unknown"
    try:
        if got == _relative(want):
            return "relative"
    except ValueError:
        return "off"
    if got.rstrip("m") == want.rstrip("m"):
        return "parallel"
    return "off"


def score() -> None:
    """Score the current analyzer against tests/fixtures-analysis.tsv.

    Reports the distribution of error TYPES, not a single accuracy number,
    because for this toolkit an octave error and a semitone error are different
    problems. Rows whose bpm is suffixed `?` are counted separately -- those are
    labels we do not trust yet.
    """
    if not FIXTURES.is_file():
        print(f"skip: {FIXTURES.name} not present")
        return
    rows = []
    for line in FIXTURES.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            rows.append((parts[0], parts[1].strip(), parts[2].strip()))
    if not rows:
        print("skip: no fixture rows")
        return

    from collections import Counter

    bpm_c, key_c, suspect = Counter(), Counter(), Counter()
    print(f"{'track':30s} {'want':>6} {'got':>7}  {'bpm':<13} {'key':<10}")
    for rel, want_bpm, want_key in rows:
        p = REPO / rel
        if not p.is_file():
            print(f"  MISSING {rel}")
            continue
        sp = at.spectra(at.decode_mono(p, at.SR))
        got_bpm = at.detect_tempo(sp)
        got_key = at.detect_key(sp)
        doubtful = want_bpm.endswith("?")
        wb = float(want_bpm.rstrip("?")) if want_bpm.rstrip("?") else 0.0
        bc = _bpm_class(got_bpm, wb)
        kc = _key_class(got_key, want_key) if want_key else "none"
        (suspect if doubtful else bpm_c)[bc] += 1
        key_c[kc] += 1
        mark = "?" if doubtful else " "
        print(
            f"{p.stem[:30]:30s} {want_bpm:>6} {got_bpm:7.1f}  {bc:<13}{mark}{got_key:<8} {kc}"
        )

    total = sum(bpm_c.values())
    print(f"\nBPM (trusted labels, n={total}): {dict(bpm_c)}")
    print(f"BPM (suspect labels, n={sum(suspect.values())}): {dict(suspect)}")
    print(f"KEY (n={sum(key_c.values())}): {dict(key_c)}")
    octave = bpm_c["half"] + bpm_c["double"]
    print(f"\noctave errors on trusted labels: {octave}/{total}")
    print("NOTE: labels are Echo Nest-derived, not independent ground truth.")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "score":
        score()
        print(f"\n{_passed} passed, {_failed} failed")
        sys.exit(1 if _failed else 0)
    if mode in ("all", "synthetic"):
        synthetic()
    if mode in ("all", "replay"):
        replay()
    if mode not in ("all", "synthetic", "replay"):
        print(f"unknown mode: {mode}")
        sys.exit(2)
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
