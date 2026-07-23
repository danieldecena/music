#!/usr/bin/env python3
"""Fuzzy-find a track by title across the toolkit's audio + stem folders.

Lets a user type a song title (with typos) instead of dragging a path. Searches
two candidate spaces under the music root:

  * Stems/<model>/<track>/         -> the track's stem folder (preferred: has drums)
  * Apple Music|SoundCloud|Downloads/**/*.{m4a,wav,mp3,...}  -> the source file

A track present as both a stem folder and a source file collapses to one row,
keeping the stem folder (click/analyze steps want the drums stem).

stdlib only (difflib), matching chop.py / catalog.py. Ranks by a substring-first
score with a difflib fuzzy fallback so single-character typos still match.

CLI:
    find_track.py "<query>" [--root DIR] [--limit N] [--min-score F]
                            [--tsv | --json]

Default output is one candidate path per line (best first). --tsv adds
score/kind/label columns; --json emits a list of objects. Exit 0 with matches,
1 if none clear the score threshold.
"""

import argparse
import difflib
import json
import sys
from pathlib import Path

AUDIO_EXTS = {".m4a", ".wav", ".mp3", ".flac", ".aiff", ".aif", ".ogg"}
SOURCE_DIRS = ("Apple Music", "SoundCloud", "Downloads")
STEM_MODELS = ("htdemucs", "htdemucs_6s")
# stems outrank source so a track that is both collapses to its stem folder.
KIND_RANK = {"stems": 1, "source": 0}


def _norm(s: str) -> str:
    """Lowercase, keep alphanumerics and spaces, collapse runs of space."""
    kept = "".join(c if c.isalnum() else " " for c in s.lower())
    return " ".join(kept.split())


def score(query: str, label: str) -> float:
    """0..1 match of query against a candidate label.

    Substring hits win (exact 1.0, contained ~0.9 scaled by coverage); everything
    else falls back to difflib's ratio so a mistyped char still scores. The query
    is also scored against each label token and the best is taken, so "rambo"
    matches "09 Rambo" strongly rather than being diluted by the track number.
    """
    q, lab = _norm(query), _norm(label)
    if not q or not lab:
        return 0.0
    if q == lab:
        return 1.0
    best = difflib.SequenceMatcher(None, q, lab).ratio()
    if q in lab:
        best = max(best, 0.9 + 0.1 * (len(q) / len(lab)))
    for tok in lab.split():
        if q == tok:
            best = max(best, 0.97)
        elif q in tok:
            best = max(best, 0.9)
        else:
            best = max(best, difflib.SequenceMatcher(None, q, tok).ratio())
    return best


def candidates(root: Path):
    """Yield (kind, label, path) for every stem folder and source audio file."""
    for model in STEM_MODELS:
        mdir = root / "Stems" / model
        if mdir.is_dir():
            for track in sorted(mdir.iterdir()):
                if track.is_dir():
                    yield ("stems", track.name, track)
    for name in SOURCE_DIRS:
        base = root / name
        if base.is_dir():
            for f in sorted(base.rglob("*")):
                if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
                    yield ("source", f.stem, f)


def find(query: str, root: Path, limit: int, min_score: float, gap: float = 0.25):
    """Ranked, deduped matches: list of (score, kind, label, path).

    Drops the weak tail: once a strong top match exists, rows more than `gap`
    below it are cut so a picker shows a handful, not the whole library.
    """
    best: dict[str, tuple] = {}  # normalized label -> best row
    for kind, label, path in candidates(root):
        sc = score(query, label)
        if sc < min_score:
            continue
        key = _norm(label)
        row = (sc, kind, label, str(path))
        prev = best.get(key)
        if prev is None or (sc, KIND_RANK[kind]) > (prev[0], KIND_RANK[prev[1]]):
            best[key] = row
    ranked = sorted(best.values(), key=lambda r: (-r[0], r[2].lower()))
    if ranked:
        floor = ranked[0][0] - gap
        ranked = [r for r in ranked if r[0] >= floor]
    return ranked[:limit]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fuzzy-find a track by title.")
    ap.add_argument("query")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--min-score", type=float, default=0.34)
    out = ap.add_mutually_exclusive_group()
    out.add_argument(
        "--tsv", action="store_true", help="score<TAB>kind<TAB>label<TAB>path"
    )
    out.add_argument("--json", action="store_true")
    ns = ap.parse_args(argv)

    rows = find(ns.query, Path(ns.root).expanduser(), ns.limit, ns.min_score)
    if not rows:
        return 1
    if ns.json:
        print(
            json.dumps(
                [
                    {"score": round(s, 4), "kind": k, "label": lb, "path": p}
                    for s, k, lb, p in rows
                ]
            )
        )
    elif ns.tsv:
        for s, k, lb, p in rows:
            print(f"{s:.4f}\t{k}\t{lb}\t{p}")
    else:
        for row in rows:
            print(row[3])
    return 0


if __name__ == "__main__":
    sys.exit(main())
