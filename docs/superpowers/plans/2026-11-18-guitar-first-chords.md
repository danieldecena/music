# Guitar-First Chords Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command turns a song into a Chordbook chart built from Logic's Chord ID on the guitar part, filled from the full mix where the guitar rests, and publishes it to the phone.

**Architecture:** A pure Python script (`Scripts/combine_charts.py`) merges a guitar-only chart into the song's full-mix chart. A new core function `guitar_chords` in `lib/music-core.sh` chains the existing pieces: the full-mix Logic chart (`logic_chords`), the 6-stem split (`separate_stems`), a Logic run on the guitar stem, the merge, and Chordbook's publish script. The menu gets one new Tools key. Nothing about how Logic is driven changes: both Logic runs use the semi-manual mode (`--manual`, Daniel clicks the region and presses Ctrl-Opt-Shift-Cmd-C), because the scripted press is unreliable (STATUS.md, Known broken, 2026-11-18).

**Tech Stack:** zsh (`lib/music-core.sh`, `music`), Python 3 stdlib (`Scripts/combine_charts.py`), hand-rolled test files (`tests/test-*.py`, `tests/test-core.sh`).

**Spec:** No separate spec. This plan writes down the routine done by hand on 2026-11-18 for WALKING AWAY, whose result Daniel accepted ("combined chart"): STATUS.md Known broken entry, and this session's findings below.

## Background (what was learned by hand)

- Logic's Chord ID on the **full mix** read WALKING AWAY as D#maj7 / F; on the **guitar stem alone** (Demucs `htdemucs_6s`, `guitar.wav`) it read plain D# / F / A# power chords. The two agreed on 36 of 89 bars. Daniel said the full-mix chart "doesn't sound good".
- The guitar-only chart has 12 bars of `-` where the guitar rests. The accepted chart uses the guitar chord for every bar the guitar plays (with its `N.3` beat-3 changes), and the full-mix chord for `-` bars, with D#maj7 written as plain D# because the guitar plays plain D#.
- The accepted chart kept the full-mix chart's tempo line (87.99 BPM, start 0.313 s), not the guitar run's (88.04 BPM, start 0.114 s). Whether the guitar's start is better is not known yet; keep the full-mix tempo line until Daniel says otherwise.
- `Scripts/logic_chords.py` already spells Logic's power chords ("e flat 5") as plain names (commit 0b31db8).
- The hand-made result is in `Apple Music/Justin Bieber/SWAG/10 WALKING AWAY chords.txt`; the full-mix chart is kept beside it as `10 WALKING AWAY chords (mix).txt`. That pair is the control for Task 4.

## Global Constraints

- Python: the repo's `.venv/bin/python` for anything that imports numpy; stdlib-only scripts may use `/opt/homebrew/bin/python3`. Never bare `python3`.
- Never duplicate logic into a wrapper (`music`, `*.sh`): logic lives in `lib/music-core.sh` (repo CLAUDE.md, "Core/wrapper split").
- Chart format: `# Chords -- <title>` line, `# key <K>  <BPM> BPM  <N> bars[  start <s> s]` line, a source line, then `<bar><TAB><chord>` per bar with optional `<bar>.3<TAB><chord>` right after its bar. Sharps only (`D#`, not `Eb`).
- Logic is opened only by `Scripts/logic_chords.py`, only when no Logic is running, always with `--manual` in this feature.
- Commits: imperative subject, reasoning in body, end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, explicit pathspec, never `--no-verify`.
- No emoji, no em dashes in code, comments, docs or output.

## File Structure

- Create `Scripts/combine_charts.py`: the merge (pure function `combine`) plus a CLI that keeps the old chart as `<name> chords (mix).txt` and writes the merged chart in its place. One responsibility: chart text in, chart text out.
- Create `tests/test-combine-charts.py`: hand-rolled tests for `combine` and the CLI, same style as `tests/test-logic-chords.py`.
- Modify `lib/music-core.sh`: add `guitar_chords()` after `logic_chords()`.
- Modify `tests/test-core.sh`: refusal tests for `guitar_chords`, after the `logic_chords` block.
- Modify `music`: Tools menu key `J) Guitar-first chords`.
- Modify `CLAUDE.md` (repo): one bullet for `guitar_chords` and the menu key list.

---

### Task 1: The chart merge

**Files:**
- Create: `Scripts/combine_charts.py`
- Test: `tests/test-combine-charts.py`

