#!/usr/bin/env python3
"""Render ranked mix pairs as a report -- text for a human, a dict for JSON.

Pure: no database, no filesystem, no network. Takes the pair dicts rank_pairs
already produces and turns them into something you can act on.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402
import harmonic_mix  # noqa: E402

MAX_NEAR_MISSES = 3


def track_label(t: dict) -> str:
    who = f"{t['artist']} — " if t.get("artist") else ""
    return f"{who}{catalog.song_title(t['name'])} ({t['key']}/{t['bpm']:g})"


def why_line(pair: dict) -> str:
    """Why the pair works, tempo first.

    Tempo is the trustworthy half of the analysis; key detection scores 2/13
    exact against published labels. Leading with key would project confidence
    the estimate does not earn, so the key claim trails and is hedged.
    """
    if pair["half_double"]:
        tempo = "half/double time — one plays at twice the other's pulse, 0 BPM apart once folded"
    else:
        gap = pair["tempo_gap"]
        tempo = (
            f"{gap:g} BPM apart — straight beatmatch, no pitch-fader work"
            if gap <= 1
            else f"{gap:g} BPM apart — inside pitch-fader range"
        )
    rel = pair["key_rel"]
    if not rel:
        return f"{tempo}. Keys are unrelated, so mix on the drums."
    ca = harmonic_mix.key_to_camelot(pair["a"]["key"])
    cb = harmonic_mix.key_to_camelot(pair["b"]["key"])
    wheel = f" ({ca} -> {cb})" if ca and cb else ""
    return f"{tempo}. Keys read as {rel}{wheel} — confirm by ear."


def near_misses(
    seed: dict, tracks: list[dict], tol: float, limit: int = MAX_NEAR_MISSES
):
    """Key-compatible tracks the tempo rules out, closest first.

    A seed with no compatible partner should say why nothing came back, not
    return an empty list and leave the user guessing.
    """
    out = []
    for t in tracks:
        if t.get("name") == seed.get("name"):
            continue
        rel = harmonic_mix.key_compatible(seed.get("key"), t.get("key"))
        ok, _ = harmonic_mix.tempo_compatible(
            seed.get("bpm") or 0, t.get("bpm") or 0, tol
        )
        if rel and not ok:
            out.append(
                {
                    "track": t,
                    "key_rel": rel,
                    "tempo_gap": abs((seed.get("bpm") or 0) - (t.get("bpm") or 0)),
                }
            )
    out.sort(key=lambda m: m["tempo_gap"])
    return out[:limit]


def build_report(
    seed: dict, pairs: list[dict], words_by_pair: dict, misses: list[dict]
) -> dict:
    """The report as plain data -- render_text and --json both read this."""
    return {
        "seed": seed,
        "verdict": pairs[0] if pairs else None,
        "pairs": [
            {
                "a": p["a"],
                "b": p["b"],
                "tier": p["tier"],
                "key_rel": p["key_rel"],
                "tempo_gap": p["tempo_gap"],
                "half_double": p["half_double"],
                "why": why_line(p),
                "shared_words": [list(w) for w in words_by_pair.get(id(p), [])],
            }
            for p in pairs
        ],
        "near_misses": [
            {"track": m["track"], "key_rel": m["key_rel"], "tempo_gap": m["tempo_gap"]}
            for m in misses
        ],
    }


def render_text(report: dict) -> str:
    seed = report["seed"]
    lines = [f"Seed: {track_label(seed)}", ""]
    if not report["pairs"]:
        lines.append(
            "No compatible partner in the catalog — nothing matched on key or tempo."
        )
    else:
        top = report["pairs"][0]
        lines += [
            f"Best mix: {track_label(top['a'])}  x  {track_label(top['b'])}",
            f"  {top['why']}",
        ]
        if top["shared_words"]:
            lines.append(
                "  Shared words (rarest first): "
                + ", ".join(w for w, _ in top["shared_words"])
            )
        if len(report["pairs"]) > 1:
            lines += ["", "Also compatible:"]
            for p in report["pairs"][1:]:
                lines.append(f"  {track_label(p['b'])}  —  {p['why']}")
    if report["near_misses"]:
        lines += ["", "Near misses (key works, tempo does not):"]
        for m in report["near_misses"]:
            lines.append(
                f"  {track_label(m['track'])}  —  {m['key_rel']} key, "
                f"{m['tempo_gap']:g} BPM away"
            )
    return "\n".join(lines)
