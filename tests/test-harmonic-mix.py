#!/usr/bin/env python3
"""
Tests for Scripts/harmonic_mix.py -- the pure harmonic-mixing logic (Camelot
wheel + tempo tolerance + pair ranking). Hand-rolled assertions in the style of
tests/test-analysis.py. Pure stdlib; run with any python3:

    python3 tests/test-harmonic-mix.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import harmonic_mix as hm  # noqa: E402

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


ANALYZER_KEYS = [
    f"{p}{m}"
    for p in ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    for m in ("", "m")
]


def camelot() -> None:
    # All 24 analyzer-producible keys map to a valid, distinct Camelot code.
    codes = [hm.key_to_camelot(k) for k in ANALYZER_KEYS]
    check(all(c is not None for c in codes), "all 24 keys map to a Camelot code")
    check(len(set(codes)) == 24, "all 24 Camelot codes are distinct")

    # Spot-check anchors (relative pairs share a number; minor=A, major=B).
    check(hm.key_to_camelot("Am") == "8A", "Am -> 8A")
    check(hm.key_to_camelot("C") == "8B", "C -> 8B (relative major of Am)")
    check(hm.key_to_camelot("Em") == "9A", "Em -> 9A")
    check(hm.key_to_camelot("G") == "9B", "G -> 9B")
    check(hm.key_to_camelot("B") == "1B", "B -> 1B")
    check(hm.key_to_camelot("G#m") == "1A", "G#m -> 1A")
    check(hm.key_to_camelot("C#m") == "12A", "C#m -> 12A")

    # Flats are defensively accepted (analyzer never emits them, manual entry can).
    check(hm.key_to_camelot("Db") == hm.key_to_camelot("C#") == "3B", "Db == C# == 3B")
    check(
        hm.key_to_camelot("Bbm") == hm.key_to_camelot("A#m") == "3A", "Bbm == A#m == 3A"
    )

    # Unmappable inputs -> None, never a crash.
    check(hm.key_to_camelot("unknown") is None, "unknown -> None")
    check(hm.key_to_camelot("") is None, "empty -> None")
    check(hm.key_to_camelot(None) is None, "None -> None")


def key_compat() -> None:
    check(hm.key_compatible("Am", "Am") == "perfect", "Am/Am perfect")
    check(hm.key_compatible("Am", "C") == "relative", "Am/C relative (8A/8B)")
    check(hm.key_compatible("Am", "Em") == "adjacent", "Am/Em adjacent (8A/9A)")
    check(hm.key_compatible("Am", "Dm") == "adjacent", "Am/Dm adjacent (8A/7A)")
    # Wheel wrap: 12A and 1A are adjacent.
    check(hm.key_compatible("C#m", "G#m") == "adjacent", "C#m/G#m adjacent (12A/1A)")
    # Incompatible + unmappable.
    check(hm.key_compatible("Am", "F#") is None, "Am/F# incompatible (8A/2B)")
    check(hm.key_compatible("Am", "unknown") is None, "Am/unknown -> None")


def tempo() -> None:
    check(hm.tempo_compatible(120, 120) == (True, False), "120/120 exact")
    check(hm.tempo_compatible(120, 124) == (True, False), "120/124 within 6%")
    check(hm.tempo_compatible(120, 130) == (False, False), "120/130 out of tol")
    check(hm.tempo_compatible(80, 160) == (True, True), "80/160 half-double")
    check(hm.tempo_compatible(96, 192) == (True, True), "96/192 half-double")
    check(hm.tempo_compatible(100, 160) == (False, False), "100/160 not mixable")
    check(hm.tempo_compatible(0, 120) == (False, False), "zero bpm -> not compatible")


def ranking() -> None:
    tracks = [
        {"name": "t_am", "artist": "X", "bpm": 120, "key": "Am"},
        {"name": "t_c", "artist": "X", "bpm": 122, "key": "C"},  # strong vs t_am
        {"name": "t_em", "artist": "X", "bpm": 200, "key": "Em"},  # key-only vs t_am
        {"name": "t_fs", "artist": "X", "bpm": 121, "key": "F#"},  # tempo-only vs t_am
        {"name": "t_far", "artist": "X", "bpm": 175, "key": "D#"},  # no match vs t_am
    ]
    pairs = hm.rank_pairs(tracks)
    tiers = {(p["a"]["name"], p["b"]["name"]): p["tier"] for p in pairs}

    def tier_of(n1, n2):
        return tiers.get((n1, n2)) or tiers.get((n2, n1))

    check(tier_of("t_am", "t_c") == "strong", "Am120/C122 -> strong")
    check(tier_of("t_am", "t_em") == "key-only", "Am120/Em200 -> key-only")
    check(tier_of("t_am", "t_fs") == "tempo-only", "Am120/F#121 -> tempo-only")
    check(tier_of("t_am", "t_far") is None, "Am120/D#175 -> dropped")

    # No self-pairs; unordered dedupe (<= n*(n-1)/2 pairs).
    names = [(p["a"]["name"], p["b"]["name"]) for p in pairs]
    check(all(a != b for a, b in names), "no self-pairs")
    check(len(names) == len(set(frozenset(n) for n in names)), "pairs deduped")
    check(len(pairs) <= 5 * 4 // 2, "at most C(5,2) pairs")

    # Strong tier ranked ahead of weaker tiers.
    order = [p["tier"] for p in pairs]
    strong_idx = [i for i, t in enumerate(order) if t == "strong"]
    weak_idx = [i for i, t in enumerate(order) if t != "strong"]
    check(
        not strong_idx or not weak_idx or max(strong_idx) < min(weak_idx),
        "strong pairs sorted before weaker tiers",
    )

    # Empty / single-track input -> no pairs, no crash.
    check(hm.rank_pairs([]) == [], "empty input -> []")
    check(hm.rank_pairs([tracks[0]]) == [], "single track -> []")


def main() -> None:
    camelot()
    key_compat()
    tempo()
    ranking()
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
