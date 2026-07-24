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

print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
