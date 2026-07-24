#!/usr/bin/env python3
"""Harmonic mixing logic: Camelot-wheel key compatibility, tempo tolerance, and
track-pair ranking. Pure stdlib -- no DB, no network, no numpy. The catalog `mix`
subcommand feeds it rows and prints the result.

"Mix well" here means what a DJ means: two tracks in compatible keys (adjacent on
the Camelot wheel, or a relative major/minor pair) that also beatmatch (same tempo
within a pitch-shift tolerance, or a clean half/double-time relationship).
"""

from __future__ import annotations  # str | None annotations on py3.9

import math

# Analyzer key label -> Camelot code. The analyzer spells with sharps only
# (PITCHES in analyze_track.py) and an "m" suffix for minor, so these 24 cover
# every value it can emit. Minor keys sit on the "A" ring, major on "B"; a
# relative major/minor pair shares its number (Am 8A <-> C 8B). Built from the
# circle of fifths: the B-ring number increments by a perfect fifth.
_MAJOR_CAMELOT = {
    "B": 1,
    "F#": 2,
    "C#": 3,
    "G#": 4,
    "D#": 5,
    "A#": 6,
    "F": 7,
    "C": 8,
    "G": 9,
    "D": 10,
    "A": 11,
    "E": 12,
}
_MINOR_CAMELOT = {
    "G#": 1,
    "D#": 2,
    "A#": 3,
    "F": 4,
    "C": 5,
    "G": 6,
    "D": 7,
    "A": 8,
    "E": 9,
    "B": 10,
    "F#": 11,
    "C#": 12,
}

# Defensive flat -> sharp spelling. The analyzer never emits flats, but --key /
# set-analysis are free text, so a hand-entered "Bbm" must still map.
_FLAT_TO_SHARP = {
    "Db": "C#",
    "Eb": "D#",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
    "Cb": "B",
    "Fb": "E",
}


def key_to_camelot(key: str | None) -> str | None:
    """Camelot code (e.g. '8A', '12B') for a key label, or None if unmappable.

    Accepts the analyzer's sharp spelling ('Am', 'C', 'F#m') and, defensively,
    flats ('Bbm'). 'unknown', '', and None all return None.
    """
    if not key:
        return None
    key = key.strip()
    if not key or key == "unknown":
        return None
    minor = key.endswith("m")
    root = key[:-1] if minor else key
    root = _FLAT_TO_SHARP.get(root, root)
    table = _MINOR_CAMELOT if minor else _MAJOR_CAMELOT
    num = table.get(root)
    if num is None:
        return None
    return f"{num}{'A' if minor else 'B'}"


def _parse_code(code: str) -> tuple[int, str]:
    return int(code[:-1]), code[-1]


def key_compatible(k1: str | None, k2: str | None) -> str | None:
    """Camelot relationship between two keys, or None if not compatible.

    'perfect'  -> same code
    'relative' -> same number, opposite ring (relative major/minor)
    'adjacent' -> same ring, one step around the wheel (with 12<->1 wrap)
    """
    c1, c2 = key_to_camelot(k1), key_to_camelot(k2)
    if c1 is None or c2 is None:
        return None
    n1, r1 = _parse_code(c1)
    n2, r2 = _parse_code(c2)
    if n1 == n2 and r1 == r2:
        return "perfect"
    if n1 == n2 and r1 != r2:
        return "relative"
    if r1 == r2 and abs(n1 - n2) in (1, 11):  # 11 == the 12<->1 wrap
        return "adjacent"
    return None


def tempo_compatible(b1: float, b2: float, tol: float = 0.06) -> tuple[bool, bool]:
    """(compatible, is_half_double) for two BPMs.

    Compatible when the faster is within `tol` of the slower, or -- after folding
    the faster down by octaves (halving) into the slower's range -- lands within
    `tol`. The second case (a half/double-time mix, e.g. 80<->160) sets the flag.
    Either BPM <= 0 -> (False, False).
    """
    if b1 <= 0 or b2 <= 0:
        return (False, False)
    hi, lo = (b1, b2) if b1 >= b2 else (b2, b1)
    if hi / lo <= 1 + tol:
        return (True, False)
    folded = hi
    while folded > lo * (1 + tol):
        folded /= 2
    if lo * (1 - tol) <= folded <= lo * (1 + tol):
        return (True, True)
    return (False, False)


# Sort weights: better tier / relationship first, so a plain reverse-free sort on
# the tuple puts the best mixes at the top.
_TIER_RANK = {"strong": 0, "key-only": 1, "tempo-only": 2}
_REL_RANK = {"perfect": 0, "relative": 1, "adjacent": 2, None: 3}


def _sort_key(p: dict):
    # tier, then higher lyric similarity (0 when unscored -> neutral), then the
    # tempo gap, then key closeness. A no-lyrics run sorts as (tier, gap, rel).
    #
    # Tempo outranks key because it is the reliable half of the analysis: key
    # detection is 2/13 exact against published labels, and the report already
    # hedges every key claim with "confirm by ear". Ranking by a signal we tell
    # the user not to trust put a 4-BPM/perfect-key pair above a 1-BPM/relative
    # one -- the wrong call for actually beatmatching.
    #
    # The gap buckets to whole BPM (the report's own "straight beatmatch"
    # threshold) so an inaudible 1.0-vs-0.8 difference cannot override the key.
    # Inside a bucket, key closeness is the real tie-break.
    return (
        _TIER_RANK[p["tier"]],
        -(p["lyric_sim"] or 0.0),
        math.ceil(p["tempo_gap"]),
        _REL_RANK[p["key_rel"]],
    )


def sort_pairs(pairs: list[dict]) -> None:
    """Sort pairs in place, best mixes first. Call again after setting lyric_sim
    on the strong pairs to fold the lyric re-rank in."""
    pairs.sort(key=_sort_key)


def rank_pairs(tracks: list[dict], tol: float = 0.06) -> list[dict]:
    """Rank every compatible unordered pair of tracks, best mixes first.

    Each track is a dict with at least name/artist/bpm/key. A pair is kept when
    its keys are compatible, its tempos are compatible, or both:
      strong     -> key AND tempo compatible
      key-only   -> keys compatible, tempos not
      tempo-only -> tempos compatible, keys not
    Non-matches are dropped. No self-pairs; each unordered pair appears once.
    """
    out: list[dict] = []
    for i in range(len(tracks)):
        for j in range(i + 1, len(tracks)):
            a, b = tracks[i], tracks[j]
            rel = key_compatible(a.get("key"), b.get("key"))
            tempo_ok, half_double = tempo_compatible(
                a.get("bpm") or 0, b.get("bpm") or 0, tol
            )
            if rel and tempo_ok:
                tier = "strong"
            elif rel:
                tier = "key-only"
            elif tempo_ok:
                tier = "tempo-only"
            else:
                continue
            out.append(
                {
                    "a": a,
                    "b": b,
                    "tier": tier,
                    "key_rel": rel,
                    "tempo_gap": abs((a.get("bpm") or 0) - (b.get("bpm") or 0)),
                    "half_double": half_double,
                    "lyric_sim": None,
                }
            )
    sort_pairs(out)
    return out
