# Unified Music CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single interactive `music` entry point that wraps download, stem separation, and vocal chopping, and can chain all three end-to-end.

**Architecture:** Extract each script's logic into non-interactive functions in `lib/music-core.sh`. A new `music` menu does all prompting and calls those functions; the existing standalone scripts are slimmed to thin wrappers that source the same lib. Pure helpers (mode/sensitivity mapping, new-file detection) are unit-tested with a dependency-free zsh assert harness; the tool-wrapping functions are smoke-tested against one real track.

**Tech Stack:** zsh, demucs, gamdl/yt-dlp, ffmpeg, Python 3.14 (`chop.py`). No new dependencies.

## Global Constraints

- Interpreter for Python: `/opt/homebrew/bin/python3`; activate `.venv` before any Python call.
- No new dependencies — zsh builtins + existing tools only. No bats; tests use a hand-rolled zsh assert harness.
- Preserve existing standalone usage: `download.sh`, `stems.sh`, `chop.sh` must still run interactively after refactor.
- `chop.py` is unchanged by this plan (its own hardening lives in `2026-06-29-chop-hardening.md`).
- Stem model dir is `htdemucs` for instrumental/4stem and `htdemucs_6s` for 6stem — the vocals path depends on it.
- Demucs save requires `torchcodec` in the venv (already installed 2026-06-29).

## File Structure

- `lib/music-core.sh` — all non-interactive logic: pure arg helpers, new-file detection, and the three tool wrappers. Sourced by everything.
- `music` — interactive menu + pipeline. The single entry point. Only file that prompts.
- `tests/test-core.sh` — zsh assert harness for the pure helpers.
- `download.sh` / `stems.sh` / `chop.sh` — slimmed to prompt + call the core.

---

### Task 1: Pure helpers in `lib/music-core.sh` (TDD)

**Files:**
- Create: `lib/music-core.sh`
- Test: `tests/test-core.sh`

**Interfaces:**
- Produces:
  - `stem_mode_args <mode>` → echoes demucs args for `instrumental|4stem|6stem`; returns 1 on unknown.
  - `chop_sensitivity_args <sens>` → echoes chop.py args for `tight|loose`; returns 1 on unknown.
  - `find_new_m4a <dir> <epoch>` → echoes `*.m4a` paths under `dir` modified after `epoch`.

- [ ] **Step 1: Write the failing test harness**

Create `tests/test-core.sh`:

```bash
#!/usr/bin/env zsh
source "${0:A:h}/../lib/music-core.sh"

fail=0
assert_eq() {
  if [[ "$1" != "$2" ]]; then
    echo "FAIL ($3): expected [$2] got [$1]"; fail=1
  else
    echo "ok: $3"
  fi
}

assert_eq "$(stem_mode_args instrumental)" "--two-stems=vocals" "instrumental mode"
assert_eq "$(stem_mode_args 4stem)" "" "4stem mode"
assert_eq "$(stem_mode_args 6stem)" "-n htdemucs_6s" "6stem mode"
assert_eq "$(chop_sensitivity_args tight)" "--min-silence 0.15 --min-clip 0.3" "tight sensitivity"
assert_eq "$(chop_sensitivity_args loose)" "--min-silence 0.35 --min-clip 0.8" "loose sensitivity"

# find_new_m4a: 2020 file is old, 2099 file is new, stamp is 2050 (epoch 2524608000)
tmp=$(mktemp -d)
touch -t 202001010000 "$tmp/old.m4a"
touch -t 209901010000 "$tmp/new.m4a"
result=$(find_new_m4a "$tmp" 2524608000)
assert_eq "${result:t}" "new.m4a" "find_new_m4a returns only files after stamp"
rm -rf "$tmp"

exit $fail
```

- [ ] **Step 2: Run the harness to verify it fails**

Run: `zsh tests/test-core.sh`
Expected: FAIL — `no such file or directory: .../lib/music-core.sh` (lib not created yet).

- [ ] **Step 3: Implement the pure helpers**

Create `lib/music-core.sh`:

