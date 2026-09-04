"""Score musically-aligned spans of a track.

The song database holds beats, bars, structure boundaries and a continuous
instrument-activity signal. Every product this repo wants is a ranked selection
over that: a loop to flip, a clean span to sample, a hook to clip, a safe point
to cut between two tracks. They share one shape -- a scored, bar-aligned span --
so they share one table (`regions`) and one scorer interface.

This module currently implements the `loop` kind. A new product is a new kind
and a new scorer here, not a schema change.

Stdlib only.
"""

# A window that sits inside one structural section beats one that straddles a
# boundary: a loop crossing a section usually changes underneath the bar it
# repeats. Not a veto -- a straddling window with silent vocals can still be
# the best thing in a track -- so this is a multiplier, not a filter.
STRADDLE_PENALTY = 0.75

# The instrument whose absence defines a "clean" sampling span. Apple reports
# bass / drum / other / vocal, the same taxonomy demucs uses.
CLEAN_OF = "vocal"


def _mean_levels(activity, start, end):
    """Duration-weighted mean level per instrument over [start, end).

    Weighted rather than a plain average because the activity rows are sample
    intervals: an unweighted mean would let a run of short rows outvote a long
    one covering most of the span.
    """
    num, den = {}, {}
    for a in activity:
        lo = max(a["start_s"], start)
        hi = min(a["end_s"], end)
        w = hi - lo
        if w <= 0:
            # A zero-length row still carries a reading; give it minimal weight
            # rather than dropping it, or a sparse signal scores as absent.
            if not (start <= a["start_s"] < end):
                continue
            w = 1e-9
        inst = a["instrument"]
        num[inst] = num.get(inst, 0.0) + a["level"] * w
        den[inst] = den.get(inst, 0.0) + w
    return {k: num[k] / den[k] for k in num if den[k] > 0}


def _contained(sections, start, end):
    """True if some section fully contains [start, end)."""
    return any(
        s["start_s"] <= start and end <= s["end_s"]
        for s in sections
        if s.get("label", "section") == "section"
    )


def score_loops(beats, bars, sections, activity, n_bars=4):
    """Rank every n_bars-long, bar-aligned window of a track.

    Returns a list of dicts with start_s, end_s, start_bar, n_bars, score and
    instruments (mean level per instrument over the span). Score is
    (1 - mean vocal activity) times a section-containment multiplier, so it
    rises as the span gets cleaner and as it sits more squarely inside one
    section. Empty list when there are not enough bars for one window.
    """
    ordered = sorted(bars, key=lambda b: b["t"])
    if len(ordered) <= n_bars:
        return []

    out = []
    for i in range(len(ordered) - n_bars):
        start = ordered[i]["t"]
        end = ordered[i + n_bars]["t"]
        levels = _mean_levels(activity, start, end)
        clean = 1.0 - levels.get(CLEAN_OF, 0.0)
        mult = 1.0 if _contained(sections, start, end) else STRADDLE_PENALTY
        out.append(
            {
                "start_s": start,
                "end_s": end,
                "start_bar": ordered[i].get("idx", i),
                "n_bars": n_bars,
                "score": clean * mult,
                "instruments": levels,
            }
        )
    return out
