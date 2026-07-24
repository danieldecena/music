#!/usr/bin/env python3
"""
Tests for the Ultimate Guitar key oracle -- payload parsing, title matching, and
tonality selection. Hand-rolled assertions in the style of the other test files.
Pure stdlib and fully offline: every test feeds canned payloads, so the suite
never touches the network. Run with any python3:

    python3 tests/test-key-oracle.py
"""

import html
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import key_oracle as ko  # noqa: E402

_passed = 0
_failed = 0


def check(cond: bool, label: str) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        print(f"FAIL: {label}")


# --- title normalisation ----------------------------------------------------

# UG spells the same song several ways. "Pink + White" is filed as "Pink Plus
# White", so a single normalisation cannot match it -- the variant set is why
# that track is covered at all.
check(
    ko.norm("Pink + White") == "pinkandwhite",
    f"norm folds '+', got {ko.norm('Pink + White')!r}",
)
check(ko.norm("Don't") == "dont", "norm drops apostrophes")
check(ko.norm("  The Color Violet ") == "thecolorviolet", "norm strips and lowercases")

v = ko.title_variants("Pink + White")
check("pinkpluswhite" in v, f"'+' spells out as 'plus', got {sorted(v)}")
check("pinkandwhite" in v, f"'+' also spells out as 'and', got {sorted(v)}")
check("pinkwhite" in v, f"'+' also drops entirely, got {sorted(v)}")
check(ko.title_variants("Ivy") == {"ivy"}, "a plain title has one variant")

# --- payload parsing --------------------------------------------------------

RESULTS = [
    {
        "artist_name": "Frank Ocean",
        "song_name": "Ivy",
        "type": "Chords",
        "tonality_name": "C",
        "votes": 1025,
    },
    {
        "artist_name": "Frank Ocean",
        "song_name": "Ivy",
        "type": "Official",
        "tonality_name": "C",
        "votes": 0,
    },
    {
        "artist_name": "Frank Ocean",
        "song_name": "Ivy",
        "type": "Tabs",
        "tonality_name": "",
        "votes": 400,
    },
    {
        "artist_name": "Frank Ocean",
        "song_name": "Ivy",
        "type": "Chords",
        "tonality_name": "Am",
        "votes": 12,
    },
    {
        "artist_name": "Some Cover Band",
        "song_name": "Ivy",
        "type": "Chords",
        "tonality_name": "G",
        "votes": 9000,
    },
]
PAGE = (
    '<html><body><div class="js-store" data-content="'
    + html.escape(
        json.dumps({"store": {"page": {"data": {"results": RESULTS}}}}), quote=True
    )
    + '"></div></body></html>'
)

parsed = ko.parse_results(PAGE)
check(len(parsed) == 5, f"parse_results reads every row, got {len(parsed)}")
check(parsed[0]["tonality_name"] == "C", "parse_results decodes the escaped JSON")
check(
    ko.parse_results("<html>no store here</html>") == [], "a page with no store -> []"
)
check(ko.parse_results("") == [], "empty page -> []")
# A truncated payload must degrade, not raise -- this runs unattended in a sweep.
check(ko.parse_results('<div data-content="{not json"></div>') == [], "bad JSON -> []")

# --- tonality selection -----------------------------------------------------

pick = ko.pick_tonality(RESULTS, "Ivy", "Frank Ocean")
check(pick is not None, "a covered track resolves")
check(pick["key"] == "C", f"the most-voted tonality wins, got {pick['key']!r}")
check(
    "Official" in pick["sources"], f"sources name the tab types, got {pick['sources']}"
)

# The cover band is louder than every real tab combined and must not count --
# a wrong-artist match is the one failure that would silently poison a label.
check(
    "G" not in [c[0] for c in pick["tally"]],
    f"other artists are excluded: {pick['tally']}",
)

# Blank tonality is the common case on UG; those tabs carry no signal.
blank = [dict(r, tonality_name="") for r in RESULTS]
check(
    ko.pick_tonality(blank, "Ivy", "Frank Ocean") is None, "no stated tonality -> None"
)
check(ko.pick_tonality([], "Ivy", "Frank Ocean") is None, "no results -> None")

# A 0-vote Official tab still counts as one voice -- publisher transcriptions are
# the most authoritative rows UG has and they routinely carry no votes at all.
solo = [
    {
        "artist_name": "Frank Ocean",
        "song_name": "Solo",
        "type": "Official",
        "tonality_name": "Eb",
        "votes": 0,
    }
]
p2 = ko.pick_tonality(solo, "Solo", "Frank Ocean")
check(
    p2 is not None and p2["key"] == "Eb",
    f"a 0-vote Official tab still resolves, got {p2}",
)

# Matching is artist+title, both normalised, so the variant spelling resolves.
pw = [
    {
        "artist_name": "Frank Ocean",
        "song_name": "Pink Plus White",
        "type": "Tabs",
        "tonality_name": "A",
        "votes": 5,
    }
]
p3 = ko.pick_tonality(pw, "Pink + White", "Frank Ocean")
check(
    p3 is not None and p3["key"] == "A",
    f"'Pink + White' matches 'Pink Plus White', got {p3}",
)

# Ties must not depend on dict ordering, or a re-run reshuffles the labels.
tie = [
    {
        "artist_name": "A",
        "song_name": "T",
        "type": "Chords",
        "tonality_name": "F#",
        "votes": 0,
    },
    {
        "artist_name": "A",
        "song_name": "T",
        "type": "Chords",
        "tonality_name": "C#m",
        "votes": 0,
    },
]
check(
    ko.pick_tonality(tie, "T", "A")["key"] == "C#m",
    "a tie breaks alphabetically, not by order",
)
check(
    ko.pick_tonality(list(reversed(tie)), "T", "A")["key"] == "C#m",
    "...and the reverse agrees",
)

# --- verdicts ---------------------------------------------------------------

# Enharmonic spellings are the same key -- UG writes Ab where the analyzer
# writes G#, and calling that a miss would understate the analyzer badly.
check(ko.verdict("G#", "Ab") == "exact", "G# and Ab are one key")
check(ko.verdict("C", "C") == "exact", "identical keys are exact")
check(ko.verdict("Am", "C") == "relative", "relative major/minor is named as such")
check(ko.verdict("F#m", "Bm") == "adjacent", "a wheel step is adjacent")
check(ko.verdict("F#", "C#m") == "unrelated", "an unrelated pair says so")
check(ko.verdict("C", None) is None, "a missing label has no verdict")
check(ko.verdict("C", "") is None, "a blank label has no verdict")

print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