**Interfaces:**
- Produces: `combine(guitar: str, mix: str) -> str` (both arguments and the result are whole chart texts); CLI `combine_charts.py "<guitar chart>" "<song chart>"`, exit 0 after writing, exit 1 with a reason when either file is missing or the bar counts differ. Constant `GUITAR_NOTE`.

Rules `combine` must follow:
1. Header: every `#` line of `mix`, in order, except its source line (starting `# chords from`), which becomes `GUITAR_NOTE`.
2. For each bar number in `mix`, in order: if the guitar chart has a chord other than `-` for that bar, write the guitar's bar line, then the guitar's `N.3` line for that bar if it has one and it is not `-`.
3. Otherwise write the mix's bar line and its `N.3` line if any, each passed through the root rule.
4. Root rule: a fallback chord whose root (`[A-G]#?` at the start) the guitar plays somewhere is replaced by the guitar's most-used chord with that root. A root the guitar never plays keeps the mix's chord. `-` stays `-`.

- [ ] **Step 1: Write the failing tests**

```python
#!/usr/bin/env python3
"""
Tests for Scripts/combine_charts.py: a guitar-only chart merged into the song's full-mix chart.
Hand-rolled assertions, stdlib only:

    /opt/homebrew/bin/python3 tests/test-combine-charts.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import combine_charts as cc

_passed = 0
_failed = 0


def check(cond: bool, what: str) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"ok: {what}")
    else:
        _failed += 1
        print(f"FAIL: {what}")


MIX = """# Chords -- 10 WALKING AWAY.m4a
# key F  87.99 BPM  4 bars  start 0.313 s
# chords from Logic Pro Chord ID
1\tD#maj7
2\tF
2.3\tD#maj7
3\tGm7
4\tD#maj7
"""

GUITAR = """# Chords -- 10 WALKING AWAY.m4a
# key F  88.04 BPM  4 bars  start 0.114 s
# chords from Logic Pro Chord ID
1\tD#
1.3\tF
2\t-
3\t-
4\tD#
"""

out = cc.combine(GUITAR, MIX).splitlines()

check(out[0] == "# Chords -- 10 WALKING AWAY.m4a", "title line comes from the mix chart")
check(out[1] == "# key F  87.99 BPM  4 bars  start 0.313 s", "tempo line comes from the mix chart")
check(out[2] == cc.GUITAR_NOTE, "source line says guitar first, mix where it rests")
check(out[2].startswith("# chords from Logic Pro Chord ID"), "source line still marks a Logic chart")
check(out[3:5] == ["1\tD#", "1.3\tF"], "a guitar bar keeps its chord and its beat-3 change")
check(out[5:7] == ["2\tF", "2.3\tD#"], "a rest bar takes the mix chord; D#maj7 becomes the guitar's D#")
check(out[7] == "3\tGm7", "a root the guitar never plays keeps the mix chord")
check(out[8] == "4\tD#", "the guitar chord wins over the mix chord")
check(len(out) == 9, "no extra lines")

check(cc.root("D#maj7") == "D#", "root of D#maj7")
check(cc.root("Gm7/D") == "G", "root of a slash chord")
check(cc.root("-") == "", "no-chord has no root")

# The CLI keeps the old chart once and refuses charts of different lengths.
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp)
    song = t / "10 WALKING AWAY chords.txt"
    guitar = t / "10 WALKING AWAY guitar chords.txt"
    song.write_text(MIX)
    guitar.write_text(GUITAR)
    script = str(REPO / "Scripts/combine_charts.py")
    r = subprocess.run([sys.executable, script, str(guitar), str(song)], capture_output=True, text=True)
    check(r.returncode == 0, f"CLI writes the merged chart (stderr {r.stderr.strip()!r})")
    check((t / "10 WALKING AWAY chords (mix).txt").read_text() == MIX, "CLI keeps the old chart as (mix)")
    check(song.read_text() == cc.combine(GUITAR, MIX), "CLI writes combine()'s result")
    r = subprocess.run([sys.executable, script, str(guitar), str(song)], capture_output=True, text=True)
    check((t / "10 WALKING AWAY chords (mix).txt").read_text() == MIX, "a second run does not overwrite (mix)")
    guitar.write_text(GUITAR.replace("4 bars", "5 bars") + "5\tF\n")
    r = subprocess.run([sys.executable, script, str(guitar), str(song)], capture_output=True, text=True)
    check(r.returncode == 1, "CLI refuses charts with different bar counts")
    check("bars" in r.stdout + r.stderr, "and says it is the bar count")

print(f"\n{_passed} passed, {_failed} failed")
sys.exit(1 if _failed else 0)
```

