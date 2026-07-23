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
_MAJOR_DEGREES = {
    0: ("", "maj7"),
    2: ("m", "m7"),
    4: ("m", "m7"),
    5: ("", "maj7"),
    7: ("", "7"),
    9: ("m", "m7"),
}
_MINOR_DEGREES = {
    0: ("m", "m7"),
    3: ("", "maj7"),
    5: ("m", "m7"),
    7: ("m", "m7"),
    8: ("", "maj7"),
    10: ("", "7"),
}


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
