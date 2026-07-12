# Stem Separation Quality Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `separate_stems`' three raw modes with four named quality profiles, defaulting to the cleanest 6-stem output so guitar/piano come out by default and as clean as the toolchain allows.

**Architecture:** Two pure mapping helpers (`stem_profile_args`, `stem_profile_model`) replace the single `stem_mode_args` in `lib/music-core.sh`; `separate_stems` derives its output model dir from `stem_profile_model` instead of an inline `[[ == 6stem ]]` check; `deconstruct` passes `fast` explicitly; the menu's Separate (`2)`) arm swaps its mode prompt for a profile prompt defaulting to `hq`.

**Tech Stack:** zsh (core + menu), demucs (via `.venv`), hand-rolled assertion tests in `tests/test-core.sh`.

## Global Constraints

- No emoji anywhere (code, comments, commit messages, prompts). Use plain text / ASCII.
- Match existing `lib/music-core.sh` style: `case` statements with `print --`, `return 1` on unknown key.
- The four profile keys are exactly: `acapella`, `fast`, `6stem`, `hq`.
- Profile → demucs args (verbatim):
  - `acapella` -> `--two-stems=vocals` (model dir `htdemucs`)
  - `fast` -> *(empty string)* (model dir `htdemucs`)
  - `6stem` -> `-n htdemucs_6s` (model dir `htdemucs_6s`)
  - `hq` -> `-n htdemucs_6s --shifts 2 --overlap 0.5` (model dir `htdemucs_6s`)
- `acapella`/`fast` reproduce today's `instrumental`/`4stem` behavior verbatim; `6stem` unchanged; `hq` is new.
- `deconstruct` stays on `fast` (do not make it slow-by-default).
- Menu Separate prompt default (empty input) = `hq`.
- Do not use `git commit --no-verify`. Append `Co-Authored-By: Claude <noreply@anthropic.com>` to commits.

## File Structure

- `lib/music-core.sh` — replace `stem_mode_args` (lines 7-14) with `stem_profile_args` + `stem_profile_model`; update `separate_stems` (lines 96-110) arg lookup + model-dir derivation; update `deconstruct` (line 244) to pass `fast`.
- `tests/test-core.sh` — replace the three `stem_mode_args` assertions (lines 13-15) with `stem_profile_args` + `stem_profile_model` assertions for all four profiles plus the unknown-key error.
- `music` — rewrite the Separate (`2)`) arm's mode prompt (lines 183-184) into the profile prompt.

---

### Task 1: Profile mapping helpers + core wiring (`lib/music-core.sh`, `tests/test-core.sh`)

**Files:**
- Modify: `lib/music-core.sh:7-14` (replace `stem_mode_args`), `:100` (arg lookup + error msg), `:107-108` (model dir), `:244` (deconstruct call)
- Test: `tests/test-core.sh:13-15` (replace assertions)

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `stem_profile_args <profile>` — echoes demucs args string for a profile; `return 1` on unknown key.
  - `stem_profile_model <profile>` — echoes output model dir name (`htdemucs` or `htdemucs_6s`); `return 1` on unknown key.
  - `separate_stems <file> <profile> <out_dir>` — signature unchanged (arg 2 is now a profile key, not a mode); still echoes the vocals.wav path.

- [ ] **Step 1: Write the failing tests**

Replace `tests/test-core.sh` lines 13-15 (the three `stem_mode_args` assertions) with:

```zsh
assert_eq "$(stem_profile_args acapella)" "--two-stems=vocals" "acapella profile args"
assert_eq "$(stem_profile_args fast)" "" "fast profile args"
assert_eq "$(stem_profile_args 6stem)" "-n htdemucs_6s" "6stem profile args"
assert_eq "$(stem_profile_args hq)" "-n htdemucs_6s --shifts 2 --overlap 0.5" "hq profile args"
assert_eq "$(stem_profile_model acapella)" "htdemucs" "acapella model dir"
assert_eq "$(stem_profile_model fast)" "htdemucs" "fast model dir"
assert_eq "$(stem_profile_model 6stem)" "htdemucs_6s" "6stem model dir"
assert_eq "$(stem_profile_model hq)" "htdemucs_6s" "hq model dir"
stem_profile_args bogus 2>/dev/null; assert_eq "$?" "1" "unknown profile args errors"
stem_profile_model bogus 2>/dev/null; assert_eq "$?" "1" "unknown profile model errors"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `zsh tests/test-core.sh`
Expected: FAIL — `stem_profile_args`/`stem_profile_model` are not defined (command-not-found; assertions fail).

- [ ] **Step 3: Replace `stem_mode_args` with the two profile helpers**

In `lib/music-core.sh`, replace lines 7-14 (the whole `stem_mode_args` function) with:

```zsh
stem_profile_args() {
  # Quality profile -> demucs args. hq is the cleanest 6-stem (guitar/piano).
  case "$1" in
    acapella) print -- "--two-stems=vocals" ;;
    fast)     print -- "" ;;
    6stem)    print -- "-n htdemucs_6s" ;;
    hq)       print -- "-n htdemucs_6s --shifts 2 --overlap 0.5" ;;
    *)        return 1 ;;
  esac
}