Note on the second-run check: after the first run the song chart is already merged, so the guard that protects `(mix)` is "write it only if it does not exist yet".

- [ ] **Step 2: Run the tests to see them fail**

Run: `/opt/homebrew/bin/python3 tests/test-combine-charts.py`
Expected: `ModuleNotFoundError: No module named 'combine_charts'`

- [ ] **Step 3: Write the implementation**

```python
#!/opt/homebrew/bin/python3
"""Merge a guitar-only chart into a song's full-mix chart.

Logic's Chord ID on the guitar stem names what the guitar plays (WALKING AWAY: plain D#, F, A#)
where the full mix adds colour the guitar does not play (D#maj7). The guitar chart is used for
every bar the guitar plays; bars where it rests ("-") take the full-mix chord, spelled the way
the guitar spells that root elsewhere. The tempo line stays the full-mix chart's.

Usage: combine_charts.py "<name> guitar chords.txt" "<name> chords.txt"
The song's chart is kept as "<name> chords (mix).txt" the first time, then rewritten.
"""

import re
import sys
from collections import Counter
from pathlib import Path

GUITAR_NOTE = "# chords from Logic Pro Chord ID: the guitar part, the full mix where the guitar rests"
_BAR = re.compile(r"(\d+)\t(\S+)")
_MID = re.compile(r"(\d+)\.3\t(\S+)")


def root(chord: str) -> str:
    m = re.match(r"[A-G]#?", chord)
    return m.group(0) if m else ""


def _parse(text: str) -> tuple[list[str], dict[int, str], dict[int, str]]:
    header, bars, mids = [], {}, {}
    for line in text.splitlines():
        if line.startswith("#"):
            header.append(line)
        elif m := _BAR.fullmatch(line):
            bars[int(m.group(1))] = m.group(2)
        elif m := _MID.fullmatch(line):
            mids[int(m.group(1))] = m.group(2)
    return header, bars, mids


def combine(guitar: str, mix: str) -> str:
    _, g_bars, g_mids = _parse(guitar)
    header, m_bars, m_mids = _parse(mix)
    played = [c for c in list(g_bars.values()) + list(g_mids.values()) if c != "-"]
    by_root = {}
    for chord, _ in Counter(played).most_common():
        by_root.setdefault(root(chord), chord)

    def fallback(chord: str) -> str:
        return by_root.get(root(chord), chord) if chord != "-" else chord

    lines = [GUITAR_NOTE if h.startswith("# chords from") else h for h in header]
    for bar in sorted(m_bars):
        if g_bars.get(bar, "-") != "-":
            lines.append(f"{bar}\t{g_bars[bar]}")
            if g_mids.get(bar, "-") != "-":
                lines.append(f"{bar}.3\t{g_mids[bar]}")
        else:
            lines.append(f"{bar}\t{fallback(m_bars[bar])}")
            if bar in m_mids:
                lines.append(f"{bar}.3\t{fallback(m_mids[bar])}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 1
    guitar, song = (Path(a) for a in argv)
    for p in (guitar, song):
        if not p.is_file():
            print(f"No chart at {p}")
            return 1
    g_text, s_text = guitar.read_text(), song.read_text()
    g_n, s_n = len(_parse(g_text)[1]), len(_parse(s_text)[1])
    if g_n != s_n:
        print(f"The guitar chart has {g_n} bars and the song chart {s_n} bars; nothing written.")
        return 1
    backup = song.with_name(song.name.replace(" chords.txt", " chords (mix).txt"))
    if not backup.exists():
        backup.write_text(s_text)
    song.write_text(combine(g_text, s_text))
    print(f"Wrote {song.name} (guitar first); the full-mix chart is {backup.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `/opt/homebrew/bin/python3 tests/test-combine-charts.py`
Expected: last line `18 passed, 0 failed`, exit 0.

Then prove the root-rule test can fail: temporarily change `fallback` to `return chord`, rerun, expect the line `FAIL: a rest bar takes the mix chord; D#maj7 becomes the guitar's D#`, then restore.

- [ ] **Step 5: Check against the hand-made WALKING AWAY chart**

```bash
cd ~/developer/music
/opt/homebrew/bin/python3 -c '
import sys; sys.path.insert(0, "Scripts"); import combine_charts as cc
from pathlib import Path
d = Path("Apple Music/Justin Bieber/SWAG")
g = Path("Stems/guitar-check/10 WALKING AWAY guitar chords.txt").read_text()
m = (d / "10 WALKING AWAY chords (mix).txt").read_text()
print(cc.combine(g, m) == (d / "10 WALKING AWAY chords.txt").read_text())'
```

