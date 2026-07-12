# Per-stem Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After separation, report per-stem presence and loudness (via ffmpeg volumedetect) so empty/faint stems are obvious — printed and saved as `analysis.txt` beside the stems, wired into the menu, a wrapper, and `deconstruct`.

**Architecture:** A pure `stem_presence_label` classifier + an `analyze_stems` core function (mirrors `chop_stems` input handling) in `lib/music-core.sh`; `deconstruct` calls it; the `music` menu gains an `A)` Tools entry using the existing `resolve_stems` resolver; a thin `analyze-stems.sh` wrapper mirrors `stems.sh`.

**Tech Stack:** zsh, ffmpeg (`volumedetect`), awk (float compare), hand-rolled assertions in `tests/test-core.sh`.

## Global Constraints

- No emoji anywhere. Plain text / ASCII only.
- No new Python dependencies — ffmpeg only.
- Analysis is read-only: never modify or re-encode the stems.
- Presence thresholds (verbatim): `max < -50 dB` -> `silent`; else `mean < -45 dB` -> `faint`; else `present`.
- Match `lib/music-core.sh` style: `case`/helpers with `print --`; `analyze_stems` mirrors `chop_stems`' folder-or-single-wav input handling.
- Do not use `git commit --no-verify`. Append `Co-Authored-By: Claude <noreply@anthropic.com>`.

## File Structure

- `lib/music-core.sh` — add `stem_presence_label` (pure) and `analyze_stems`; add one `analyze_stems "$stemdir"` call at the end of `deconstruct`.
- `tests/test-core.sh` — add `stem_presence_label` assertions.
- `music` — add `A)` Tools line + `A|a)` case arm.
- `analyze-stems.sh` — new thin wrapper (created in Task 2).

---

### Task 1: `stem_presence_label` + `analyze_stems` core + deconstruct wiring

**Files:**
- Modify: `lib/music-core.sh` (add two functions after `chop_stems`; add a call in `deconstruct`)
- Test: `tests/test-core.sh` (add assertions after the `drum_split_args` block)

**Interfaces:**
- Produces:
  - `stem_presence_label <mean_dbfs> <max_dbfs>` — echoes `silent` | `faint` | `present`.
  - `analyze_stems <track_folder_or_stem_wav>` — prints a table, writes `<folder>/analysis.txt`, returns 1 if no `.wav` stems found.

- [ ] **Step 1: Write the failing tests**

In `tests/test-core.sh`, immediately after the `drum_split_args loose` assertion (currently line 19), add:

```zsh
assert_eq "$(stem_presence_label -30 -2)" "present" "present loudness"
assert_eq "$(stem_presence_label -77.3 -26.2)" "faint" "faint loudness"
assert_eq "$(stem_presence_label -60 -55)" "silent" "silent loudness"
assert_eq "$(stem_presence_label -46 -50)" "faint" "peak -50 is not silent (boundary)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `zsh tests/test-core.sh`
Expected: FAIL — `stem_presence_label` not defined.

- [ ] **Step 3: Add the two core functions**

In `lib/music-core.sh`, immediately after the `chop_stems()` function's closing `}`, add:

```zsh
stem_presence_label() {
  # $1 = mean dBFS, $2 = max dBFS -> silent | faint | present.
  # zsh has no native float <, so compare in awk.
  awk -v m="$1" -v x="$2" 'BEGIN{
    if (x < -50) print "silent";
    else if (m < -45) print "faint";
    else print "present";
  }'
}

