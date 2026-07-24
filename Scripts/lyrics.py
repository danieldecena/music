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