Expected: `True` (the script reproduces the chart Daniel accepted). If `False`, diff the two before going on; a difference is either a rule this plan got wrong or a hand-made mistake, and the hand-made one is the one Daniel heard.

- [ ] **Step 6: Commit**

```bash
git add Scripts/combine_charts.py tests/test-combine-charts.py
git commit -m "Add the guitar-first chart merge" -m "Logic's Chord ID on the guitar stem names what the guitar plays; the full mix fills the bars where it rests. Reproduces the WALKING AWAY chart accepted on 2026-11-18." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- Scripts/combine_charts.py tests/test-combine-charts.py
```

---

### Task 2: The `guitar_chords` core function

**Files:**
- Modify: `lib/music-core.sh` (add after the closing `}` of `logic_chords()`, around line 310)
- Test: `tests/test-core.sh` (add before the final `exit $fail`)

**Interfaces:**
- Consumes: `logic_chords "<audio>"` (existing, publishes at the end), `separate_stems "<audio>" 6stem "<out>"` (existing), `Scripts/logic_chords.py --manual "<audio>"` (existing), `Scripts/combine_charts.py` (Task 1), `SOURCE_NOTE` text `# chords from Logic Pro Chord ID`.
- Produces: `guitar_chords "<song>.m4a"`, exit 0 when the merged chart is written and published, 1 with a reason otherwise. Working files go to `$MUSIC_DIR/Stems/guitar-check/<name>/` (gitignored).

