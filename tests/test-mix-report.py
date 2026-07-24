#!/usr/bin/env python3
"""
Tests for the seed-pivot mix report -- lyric sourcing, IDF word ranking, the
report renderer, and the preview command builder. Hand-rolled assertions in the
style of tests/test-harmonic-mix.py. Pure stdlib; run with any python3:

    python3 tests/test-mix-report.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import lyrics as ly  # noqa: E402

_passed = 0
_failed = 0


def check(cond: bool, label: str) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        print(f"FAIL: {label}")


LRC = """[ar:Justin Bieber]
[ti:SPEED DEMON]
[00:12.34]And I go speed racing
[00:14.50]Speed demon, speed demon
[00:16.00]
[01:02.5]Faster than the rest
"""

plain = ly.strip_lrc(LRC)
check("speed racing" in plain, "strip_lrc keeps the lyric text")
check("[00:12.34]" not in plain, "strip_lrc removes timestamps")
check(
    "[ar:" not in plain and "Justin Bieber" not in plain,
    "strip_lrc drops metadata lines",
)
check("" not in plain.splitlines(), "strip_lrc drops blank lines")
check(
    len(plain.splitlines()) == 3,
    f"strip_lrc keeps 3 lyric lines, got {plain.splitlines()}",
)

# A file with no timestamps at all is already plain text -- pass it through.
check(
    ly.strip_lrc("just a line\nand another") == "just a line\nand another",
    "strip_lrc passes through untimestamped text",
)
check(ly.strip_lrc("") == "", "strip_lrc handles empty input")

# local_lyrics: reads the sidecar beside the audio file, None when absent.
check(ly.local_lyrics(None) is None, "local_lyrics(None) is None")
check(
    ly.local_lyrics("Apple Music/Nope/Does Not Exist.m4a") is None,
    "local_lyrics returns None for a missing sidecar",
)

# --- IDF word ranking -------------------------------------------------------

DOCS = [
    "speed racing faster than the rest you know",
    "the speed boat and you",
    "love you baby the",
    "love the night you",
    "hello the you",
]
df, n = ly.word_index(DOCS)
check(n == 5, f"word_index counts 5 documents, got {n}")
check(df["the"] == 5, f"'the' appears in every doc, got {df.get('the')}")
check(df["speed"] == 2, f"'speed' appears in 2 docs, got {df.get('speed')}")
check("of" not in df, "words under 3 chars are dropped")

# Shared words come back rarest-first, so a word appearing everywhere sorts last.
sw = ly.shared_words(DOCS[0], DOCS[1], df)
words = [w for w, _ in sw]
check(words[0] == "speed", f"rarest shared word first, got {words}")
# 'the' and 'you' both appear in all 5 docs, so they tie and break alphabetically;
# what matters is that both sort behind the rare word.
check(set(words[1:]) == {"the", "you"}, f"common words trail the rare one, got {words}")
check([c for _, c in sw] == sorted(c for _, c in sw), f"counts ascend, got {sw}")
check(all(isinstance(c, int) for _, c in sw), "shared_words carries doc frequencies")
check(
    len(ly.shared_words(DOCS[0], DOCS[1], df, limit=1)) == 1,
    "shared_words honors limit",
)
check(ly.shared_words("", DOCS[1], df) == [], "shared_words on empty lyrics is empty")

# IDF similarity: sharing a rare word beats sharing a common one.
rare = ly.lyric_similarity("speed racing", "speed boat", df, n)
common = ly.lyric_similarity("the night", "the rest", df, n)
check(
    rare > common, f"rare overlap outranks common overlap ({rare:.3f} vs {common:.3f})"
)
check(ly.lyric_similarity(None, "x", df, n) == 0.0, "similarity with no lyrics is 0.0")
check(ly.lyric_similarity("a b c", "d e f", df, n) == 0.0, "no overlap scores 0.0")

# Called without an index it must still work -- _lyric_rerank has no corpus.
check(
    0.0 <= ly.lyric_similarity("love you baby", "love you") <= 1.0,
    "similarity without an index stays in range",
)

# --- report rendering -------------------------------------------------------

import mix_report as mr  # noqa: E402

SEED = {"name": "03 YUKON", "artist": "Justin Bieber", "bpm": 128, "key": "Dm"}
OTHER = {"name": "06 Skyline To", "artist": "Frank Ocean", "bpm": 129, "key": "F"}
PAIR = {
    "a": SEED,
    "b": OTHER,
    "tier": "strong",
    "key_rel": "relative",
    "tempo_gap": 1,
    "half_double": False,
    "lyric_sim": 0.04,
}

check(
    mr.track_label(SEED) == "Justin Bieber — YUKON (Dm/128)",
    f"track_label drops the track number, got {mr.track_label(SEED)!r}",
)

why = mr.why_line(PAIR)
check(
    why.lower().index("bpm") < why.lower().index("key"),
    f"tempo fact precedes the key claim: {why!r}",
)
check("confirm by ear" in why, f"key claim carries its hedge: {why!r}")
check("relative" in why, f"key relation is named: {why!r}")

# A half/double pair must say so rather than reporting a huge tempo gap.
HALF = dict(
    PAIR,
    half_double=True,
    tempo_gap=64,
    b={"name": "x", "artist": "y", "bpm": 64, "key": "F"},
)
check(
    "half" in mr.why_line(HALF).lower(), f"half/double is named: {mr.why_line(HALF)!r}"
)

# Near-misses explain an empty result instead of returning nothing.
LONE = {"name": "1-01 SPEED DEMON", "artist": "Justin Bieber", "bpm": 92.7, "key": "Dm"}
misses = mr.near_misses(LONE, [OTHER], tol=0.06)
check(
    len(misses) == 1,
    f"a key-compatible but tempo-far track is a near miss, got {misses}",
)
check(misses[0]["track"]["name"] == "06 Skyline To", "near miss names the track")
check(mr.near_misses(LONE, [], tol=0.06) == [], "no candidates -> no near misses")
check(len(mr.near_misses(LONE, [OTHER] * 9, tol=0.06)) == 3, "near misses cap at 3")

report = mr.build_report(SEED, [PAIR], {id(PAIR): [("speed", 4), ("fast", 4)]}, [])
check(report["seed"]["name"] == "03 YUKON", "report carries the seed")
check(report["verdict"]["b"]["name"] == "06 Skyline To", "verdict names the winner")
check(
    report["pairs"][0]["shared_words"] == [["speed", 4], ["fast", 4]],
    f"shared words are JSON-ready lists, got {report['pairs'][0]['shared_words']}",
)

text = mr.render_text(report)
check("Best mix:" in text, f"text names a winner: {text!r}")
check("speed" in text, "text lists the shared words")

# No pairs at all must still produce readable output, not an empty string.
empty = mr.render_text(mr.build_report(SEED, [], {}, []))
check(
    "no" in empty.lower() and len(empty) > 10,
    f"empty report explains itself: {empty!r}",
)

# --- preview command builder ------------------------------------------------

import mix_preview as mp  # noqa: E402

check(
    abs(mp.atempo_ratio(128, 129) - 0.99224) < 0.0001,
    f"ratio is a_bpm/b_bpm, got {mp.atempo_ratio(128, 129)}",
)
check(mp.atempo_ratio(128, 64) == 1.0, "a double-time partner folds to 1.0")
check(0.5 <= mp.atempo_ratio(160, 40) <= 2.0, "extreme ratios fold into atempo's range")
check(0.5 <= mp.atempo_ratio(40, 160) <= 2.0, "extreme ratios fold from below too")
check(mp.atempo_ratio(0, 128) == 1.0, "a zero BPM degrades to no stretch")

# Start at a section boundary when the analyzer found one, else 25% in.
check(
    mp.excerpt_start([30.0, 60.0, 90.0], 200.0) == 30.0, "first usable transition wins"
)
check(mp.excerpt_start([], 200.0) == 50.0, "no transitions -> 25% into the track")
check(
    mp.excerpt_start([190.0], 200.0) == 50.0,
    "a transition too close to the end is skipped",
)

args = mp.preview_args("A.m4a", "B.m4a", 0.99224, "/tmp/p.wav", 40.0, 30.0)
check("-vn" in args, "preview_args passes -vn (Apple Music files carry cover art)")
check(args[0] == "ffmpeg", "preview_args builds an ffmpeg command")
check("atempo=0.992240" in " ".join(args), f"atempo ratio is in the filter: {args}")
check("acrossfade=d=8" in " ".join(args), "crossfade duration is set")
check(args[-1] == "/tmp/p.wav", "output path is last")
check(args.count("-i") == 2, "two inputs")

print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
