#!/usr/bin/env python3
"""Independent key labels from Ultimate Guitar, for grading detect_key.

Why this exists: every label in tests/fixtures-analysis.tsv is Echo Nest-derived
(tunebat / songbpm / getsongbpm / musicstax all re-display one pipeline), so
scoring the analyzer against them measures it against a correlated copy of the
same estimation error. Ultimate Guitar's tabs are transcribed by people playing
along, which makes them wrong in *different* ways -- that independence is the
whole point, not their individual accuracy.

UG's search payload states a `tonality_name` per tab, so no chord inference is
needed. Most user tabs leave it blank; the `Official` (licensed publisher)
rows usually fill it in and usually carry zero votes, which is why a 0-vote tab
still counts as one voice below.

    .venv/bin/python Scripts/key_oracle.py fetch [--limit N] [--refresh]
    .venv/bin/python Scripts/key_oracle.py score

`fetch` walks tests/fixtures-analysis.tsv, caches one JSON per track under
Samples/KeyLabels/ (gitignored, so a re-run is offline), and writes the labels to
tests/fixtures-keys-ug.tsv. `score` reads that file and classifies each analyzer
key against it as exact / relative / adjacent / unrelated.

Caveats to keep in mind when reading a score:
  - a tab's stated tonality can be a capo or transposed key, not the record's
  - "relative" means the analyzer found the right pitch-class set and flipped
    major/minor -- a mode error, not a pitch error, and worth counting apart
  - coverage is partial; tracks with no stated tonality are reported, not guessed
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harmonic_mix  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "Samples" / "KeyLabels"
FIXTURES = ROOT / "tests" / "fixtures-analysis.tsv"
LABELS = ROOT / "tests" / "fixtures-keys-ug.tsv"
_SEARCH = "https://www.ultimate-guitar.com/search.php"

# The payload rides in a data-content attribute on the js-store div, HTML-escaped.
_STORE = re.compile(r'data-content="(.*?)"\s*>', re.S)
_TRACK_NO = re.compile(r"^\d+[- ]*")


def norm(s: str | None) -> str:
    """Canonical form for comparing artist/title strings across sources."""
    s = (s or "").lower().replace("&", "and").replace("+", "and")
    return re.sub(r"[^a-z0-9]+", "", s)


def title_variants(s: str | None) -> set[str]:
    """Every spelling a '+' or '&' title might be filed under.

    UG files "Pink + White" as "Pink Plus White", so one normalisation cannot
    match it. Spelling the separator three ways covers the observed forms.
    """
    base = (s or "").lower()
    return {
        re.sub(r"[^a-z0-9]+", "", base.replace("&", rep).replace("+", rep))
        for rep in ("and", "plus", "")
    }


def parse_results(page: str) -> list[dict]:
    """Search results out of a UG page. Never raises -- a sweep runs unattended."""
    m = _STORE.search(page or "")
    if not m:
        return []
    try:
        data = json.loads(html.unescape(m.group(1)))
    except (ValueError, TypeError):
        return []
    if not isinstance(data, dict):
        return []
    return data.get("store", {}).get("page", {}).get("data", {}).get("results") or []


def pick_tonality(results: list[dict], title: str, artist: str) -> dict | None:
    """The best-supported stated tonality for one track, or None if unstated.

    Rows are kept only when the artist AND title both match -- a cover band's
    tab of the same song is the one wrong match that would silently poison a
    label, and it can easily out-vote every real tab.

    Weight is votes + 1 so a zero-vote Official tab still counts as one voice.
    Ties break alphabetically so a re-fetch cannot reshuffle the labels.
    """
    tv, na = title_variants(title), norm(artist)
    tally: dict[str, int] = {}
    sources: dict[str, set] = {}
    for r in results:
        key = (r.get("tonality_name") or "").strip()
        if not key or norm(r.get("artist_name")) != na:
            continue
        if not title_variants(r.get("song_name")) & tv:
            continue
        tally[key] = tally.get(key, 0) + (r.get("votes") or 0) + 1
        sources.setdefault(key, set()).add(r.get("type") or "?")
    if not tally:
        return None
    ranked = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))
    best = ranked[0][0]
    return {
        "key": best,
        "weight": tally[best],
        "sources": sorted(sources[best]),
        "tally": ranked,
    }


def verdict(ours: str | None, theirs: str | None) -> str | None:
    """How the analyzer's key relates to the independent label.

    Delegates to the Camelot logic the mix report already uses, so enharmonics
    (the analyzer's G# against UG's Ab) count as one key rather than a miss.
    """
    if not ours or not theirs:
        return None
    rel = harmonic_mix.key_compatible(ours, theirs)
    if rel == "perfect":
        return "exact"
    return rel or "unrelated"


def _fetch(query: str) -> str:
    """UG's search page. Shells out to curl -- urllib gets a 404 here even with a
    browser User-Agent, and the repo already shells out for ffmpeg/afplay."""
    url = (
        _SEARCH + "?" + urllib.parse.urlencode({"search_type": "title", "value": query})
    )
    try:
        r = subprocess.run(
            ["curl", "-sS", "-m", "25", "-L", url],
            capture_output=True,
            text=True,
            timeout=40,
        )
        return r.stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def _fixture_tracks() -> list[tuple[str, str, str]]:
    """(artist, title, our_key) per fixtures row."""
    out = []
    for line in FIXTURES.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        p = Path(f[0])
        out.append(
            (
                p.parts[1] if len(p.parts) > 1 else "",
                _TRACK_NO.sub("", p.stem).strip(),
                f[2].strip() if len(f) > 2 else "",
            )
        )
    return out


def fetch(limit: int | None = None, refresh: bool = False) -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    rows = _fixture_tracks()[: limit or None]
    out = []
    for artist, title, ours in rows:
        cache = CACHE_DIR / (
            re.sub(r"[^A-Za-z0-9]+", "-", f"{artist}-{title}") + ".json"
        )
        if cache.exists() and not refresh:
            results = json.loads(cache.read_text())
        else:
            results = parse_results(_fetch(f"{artist} {title}"))
            if not results:
                results = parse_results(_fetch(title))
            cache.write_text(json.dumps(results))
            time.sleep(1.2)  # one search per ~second; this is a 13-row sweep
        pick = pick_tonality(results, title, artist)
        key = pick["key"] if pick else ""
        src = ",".join(pick["sources"]) if pick else ""
        wt = pick["weight"] if pick else 0
        out.append(f"{artist}\t{title}\t{key}\t{wt}\t{src}")
        print(
            f"  {title:24.24} {ours:>5} vs {key or '--':>5}  {verdict(ours, key) or 'no label'}"
        )
    LABELS.write_text(
        "# Independent key labels from Ultimate Guitar tab tonalities.\n"
        "# Deliberately NOT Echo Nest-derived -- see Scripts/key_oracle.py.\n"
        "# artist\ttitle\tkey\tweight\tsources\n" + "\n".join(out) + "\n"
    )
    print(f"\nwrote {LABELS.relative_to(ROOT)} ({len(out)} rows)")
    return 0


def score() -> int:
    if not LABELS.exists():
        print(f"no {LABELS.relative_to(ROOT)} -- run `key_oracle.py fetch` first")
        return 1
    ours = {norm(t): k for _, t, k in _fixture_tracks()}
    tally: dict[str, int] = {}
    print(f"{'track':24} {'ours':>5} {'UG':>6}  verdict")
    for line in LABELS.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        title, theirs = f[1], (f[2] if len(f) > 2 else "")
        mine = ours.get(norm(title), "")
        v = verdict(mine, theirs)
        tally[v or "no label"] = tally.get(v or "no label", 0) + 1
        print(f"  {title:24.24} {mine:>5} {theirs or '--':>6}  {v or 'no label'}")
    covered = sum(v for k, v in tally.items() if k != "no label")
    ex, rel = tally.get("exact", 0), tally.get("relative", 0)
    print(f"\n{tally}")
    if covered:
        print(
            f"exact {ex}/{covered} covered; {ex + rel}/{covered} share the pitch-class set"
        )
        print("(a 'relative' row is a major/minor mode flip, not a pitch error)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Independent key labels from Ultimate Guitar, for grading detect_key."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="sweep UG and write the labels file")
    f.add_argument("--limit", type=int, default=None)
    f.add_argument("--refresh", action="store_true", help="ignore the cache")
    sub.add_parser("score", help="grade detect_key against the labels")
    a = ap.parse_args()
    return fetch(a.limit, a.refresh) if a.cmd == "fetch" else score()


if __name__ == "__main__":
    sys.exit(main())