Steps the function runs, in order:
1. Refuse a missing file or a song with no `<name> chords.txt` beside it (same messages as `logic_chords`).
2. If the song's chart does not contain `# chords from Logic Pro Chord ID`, run `logic_chords "$f"` first (Daniel's first press, on the full mix).
3. If `Stems/htdemucs_6s/<name>/guitar.wav` is missing, run `separate_stems "$f" 6stem "$MUSIC_DIR/Stems"`.
4. Copy `guitar.wav` to `Stems/guitar-check/<name>/<name> guitar.wav`, and as its grid the song's `(script)` chart if there is one, else the song chart, as `<name> guitar chords.txt`.
5. Run `logic_chords.py --manual` on the guitar copy (Daniel's second press). It does not publish: the guitar copy is not under `Apple Music/`.
6. Run `combine_charts.py` on the guitar chart and the song chart, then the publish step that `logic_chords` uses.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test-core.sh` before `exit $fail`:

```zsh
# guitar_chords refuses before Logic or Demucs runs: a folder is not a song, and a song with no
# chart has no bar grid. Neither may write anything or reach the publish step.
MUSIC_DIR="${0:A:h:h}"
tmp=$(mktemp -d)
mkdir "$tmp/09 Nights"
msg=$(guitar_chords "$tmp/09 Nights" 2>&1); rc=$?
assert_eq "$rc" "1" "guitar_chords refuses a folder"
assert_eq "${msg:0:29}" "Guitar chords needs the song'" "guitar_chords says why it refused a folder"
touch "$tmp/song.m4a"
msg=$(guitar_chords "$tmp/song.m4a" 2>&1); rc=$?
assert_eq "$rc" "1" "guitar_chords refuses a song with no chart"
assert_eq "${msg:0:12}" "No chart at " "guitar_chords says the chart is missing"
assert_eq "$(ls "$tmp")" "09 Nights
song.m4a" "a refused guitar_chords run writes nothing beside the song"
assert_eq "$(ls "$MUSIC_DIR/Stems/guitar-check" 2>/dev/null | grep -c '^song$')" "0" "a refused run makes no working folder"
rm -rf "$tmp"
```

- [ ] **Step 2: Run them to see them fail**

Run: `zsh tests/test-core.sh 2>&1 | grep -i guitar_chords`
Expected: `FAIL (guitar_chords refuses a folder): expected [1] got [127]` (command not found) and the other guitar_chords lines failing.

- [ ] **Step 3: Write the function**

Add to `lib/music-core.sh` right after `logic_chords()`:

```zsh
guitar_chords() {
  # $1 = a song's audio file with its "<name> chords.txt" beside it. Builds the chart from Logic's
  # Chord ID on the guitar stem, with the full mix filling bars where the guitar rests
  # (Scripts/combine_charts.py), then publishes it like logic_chords. Logic opens on screen twice
  # at most (full mix if that chart is not Logic's yet, then the guitar): click the region and
  # press Ctrl-Opt-Shift-Cmd-C each time.
  local f="$1" pub="$HOME/developer/chordbook/scripts/songs_to_icloud.sh" out rc
  if [[ ! -f "$f" ]]; then
    echo "Guitar chords needs the song's audio file, and ${f:t} is not one (a stems folder?). Drag the .m4a." >&2
    return 1
  fi
  local name="${f:t:r}" chart="${f:h}/${f:t:r} chords.txt"
  if [[ ! -f "$chart" ]]; then
    echo "No chart at $chart: run the Guitar chords step first, which sets the bar grid." >&2
    return 1
  fi
  if ! grep -q "^# chords from Logic Pro Chord ID" "$chart"; then
    echo "First, Logic's chords for the full mix:"
    logic_chords "$f" || return 1
  fi
  local stem="$MUSIC_DIR/Stems/htdemucs_6s/$name/guitar.wav"
  if [[ ! -f "$stem" ]]; then
    echo "Splitting out the guitar (a few minutes)..."
    separate_stems "$f" 6stem "$MUSIC_DIR/Stems" >/dev/null || return 1
  fi
  local work="$MUSIC_DIR/Stems/guitar-check/$name" grid="${f:h}/$name chords (script).txt"
  [[ -f "$grid" ]] || grid="$chart"
  mkdir -p "$work"
  cp "$stem" "$work/$name guitar.wav" || return 1
  cp "$grid" "$work/$name guitar chords.txt" || return 1
  echo "Now Logic's chords for the guitar alone:"
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/logic_chords.py" --manual "$work/$name guitar.wav" || return 1
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/combine_charts.py" "$work/$name guitar chords.txt" "$chart" || return 1
  if [[ ! -x "$pub" ]]; then
    echo "Chordbook is not on this Mac, so nothing was sent to the phone."
    return 0
  fi
  out="$("$pub" 2>&1)"; rc=$?
  print -rl -- "${(@M)${(f)out}:#*($name|FAILED|added, )*}"
  return $rc
}
```

Note the refusals print to stderr and the tests capture `2>&1`, matching the `logic_chords` tests.

- [ ] **Step 4: Run the tests to see them pass**

Run: `zsh tests/test-core.sh 2>&1 | tail -12` and `zsh -n lib/music-core.sh`
Expected: every `guitar_chords` line `ok:`, no `FAIL` anywhere, exit 0; the syntax check prints nothing.

Prove one test can fail: change the folder message to start "Guitar chord needs", rerun, expect `FAIL (guitar_chords says why it refused a folder)`, restore.

- [ ] **Step 5: Commit**

```bash
git commit -m "Add guitar_chords: Logic's chords from the guitar stem, mix where it rests" -m "Chains the full-mix Logic chart, the 6-stem split, a Logic run on the guitar stem, the merge and the publish. Both Logic runs are semi-manual." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- lib/music-core.sh tests/test-core.sh
```

---

### Task 3: Menu key and docs

**Files:**
- Modify: `music` (Tools menu listing and the `case` arms; the `K|k)` arm is at about line 269)
- Modify: `CLAUDE.md` (repo root)

**Interfaces:**
- Consumes: `guitar_chords` (Task 2), the menu's `CUR_SRC` and `resolve_target` (existing, as the `K|k)` arm uses them).

- [ ] **Step 1: Confirm `J` is free**

Run: `grep -n '^ *J|j)\|"J"\| J) ' music`
Expected: no output. If `J` is taken, use the first free letter from `grep -o '^ *[A-Z]|[a-z])' music` and use it everywhere below.

- [ ] **Step 2: Add the menu line**

Find the Tools listing line that shows `K) Logic chords` (`grep -n "Logic chords" music`) and add right after it, in the same format as that line:

```zsh
  echo "  J) Guitar-first chords (Logic on the guitar stem, mix where it rests)"
```

(Match the exact indentation and wording style of the neighbouring `K)` line; if the listing is one `print` with several entries, add `J)` to it in the same way.)

- [ ] **Step 3: Add the case arm, right after the `K|k)` arm's `;;`**

```zsh
    J|j)
      if [[ -f "$CUR_SRC" ]]; then
        INPUT="$CUR_SRC"
      else
        read "raw?Song title (typos OK) or drag its audio file> "
        INPUT=$(resolve_target "$raw") || continue
      fi
      guitar_chords "$INPUT"
      ;;