```bash
#!/usr/bin/env zsh
# Non-interactive core for the music toolkit. Source, don't execute.

LIB_DIR="${${(%):-%x}:A:h}"
MUSIC_DIR="${LIB_DIR:h}"

stem_mode_args() {
  case "$1" in
    instrumental) print -- "--two-stems=vocals" ;;
    4stem)        print -- "" ;;
    6stem)        print -- "-n htdemucs_6s" ;;
    *)            return 1 ;;
  esac
}

chop_sensitivity_args() {
  case "$1" in
    tight) print -- "--min-silence 0.15 --min-clip 0.3" ;;
    loose) print -- "--min-silence 0.35 --min-clip 0.8" ;;
    *)     return 1 ;;
  esac
}

find_new_m4a() {
  # $1 = directory, $2 = epoch seconds.
  # BSD find (/usr/bin/find on macOS) can't parse -newermt "@epoch", so compare
  # against the mtime of a reference file stamped at the target time instead.
  local ref
  ref=$(mktemp)
  touch -t "$(date -r "$2" '+%Y%m%d%H%M.%S')" "$ref"
  find "$1" -name '*.m4a' -newer "$ref" 2>/dev/null
  rm -f "$ref"
}
```

- [ ] **Step 4: Run the harness to verify it passes**

Run: `zsh tests/test-core.sh`
Expected: PASS — 6 `ok:` lines, exit 0.

- [ ] **Step 5: Commit**

```bash
git add lib/music-core.sh tests/test-core.sh
git commit -m "feat: add pure helpers for music core (mode/sensitivity/new-file)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Tool-wrapping functions in `lib/music-core.sh`

**Files:**
- Modify: `lib/music-core.sh` (append three functions)

**Interfaces:**
- Consumes: `stem_mode_args`, `chop_sensitivity_args`, `MUSIC_DIR` from Task 1.
- Produces:
  - `download_url <url> <output_base>` → routes Apple Music/SoundCloud/other; echoes nothing, downloads to disk.
  - `separate_stems <file> <mode> <out_dir>` → runs demucs; echoes the produced `vocals.wav` path.
  - `chop_vocals <vocals_wav> <out_dir> <sensitivity>` → runs `chop.py`; passes through its stdout.

- [ ] **Step 1: Append the three wrappers to `lib/music-core.sh`**

```bash
download_url() {
  # $1 = url, $2 = apple-music output dir (other types derive siblings)
  local url="$1" am_out="$2"
  local cookies="$MUSIC_DIR/cookies.txt"

  if [[ "$url" == *"music.apple.com"* ]]; then
    if [[ ! -f "$cookies" ]]; then
      /opt/homebrew/bin/python3 "$MUSIC_DIR/get-cookies.py" "$cookies" || {
        echo "Cookie extraction failed. Sign into music.apple.com in Safari + grant Full Disk Access." >&2
        return 1
      }
    fi
    expect -c "
      set timeout -1
      spawn gamdl --cookies-path [list ${cookies}] --output-path [list ${am_out}] [list ${url}]
      expect -re {[?>]}
      send \"\x01\"
      send \"\r\"
      interact
    "
  elif [[ "$url" == *"soundcloud.com"* ]]; then
    local sc_out="$MUSIC_DIR/SoundCloud"; mkdir -p "$sc_out"
    yt-dlp --format "bestaudio[ext=m4a]/bestaudio/best" --extract-audio \
      --audio-format mp3 --audio-quality 0 --embed-thumbnail --add-metadata \
      --output "$sc_out/%(uploader)s/%(title)s.%(ext)s" "$url"
  else
    local other="$MUSIC_DIR/Downloads"; mkdir -p "$other"
    yt-dlp --format "bestaudio[ext=m4a]/bestaudio/best" --extract-audio \
      --audio-format mp3 --audio-quality 0 --embed-thumbnail --add-metadata \
      --output "$other/%(uploader)s/%(title)s.%(ext)s" "$url"
  fi
}

separate_stems() {
  # $1 = file, $2 = mode, $3 = out_dir ; echoes vocals.wav path
  local file="$1" mode="$2" out="$3"
  local args
  args=$(stem_mode_args "$mode") || { echo "bad mode: $mode" >&2; return 1; }
  mkdir -p "$out"
  demucs ${=args} --out "$out" "$file"
  local model_dir=htdemucs
  [[ "$mode" == 6stem ]] && model_dir=htdemucs_6s
  print -- "$out/$model_dir/${file:t:r}/vocals.wav"
}

