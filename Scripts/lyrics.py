#!/usr/bin/env python3
"""Best-effort lyrics fetch + a stdlib theme-similarity, for the catalog `mix`
subcommand's optional --lyrics re-rank. Deliberately isolated: every failure path
(no network, 404, timeout, bad JSON) returns None/0.0 and never raises, so the
harmonic finder keeps working when lyrics don't.

Source: LRCLIB (lrclib.net) -- free, no API key, no account. Fetched via urllib
to stay stdlib-only, cached to <MUSIC>/Samples/Lyrics/<slug>.txt so a repeat run
never hits the network. A pre-existing file there (dropped in by hand) is used
as-is, which also makes the whole feature work fully offline.
"""

from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "Samples" / "Lyrics"
_LRCLIB = "https://lrclib.net/api/get"

_WORD = re.compile(r"[a-z']+")

# An .lrc line is either a metadata tag ([ar:...], [ti:...]) or a timestamped
# lyric line. Timestamps carry 2 or 3 decimal places depending on the source.
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
            text = strip_lrc(lrc.read_text(encoding="utf-8", errors="ignore"))
            return text.strip() or None
    except OSError:
        pass
    return None


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "track"


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
    try:
        if cache.is_file():
            text = cache.read_text(encoding="utf-8").strip()
            return text or None
    except OSError:
        pass  # unreadable cache -> fall through to a fresh fetch

    q = {"track_name": title, "artist_name": artist or ""}
    url = f"{_LRCLIB}?{urllib.parse.urlencode(q)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "music-mixmatch/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (data.get("plainLyrics") or "").strip()
    except Exception:  # noqa: BLE001 -- any failure degrades to "no lyrics"
        return None
    if not text:
        return None
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
    except OSError:
        pass  # cache write is best-effort; the lyrics are still returned
    return text


def doc_words(text: str | None) -> set[str]:
    """Content words in a lyric: 3+ chars, surrounding apostrophes trimmed.

    No stopword list -- document frequency demotes function words on its own,
    and a hand-maintained list goes stale against a growing library.
    """
    if not text:
        return set()
    return {
        w for w in (m.strip("'") for m in _WORD.findall(text.lower())) if len(w) >= 3
    }


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
    a: str | None, b: str | None, df: dict[str, int], limit: int = 8
) -> list[tuple[str, int]]:
    """Words in both lyrics, rarest in the library first, with their doc counts.

    Sorting by raw document frequency is equivalent to sorting by IDF -- the log
    is monotonic -- so no document count is needed here. Ties break alphabetically.
    """
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
