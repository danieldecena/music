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
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "Samples" / "Lyrics"
_LRCLIB = "https://lrclib.net/api/get"

# Small stopword set -- enough to stop function words dominating the overlap
# without pulling in a dependency. Theme words are what survive.
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "if",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "at",
    "by",
    "from",
    "up",
    "out",
    "so",
    "as",
    "it",
    "its",
    "is",
    "am",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "i",
    "im",
    "you",
    "youre",
    "your",
    "me",
    "my",
    "we",
    "he",
    "she",
    "they",
    "them",
    "his",
    "her",
    "our",
    "that",
    "this",
    "these",
    "those",
    "there",
    "here",
    "what",
    "when",
    "where",
    "who",
    "how",
    "not",
    "no",
    "yeah",
    "oh",
    "na",
    "la",
    "ooh",
    "uh",
    "yo",
    "aint",
    "do",
    "dont",
    "did",
    "got",
    "get",
    "gonna",
    "wanna",
    "cause",
    "just",
    "all",
    "like",
    "can",
    "will",
    "would",
    "could",
    "know",
    "now",
    "one",
    "let",
    "go",
}
_WORD = re.compile(r"[a-z']+")


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "track"


def fetch_lyrics(artist: str | None, title: str, timeout: float = 5.0) -> str | None:
    """Plain lyrics for a track, or None. Prefers a cached/hand-dropped file;
    otherwise queries LRCLIB once and caches the result. Never raises."""
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


def theme_signature(text: str | None, top_n: int = 40) -> set[str]:
    """The top-N most frequent content words (>=3 chars, non-stopword)."""
    if not text:
        return set()
    counts: dict[str, int] = {}
    for w in _WORD.findall(text.lower()):
        w = w.strip("'")
        if len(w) >= 3 and w not in _STOPWORDS:
            counts[w] = counts.get(w, 0) + 1
    top = sorted(counts, key=lambda w: (-counts[w], w))[:top_n]
    return set(top)


def lyric_similarity(a: str | None, b: str | None) -> float:
    """Jaccard overlap of two lyric theme signatures; 0.0 if either is empty."""
    sa, sb = theme_signature(a), theme_signature(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