chop_vocals() {
  # $1 = vocals.wav, $2 = out_dir, $3 = sensitivity
  local vocals="$1" out="$2" sens="$3"
  local args
  args=$(chop_sensitivity_args "$sens") || { echo "bad sensitivity: $sens" >&2; return 1; }
  source "$MUSIC_DIR/.venv/bin/activate"
  /opt/homebrew/bin/python3 "$MUSIC_DIR/Scripts/chop.py" "$vocals" "$out" ${=args}
}
```

- [ ] **Step 2: Smoke-test `separate_stems` path echo against an already-stemmed track**

The Open Interlude stem already exists from earlier verification. Confirm the echoed path matches reality:

```bash
source lib/music-core.sh
EXPECT="Stems/htdemucs/06 Open Interlude/vocals.wav"
GOT=$(separate_stems "Apple Music/Bryson Tiller/T R A P S O U L (Deluxe)/06 Open Interlude.m4a" instrumental Stems 2>/dev/null | tail -1)
[[ "${GOT##*/Stems/}" == "${EXPECT##Stems/}" ]] && echo "PATH OK: $GOT" || echo "PATH MISMATCH: $GOT"
ls -la "$GOT"
```
Expected: `PATH OK:` and `ls` shows a non-zero `vocals.wav`.

- [ ] **Step 3: Smoke-test `chop_vocals` on that stem**

```bash
source lib/music-core.sh
chop_vocals "Stems/htdemucs/06 Open Interlude/vocals.wav" /tmp/chop-core-smoke loose
ls /tmp/chop-core-smoke/*/ | head
```
Expected: several `vocals_NNN.wav` files printed.

- [ ] **Step 4: Commit**

```bash
git add lib/music-core.sh
git commit -m "feat: add download/stems/chop tool wrappers to music core

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: `music` menu — single-step options

**Files:**
- Create: `music`

**Interfaces:**
- Consumes: all functions from `lib/music-core.sh`.
- Produces: an executable interactive menu (options 1–3, 5 wired; option 4 added in Task 4).

- [ ] **Step 1: Create the menu with single-step routing**

Create `music`:

```bash
#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

read_path() {  # prints a cleaned drag-and-drop path
  local p; read "p?> "
  p="${p//\\ / }"
  print -- "${p%"${p##*[! ]}"}"
}

while true; do
  echo ""
  echo "Music Toolkit"
  echo "-------------"
  echo "1) Download"
  echo "2) Separate stems"
  echo "3) Chop vocals"
  echo "4) Full pipeline (download → stems → chop)"
  echo "5) Quit"
  read "choice?> "

  case "$choice" in
    1)
      read "url?Paste URL> "
      [[ -z "$url" ]] && { echo "No URL."; continue; }
      download_url "$url" "$SCRIPT_DIR/Apple Music"
      ;;
    2)
      echo "Drag a file or folder:"; INPUT=$(read_path)
      [[ ! -e "$INPUT" ]] && { echo "Invalid path."; continue; }
      echo "Mode: 1) instrumental  2) 4stem  3) 6stem"; read "m?> "
      case "$m" in 1) MODE=instrumental;; 2) MODE=4stem;; 3) MODE=6stem;; *) echo "Invalid."; continue;; esac
      if [[ -f "$INPUT" ]]; then
        separate_stems "$INPUT" "$MODE" "$SCRIPT_DIR/Stems"
      else
        find "$INPUT" -type f \( -name '*.m4a' -o -name '*.mp3' -o -name '*.flac' -o -name '*.wav' \) | while read -r f; do
          echo "Processing: ${f:t}"; separate_stems "$f" "$MODE" "$SCRIPT_DIR/Stems"
        done
      fi
      ;;
    3)
      echo "Drag a vocals.wav or Stems folder:"; INPUT=$(read_path)
      [[ -z "$INPUT" ]] && INPUT="$SCRIPT_DIR/Stems"
      [[ ! -e "$INPUT" ]] && { echo "Invalid path."; continue; }
      echo "Sensitivity: 1) tight  2) loose"; read "s?> "
      case "$s" in 1) SENS=tight;; 2) SENS=loose;; *) SENS=loose;; esac
      chop_vocals "$INPUT" "$SCRIPT_DIR/Samples/Vocals" "$SENS"
      ;;
    4)
      echo "(pipeline added in next task)"
      ;;
    5) echo "Bye."; exit 0 ;;
    *) echo "Invalid choice." ;;
  esac
done
```

- [ ] **Step 2: Make it executable and smoke-test the menu loop**

```bash
chmod +x music
printf '5\n' | ./music
```
Expected: prints the menu then `Bye.` and exits 0.

- [ ] **Step 3: Smoke-test the chop route end-to-end**

```bash
printf '3\n%s\n2\n' "Stems/htdemucs/06 Open Interlude/vocals.wav" | ./music
ls "Samples/Vocals/06 Open Interlude/" | head
```
Expected: clips listed under `Samples/Vocals/06 Open Interlude/`.

- [ ] **Step 4: Commit**

```bash
git add music
git commit -m "feat: add interactive music menu with single-step routing

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Full pipeline (option 4)

**Files:**
- Modify: `music` (replace the option-4 placeholder)

**Interfaces:**
- Consumes: `download_url`, `find_new_m4a`, `separate_stems`, `chop_vocals` from the lib.
- Produces: option 4 chaining download → stems → chop with timestamp handoff.

- [ ] **Step 1: Replace the option-4 block**

In `music`, replace:

```bash
    4)
      echo "(pipeline added in next task)"
      ;;
```

with:

```bash
    4)
      read "url?Paste URL> "
      [[ -z "$url" ]] && { echo "No URL."; continue; }
      STAMP=$(date +%s)
      download_url "$url" "$SCRIPT_DIR/Apple Music"
      new_files=$(find_new_m4a "$SCRIPT_DIR/Apple Music" "$STAMP")
      if [[ -z "$new_files" ]]; then
        echo "Nothing downloaded — aborting pipeline."; continue
      fi
      echo "$new_files" | while read -r track; do
        echo "→ Stems: ${track:t}"
        vocals=$(separate_stems "$track" instrumental "$SCRIPT_DIR/Stems" | tail -1)
        if [[ ! -f "$vocals" ]]; then
          echo "  no vocals.wav for ${track:t} — skipping chop."; continue
        fi
        echo "→ Chop: ${vocals:h:t}"
        chop_vocals "$vocals" "$SCRIPT_DIR/Samples/Vocals" loose
      done
      echo "Pipeline complete."
      ;;
```

- [ ] **Step 2: Verify the no-download abort path without invoking gamdl**

Temporarily exercise the detection logic in isolation (no real download):

```bash
source lib/music-core.sh
STAMP=$(date +%s)
# no new files created after STAMP:
out=$(find_new_m4a "Apple Music" "$STAMP")
[[ -z "$out" ]] && echo "ABORT PATH OK (no new files)" || echo "unexpected: $out"
```
Expected: `ABORT PATH OK (no new files)`.

- [ ] **Step 3: Verify handoff detects a freshly-touched file**

```bash
source lib/music-core.sh
STAMP=$(date +%s)
touch "Apple Music/.pipeline-test.m4a"
out=$(find_new_m4a "Apple Music" "$STAMP")
[[ "${out:t}" == ".pipeline-test.m4a" ]] && echo "HANDOFF OK" || echo "MISS: $out"
rm -f "Apple Music/.pipeline-test.m4a"
```
Expected: `HANDOFF OK`.

- [ ] **Step 4: Commit**

```bash
git add music
git commit -m "feat: add download→stems→chop pipeline with timestamp handoff

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Slim the standalone wrappers to source the core

**Files:**
- Modify: `stems.sh`, `chop.sh`, `download.sh`

**Interfaces:**
- Consumes: the lib functions. No new interface produced.

- [ ] **Step 1: Rewrite `stems.sh` as a thin wrapper**

Replace the whole file with:

```bash
#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Stem Separator"
echo "--------------"
echo "Drag a file or folder here, then press Enter:"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -e "$INPUT" ]] && { echo "Invalid path. Exiting."; exit 1; }

echo "Mode: 1) instrumental  2) 4stem  3) 6stem"; read "m?> "
case "$m" in 1) MODE=instrumental;; 2) MODE=4stem;; 3) MODE=6stem;; *) echo "Invalid."; exit 1;; esac

if [[ -f "$INPUT" ]]; then
  separate_stems "$INPUT" "$MODE" "$SCRIPT_DIR/Stems"
else
  find "$INPUT" -type f \( -name '*.m4a' -o -name '*.mp3' -o -name '*.flac' -o -name '*.wav' \) | while read -r f; do
    echo "Processing: ${f:t}"; separate_stems "$f" "$MODE" "$SCRIPT_DIR/Stems"
  done
fi
echo "Done. Stems saved to: $SCRIPT_DIR/Stems"
```

- [ ] **Step 2: Rewrite `chop.sh` as a thin wrapper**

Replace the whole file with:

```bash
#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Vocal Chopper"
echo "-------------"
echo "Drag a vocals.wav file or a Stems folder here (or press Enter for all stems):"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ -z "$INPUT" ]] && INPUT="$SCRIPT_DIR/Stems"
[[ ! -e "$INPUT" ]] && { echo "Invalid path. Exiting."; exit 1; }

echo "Sensitivity: 1) tight  2) loose"; read "s?> "
case "$s" in 1) SENS=tight;; 2) SENS=loose;; *) SENS=loose;; esac

chop_vocals "$INPUT" "$SCRIPT_DIR/Samples/Vocals" "$SENS"
```

- [ ] **Step 3: Rewrite `download.sh` as a thin wrapper**

Replace the whole file with:

```bash
#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Music Downloader"
echo "----------------"
echo "Paste a URL (Apple Music, SoundCloud, YouTube, Bandcamp, etc.):"
read "URL?> "
[[ -z "$URL" ]] && { echo "No URL provided. Exiting."; exit 1; }

download_url "$URL" "$SCRIPT_DIR/Apple Music"
```

- [ ] **Step 4: Verify each wrapper still loads and the test harness still passes**

```bash
zsh -n stems.sh && zsh -n chop.sh && zsh -n download.sh && echo "syntax OK"
zsh tests/test-core.sh
printf '3\n%s\n2\n' "Stems/htdemucs/06 Open Interlude/vocals.wav" | zsh chop.sh && echo "chop.sh wrapper OK"
```
Expected: `syntax OK`, 6 `ok:` lines, and chop.sh produces clips.

- [ ] **Step 5: Commit**

```bash
git add stems.sh chop.sh download.sh
git commit -m "refactor: slim standalone scripts to source music-core

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Core+menu architecture → Tasks 1–3. ✓
- `download_url` / `separate_stems` / `chop_vocals` cores → Tasks 1–2. ✓
- Menu options 1–5 → Task 3 (1–3,5) + Task 4 (4). ✓
- Full pipeline with `date +%s` snapshot + `find -newermt` handoff → Task 4. ✓
- Error handling (zero downloads abort; missing vocals skip; invalid choice reprints) → Task 4 Step 1 + Task 3 Step 1. ✓
- Standalone wrappers still work → Task 5. ✓
- Testing via manual smoke + pure-helper units → Tasks 1–5. ✓
- Out-of-scope items (subcommands, BPM tagging) → not in any task. ✓

**Placeholder scan:** Option-4 placeholder in Task 3 is intentional scaffolding, explicitly replaced in Task 4 Step 1. No TBD/TODO elsewhere; every code step shows complete code. ✓

**Type/name consistency:** `stem_mode_args` modes (`instrumental|4stem|6stem`) match `separate_stems` and the menu's `MODE` mapping. `chop_sensitivity_args` values (`tight|loose`) match `chop_vocals` and the menu's `SENS` mapping. `find_new_m4a <dir> <epoch>` signature matches both the test and the Task 4 call. `MUSIC_DIR` defined in Task 1, used in Task 2. ✓