analyze_stems() {
  # $1 = a Stems/<model>/<track> folder (or a single stem .wav). Prints a
  # presence/loudness table per stem (ffmpeg volumedetect) and writes it to
  # <folder>/analysis.txt. Read-only; never modifies the stems.
  local input="$1"
  local -a stems
  local track dir
  if [[ -d "$input" ]]; then
    track="${input:t}"; dir="$input"
    stems=("$input"/*.wav(N))
  else
    track="${input:h:t}"; dir="${input:h}"
    stems=("$input")
  fi
  [[ ${#stems} -eq 0 ]] && { echo "No stem .wav files in $input" >&2; return 1; }
  local report="$dir/analysis.txt"
  local stem name vd mean max label
  {
    printf "%-10s %9s %9s  %s\n" "stem" "mean" "peak" "presence"
    for stem in $stems; do
      name="${stem:t:r}"
      vd=$(ffmpeg -nostdin -i "$stem" -af volumedetect -f null - 2>&1)
      mean=$(print -r -- "$vd" | awk -F': ' '/mean_volume:/{print $2+0}')
      max=$(print -r -- "$vd" | awk -F': ' '/max_volume:/{print $2+0}')
      label=$(stem_presence_label "$mean" "$max")
      printf "%-10s %6s dB %6s dB  %s\n" "$name" "$mean" "$max" "$label"
    done
  } | tee "$report"
  echo "  Report: $report" >&2
}
```

- [ ] **Step 4: Wire `analyze_stems` into `deconstruct`**

In `lib/music-core.sh`, find the `deconstruct()` line that runs the 8s stem snippets:

```zsh
  echo "→ 8s stem snippets…"
  chop_stems "$stemdir" "$MUSIC_DIR/Samples/Chops" 8 >/dev/null
```

Immediately BEFORE the `echo "→ 8s stem snippets…"` line, insert:

```zsh
  echo "→ Stem presence & loudness…"
  analyze_stems "$stemdir" >/dev/null
```

(`>/dev/null` suppresses the table during the deconstruct chain; `analysis.txt` is still written beside the stems. Uses the existing `stemdir` local.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `zsh tests/test-core.sh`
Expected: PASS — all assertions ok (the 4 new presence ones plus the existing suite).

- [ ] **Step 6: Syntax-check the core**

Run: `zsh -n lib/music-core.sh`
Expected: no output (exit 0).

- [ ] **Step 7: Smoke-test `analyze_stems` on a real stem folder**

Run:

```bash
zsh -c 'source lib/music-core.sh; analyze_stems "Stems/htdemucs_6s/02 Let Em'\'' Know"'
```

Expected: an aligned table with a row per stem and a `present`/`faint`/`silent` label each; a `Report: .../analysis.txt` line on stderr; `analysis.txt` present in that folder afterward. (If that exact folder is absent, substitute any real `Stems/<model>/<track>` dir from `find Stems -maxdepth 2 -type d`.)

- [ ] **Step 8: Commit**

```bash
git add lib/music-core.sh tests/test-core.sh
git commit -m "feat: per-stem presence & loudness analysis

Add stem_presence_label (silent/faint/present from mean+peak dBFS) and
analyze_stems (ffmpeg volumedetect per stem -> aligned table + analysis.txt
beside the stems). deconstruct now writes analysis.txt for every track.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Menu entry + `analyze-stems.sh` wrapper

**Files:**
- Modify: `music` (Tools group line + `A|a)` case arm)
- Create: `analyze-stems.sh`

**Interfaces:**
- Consumes: `analyze_stems` from Task 1; `resolve_stems` (existing, `music:23`).

- [ ] **Step 1: Add the Tools-group menu line**

In `music`, the Tools group currently ends with:

```zsh
  echo "  P) Build Logic project      G) Guide / how it works"
  echo "                              C) Clear current track   Q) Quit"
```

Replace those two lines with:

```zsh
  echo "  P) Build Logic project      A) Analyze stems (loudness/presence)"
  echo "                              G) Guide / how it works"
  echo "                              C) Clear current track   Q) Quit"
```

- [ ] **Step 2: Add the `A|a)` case arm**

In `music`, immediately before the `M|m)` case arm (currently `music:123`), add:

```zsh
    A|a)
      INPUT=$(resolve_stems)
      [[ -z "$INPUT" ]] && continue
      [[ ! -e "$INPUT" ]] && { echo "Invalid path."; continue; }
      analyze_stems "$INPUT"
      ;;
```

- [ ] **Step 3: Create the `analyze-stems.sh` wrapper**

Create `analyze-stems.sh`:

```zsh
#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Stem Analyzer"
echo "-------------"
echo "Drag a Stems/<model>/<track> folder (or a single stem .wav), then press Enter:"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -e "$INPUT" ]] && { echo "Invalid path. Exiting."; exit 1; }

analyze_stems "$INPUT"
```

- [ ] **Step 4: Make the wrapper executable**

Run: `chmod +x analyze-stems.sh`

- [ ] **Step 5: Syntax-check both scripts**

Run: `zsh -n music && zsh -n analyze-stems.sh`
Expected: no output (exit 0).

- [ ] **Step 6: Verify the menu line and arm are present**

Run:

```bash
grep -nq 'A) Analyze stems' music && grep -nq 'A|a)' music && echo "menu ok"
```

Expected: `menu ok`.

- [ ] **Step 7: Commit**

```bash
git add music analyze-stems.sh
git commit -m "feat: Analyze stems menu entry + wrapper

Add A) Analyze stems to the Tools group (uses resolve_stems, so a picked
library track analyzes with one keypress) and a standalone analyze-stems.sh
wrapper mirroring stems.sh.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

- **Spec coverage:** volumedetect metric -> Task 1 Step 3 (`analyze_stems`). Classifier + thresholds -> Task 1 Step 3 (`stem_presence_label`) + tests Step 1. Beside-stems `analysis.txt` -> Step 3 (`tee`). deconstruct wiring -> Step 4. Menu `A)` + resolve_stems -> Task 2 Steps 1-2. Wrapper -> Task 2 Step 3. Tests -> Task 1 Step 1. Catalog columns explicitly out of scope (spec) -> no task, correct.
- **Placeholder scan:** none — all code is literal.
- **Type consistency:** `stem_presence_label` and `analyze_stems` names identical across core, tests, deconstruct call, menu arm, and wrapper. `analyze_stems` takes one arg (a path) everywhere.