```

- [ ] **Step 4: Check the menu still parses and the arm is reachable**

Run: `zsh -n music && grep -n "guitar_chords" music`
Expected: no syntax output; one match in the `J|j)` arm. Then run `./music`, open Tools (`T`), confirm the `J)` line shows, and quit with `Q` without running it.

- [ ] **Step 5: Document it in the repo `CLAUDE.md`**

In the Commands bullet's Tools list (`Tools (T): A stem levels, ...`), add `J guitar-first chords` after `K Logic chords`. After the `logic_chords(file)` bullet under Architecture, add:

```markdown
- `guitar_chords(file)` (menu Tools `J`) -- Logic's Chord ID on the guitar stem, which names what the guitar plays (WALKING AWAY, 2026-11-18: plain D#/F where the full mix said D#maj7; Daniel: the full-mix chart "doesn't sound good"). Runs `logic_chords` first if the chart is not Logic's yet, splits 6 stems if `guitar.wav` is missing, runs `logic_chords.py --manual` on a copy in `Stems/guitar-check/<name>/`, then `Scripts/combine_charts.py`: guitar chord for every bar the guitar plays (with its beat-3 change), the full-mix chord where it rests, spelled as the guitar spells that root. The tempo line stays the full mix's. The full-mix chart is kept as `<name> chords (mix).txt`. Tests: `tests/test-combine-charts.py`, `tests/test-core.sh`.
```

- [ ] **Step 6: Commit**

```bash
git commit -m "Add menu key J for guitar-first chords and document it" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- music CLAUDE.md
```

---

### Task 4: Prove it end to end on WALKING AWAY (needs Daniel at the Mac)

**Files:** none changed; this is the live check.

- [ ] **Step 1: Set up a scratch copy so the real song is not touched**

```bash
cd ~/developer/music
s="$HOME/developer/music/Stems/guitar-check/proof"
mkdir -p "$s"
d="Apple Music/Justin Bieber/SWAG"
cp "$d/10 WALKING AWAY.m4a" "$s/"
cp "$d/10 WALKING AWAY chords (mix).txt" "$s/10 WALKING AWAY chords.txt"
cp "$d/10 WALKING AWAY chords (script).txt" "$s/"
```

The copy's chart is the full-mix Logic chart, so step 2 skips the first Logic run. `Stems/htdemucs_6s/10 WALKING AWAY/guitar.wav` exists, so the split is skipped too.

- [ ] **Step 2: Run it, with Daniel pressing the shortcut once**

Logic must be closed. Run: `zsh -c 'export MUSIC_DIR=$PWD; source lib/music-core.sh; guitar_chords "Stems/guitar-check/proof/10 WALKING AWAY.m4a"'`
Daniel: when Logic shows the `10 WALKING AWAY guitar` region, click it and press Ctrl-Opt-Shift-Cmd-C.
Expected output includes `Logic found ... chord changes`, `Wrote 10 WALKING AWAY chords.txt (guitar first)`.

Note: the publish step at the end republishes the music project's songs; the proof copy is under `Stems/`, which `songs_to_icloud.sh` does not publish, so the phone is unchanged. Check the summary line says `0 failed`.

- [ ] **Step 3: Compare with the accepted chart**

```bash
diff <(grep -v '^#' "Stems/guitar-check/proof/10 WALKING AWAY chords.txt") <(grep -v '^#' "Apple Music/Justin Bieber/SWAG/10 WALKING AWAY chords.txt") && echo SAME
```

Expected: `SAME`, or a handful of bars that differ because Logic's second run on the same stem placed a change differently. Report the count; more than 5 differing bars means look before going on.

- [ ] **Step 4: Record and close out**

Add a line to STATUS.md "Confirmed working": guitar-first chords, proved on a WALKING AWAY copy with the result. Tick the TASKS.md item if one was added at plan approval. Commit STATUS.md/TASKS.md with an explicit pathspec.

## Not in this plan

- **Hands-free Logic.** The scripted press stays unreliable (STATUS.md); both runs here are `--manual`.
- **Logic's own Stem Splitter** in place of Demucs. Logic's Assistant says it can split a Guitar stem on Apple Silicon (Processing > Stem Splitter); untried.
- **Flex Pitch to MIDI** for riffs and melody. Logic's Assistant described it; untried, and believed to suit single-note lines only.
- **The guitar run's own tempo/start** (88.04 BPM, 0.114 s vs the mix's 87.99 BPM, 0.313 s). Kept as the mix's until Daniel says the strum sits early or late.