stem_profile_model() {
  # Quality profile -> output model directory under Stems/.
  case "$1" in
    acapella|fast) print -- "htdemucs" ;;
    6stem|hq)      print -- "htdemucs_6s" ;;
    *)             return 1 ;;
  esac
}
```

- [ ] **Step 4: Update `separate_stems` to use the profile helpers**

In `lib/music-core.sh`, update the `separate_stems` function:

Change the comment/param naming and arg lookup (currently lines 97-100):

```zsh
  # $1 = file, $2 = profile, $3 = out_dir ; echoes vocals.wav path
  local file="$1" profile="$2" out="$3"
  local args
  args=$(stem_profile_args "$profile") || { echo "bad profile: $profile" >&2; return 1; }
```

Change the model-dir derivation (currently lines 107-108) to:

```zsh
  local model_dir
  model_dir=$(stem_profile_model "$profile")
```

Leave line 109 (`print -- "$out/$model_dir/${file:t:r}/vocals.wav"`) unchanged.

- [ ] **Step 5: Update `deconstruct` to pass `fast`**

In `lib/music-core.sh` line 244, change:

```zsh
  separate_stems "$file" 4stem "$MUSIC_DIR/Stems" >/dev/null || return 1
```

to:

```zsh
  separate_stems "$file" fast "$MUSIC_DIR/Stems" >/dev/null || return 1
```

(The `stemdir="$MUSIC_DIR/Stems/htdemucs/$track"` at line 240 stays correct — `fast` maps to `htdemucs`.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `zsh tests/test-core.sh`
Expected: PASS — all assertions ok (10 new profile assertions + the unchanged chop/drum/find/stems_dir_for ones).

- [ ] **Step 7: Syntax-check the sourced core**

Run: `zsh -n lib/music-core.sh`
Expected: no output (exit 0).

- [ ] **Step 8: Commit**

```bash
git add lib/music-core.sh tests/test-core.sh
git commit -m "feat: replace stem modes with quality profiles in core

Replace stem_mode_args with stem_profile_args + stem_profile_model.
separate_stems derives its model dir from the profile; deconstruct
passes fast. Adds acapella/fast/6stem/hq; hq is the clean 6-stem
(--shifts 2 --overlap 0.5) that isolates guitar/piano.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Menu Separate profile prompt (`music`)

**Files:**
- Modify: `music:183-184` (Separate arm's mode prompt)

**Interfaces:**
- Consumes: `separate_stems <file> <profile> <out_dir>` from Task 1 (arg 2 is a profile key).
- Produces: nothing downstream.

- [ ] **Step 1: Rewrite the mode prompt into a profile prompt**

In `music`, replace lines 183-184:

```zsh
      echo "Mode: 1) instrumental  2) 4stem [recommended]  3) 6stem"; read "m?> "
      case "$m" in 1) MODE=instrumental;; 3) MODE=6stem;; 2|"") MODE=4stem;; *) echo "Invalid."; continue;; esac
```

with:

```zsh
      echo "Quality: 1) fast (4-stem)  2) 6-stem  3) 6-stem HQ [recommended, slow]  4) acapella"; read "m?> "
      case "$m" in 1) MODE=fast;; 2) MODE=6stem;; 4) MODE=acapella;; 3|"") MODE=hq;; *) echo "Invalid."; continue;; esac
```

(Lines 185-191, which call `separate_stems "$INPUT" "$MODE" ...` / `separate_stems "$f" "$MODE" ...`, stay unchanged — `$MODE` now holds a profile key.)

- [ ] **Step 2: Syntax-check the menu**

Run: `zsh -n music`
Expected: no output (exit 0).

- [ ] **Step 3: Verify the prompt renders and maps (non-interactive smoke)**

Run:

```bash
grep -n 'Quality: 1) fast' music && grep -n 'MODE=hq' music
```

Expected: both lines print (the prompt text and the empty-default `hq` mapping are present).

- [ ] **Step 4: Commit**

```bash
git add music
git commit -m "feat: profile-based quality prompt in Separate menu

Replace the instrumental/4stem/6stem mode prompt with fast/6-stem/
6-stem HQ/acapella; empty input defaults to hq (clean 6-stem).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

- **Spec coverage:** Profiles table -> Task 1 Step 3 (both helpers, all four keys). `separate_stems` model-dir derivation -> Task 1 Step 4. `deconstruct` stays `fast` -> Task 1 Step 5. Menu profile prompt + `hq` default -> Task 2 Step 1. Test replacement -> Task 1 Step 1. `stems_dir_for`/current-track compatibility -> unchanged by design (hq writes `htdemucs_6s`, already handled). All spec "Affected files" covered.
- **Placeholder scan:** none — every code step shows the exact code.
- **Type consistency:** `stem_profile_args`/`stem_profile_model` names identical across Task 1 helpers, tests, and `separate_stems`; `MODE` holds a profile key consistently in the menu arm.
