---
name: run-music
description: Launch, drive, and smoke-test the music toolkit to prove a change actually works. Use whenever running, starting, building, screenshotting, or reproducing a bug in the music flip-path app — the zsh `music` menu, the `music-menu` or `studio-tui` ratatui apps, a single pipeline step, or a `Scripts/*.py` analyzer. Trigger even for a one-off "does this step still run?" check.
---

# Running the music toolkit

The repo holds **three drivable surfaces** over one shared core
(`lib/music-core.sh` + `Scripts/*.py`):

| Surface | Command | Input model |
|---|---|---|
| `menu` | `./music` | zsh, line-based — every key needs **Enter** |
| `rust` | `music-menu/target/debug/music-menu` | ratatui, **raw keys, no Enter** |
| `studio` | `StudioTUI/target/debug/studio-tui` | ratatui, **raw keys, no Enter** |

All three are interactive and block on stdin, so none can be piped. Drive them
through the committed driver, which wraps them in tmux:

```
.claude/skills/run-music/driver.sh
```

**Repo root: `/Users/home/Developer/music`. Every path below is relative to it.**

`StudioUI/` is **not** a fourth surface — it is the static HTML mockup
`music-studio.pdf` was rendered from (STATUS.md). Do not try to run it.

## Run: headless smoke (start here)

Proves the core works end to end without touching a TUI. Use this after any
change to `Scripts/*.py` or `lib/music-core.sh`.

```bash
./.claude/skills/run-music/driver.sh smoke
```

Observed output — 8 checks, exits 0:

```
== music smoke ==
repo: /Users/home/Developer/music
  [ok] venv numpy — 2.5.0
  [ok] core unit tests — ok: acapella profile args
  [ok] find_track fuzzy — 0.9786	stems	02 Let Em' Know	/Users/home/...
  [ok] catalog stats — tracks: 58  (deconstructed 22, pending 36)
  [ok] catalog mix — 5 compatible pair(s) from 55 analyzed tracks (tempo tol ±6%)
  [ok] chords.py on stems — Chords -- 02 Let Em' Know
  [ok] chords.txt written — 122 lines
  [ok] chords.py rejects a non-stem dir — exits 1 as it should — chord analysis failed…

8 passed, 0 failed
```

It **exits non-zero when a check fails** — verified, not assumed. Point it at a
missing fixture to watch it fail:

```bash
MUSIC_FIXTURE="Stems/htdemucs_6s/NoSuchTrack" ./.claude/skills/run-music/driver.sh smoke
# -> [x] fixture missing: … / 6 passed, 1 failed / exit 1
```

The suite deliberately includes a **negative control** (`chords.py` on `/tmp`
must exit non-zero). Keep it. Without it the suite has never been observed to
fail, and a check that cannot fail proves nothing.

## Run: drive a TUI

One command — launch, send each key, print the frame after each, tear down:

```bash
./.claude/skills/run-music/driver.sh tui menu T X ""     # zsh menu -> Tools -> Mix-match -> default answer
./.claude/skills/run-music/driver.sh tui rust j j        # ratatui list, move down twice
./.claude/skills/run-music/driver.sh tui studio 2        # studio, switch to the Sequencer tab
```

Use `""` as a key to send a bare Enter (answers a `[y/N]` prompt with its
default).

For step-by-step exploration:

```bash
./.claude/skills/run-music/driver.sh tui-start rust
./.claude/skills/run-music/driver.sh tui-send j
./.claude/skills/run-music/driver.sh tui-screen
./.claude/skills/run-music/driver.sh tui-stop
```

`tui-send` reads which app is running from a state file and sends Enter **only**
for `menu`. You do not have to remember the difference — but do not bypass the
driver and call `tmux send-keys` yourself, or you will send Enter to a ratatui
app and fire a pipeline step instead of moving the cursor.

The driver waits for the pane to **settle** (two identical captures) rather than
sleeping a fixed interval, so frames are never captured mid-redraw.

### Menu map — `./music` (verified by driving it)

**Main:** `1` Download · `8` Deconstruct · `2` Separate stems · `7` Tempo & key ·
`3` Chop vocals · `4` Split drums · `6` Sort drum kit · `5` Chop stems ·
`L` Browse tracks · `O` Open Samples/ · `T` More tools · `G` Guide · `Q` Quit ·
`C` Clear track *(shown only once a track is selected)*.

**Tools (reached with `T`):** `A` Stem levels · `H` Chords · `X` Mix-match ·
`Z` Mix report · `T` Tempo lock · `M` Bass→MIDI · `R` Re-voice ·
`P` Build Logic project · `9` Download + chop · `B` Back.

`A`/`H`/`X`/`Z`/`M`/`R`/`P` exist **only inside Tools** — send `T` first. Steps
needing a file prompt for a path; `L` selects a current track so the tools have
something to act on.

## Direct invocation — the layer most changes touch

Recent work is almost entirely `Scripts/*.py` (key detection, mix ranking,
catalog). Call the entry point directly; do not go through the interactive
wrapper, which only prompts and forwards.

```bash
# Chord chart for a Stems folder or an audio file (writes chords.txt beside it)
.venv/bin/python Scripts/chords.py "Stems/htdemucs_6s/02 Let Em' Know"

# Harmonic mix-match over the catalog
.venv/bin/python Scripts/catalog.py mix --limit 5
.venv/bin/python Scripts/catalog.py mix --seed "ivy" --lyrics

# Tempo + key estimate
.venv/bin/python Scripts/analyze_track.py "Apple Music/Frank Ocean/Blonde/02 Ivy.m4a"

# Fuzzy track resolution (stdlib only, no venv needed)
.venv/bin/python Scripts/find_track.py "let em know" --tsv

# A core shell function with arguments (the *.sh wrappers are interactive; this is not)
zsh -c 'source lib/music-core.sh && analyze_track "Stems/htdemucs_6s/02 Let Em'\'' Know"'
```

Check the **exit code** as well as the text — `analyze_track.py` and `chords.py`
exit non-zero on failure and callers (`music-menu`, `studio-tui`,
`deconstruct`'s catalog parse) gate on it.

## Build

The zsh surface needs no build. The two Rust surfaces do:

```bash
(cd music-menu && cargo build)   # ~10s warm
(cd StudioTUI && cargo build)    # ~6s warm; emits 3 dead-code warnings — pre-existing, not yours
```

Python steps other than `chop.py`, `catalog.py`, `find_track.py`, `lyrics.py`,
`mix_report.py`, `mix_preview.py` need the venv's numpy. Invoke
`.venv/bin/python` **directly** rather than `source .venv/bin/activate`.

## Test

```bash
zsh tests/test-core.sh      # hand-rolled assertions, no framework, ~0.1s
```

## Gotchas

- **`T` means two different things.** On the main menu it opens Tools; inside
  Tools it is Tempo lock. A driver script that sends `T T` expecting to reach
  Tools twice lands in the click-compare path and then blocks on a path prompt.
- **Never send Enter to `rust` or `studio`.** They read raw keypresses; Enter
  activates the selected row and starts a real pipeline step. Only the zsh
  `menu` needs it. The driver handles this per-app — use it.
- **`${PIPESTATUS[0]}` is empty in zsh.** It is `${pipestatus[1]}` — lowercase,
  1-indexed. Reading the wrong one silently yields an empty string, so an exit
  check written the bash way always looks like it passed.
- **`${${(f)out}[1]}` is not "first line".** When the split yields one line it
  subscripts the *string* and returns the first **character** (`2.5.0` → `2`);
  with two or more lines it subscripts the array and returns the line. Assign to
  an explicit array first: `local -a l; l=( ${(f)out} ); print $l[1]`. This bit
  the driver and made every single-line check report one character.
- **`mix --seed` matches more strictly than `find_track.py`.** `find_track.py
  "let em know"` resolves at 0.98, but `mix --seed "let em know"` returns *no
  analyzed track matches* and exits 1 — the seed matcher runs over the catalog's
  **analyzed** rows, whose title carries the apostrophe (`Let Em' Know`). A
  one-word seed (`--seed "ivy"`) is the reliable form; when one fails, run
  `catalog.py search "<title>"` to see the row it is actually matching against.
- **Every `*.sh` wrapper blocks on stdin.** Piping into one, or running it where
  stdin is closed, hangs. Use the arg-driven core function or `Scripts/*.py`.
- **The tmux pane is 200x50.** Output longer than 50 rows scrolls off, and
  `capture-pane -S -` did not recover it here. Narrow the query (`--limit 5`)
  or read the step headless instead of through the menu.
- **`capture-pane` returns the whole visible pane**, so a frame includes the
  *previous* screen above the current one. Read the bottom of the frame, not the
  top, when checking what a key did.
- **Mix-match with fewer than 2 analyzed tracks** prints a clean message and
  exits non-zero. That is correct sparse-catalog behavior, not a bug.
- **`analyze_track.py` reports "analysis failed" on `03 Exchange.m4a`** — a
  corrupt-mvhd quirk in that one file, faithfully surfaced.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: numpy` | You used system python. Use `.venv/bin/python`. |
| `… not built — run: (cd music-menu && cargo build)` | The debug binary is missing. Run exactly that. |
| A wrapper hangs with no output | It is blocked on stdin. Kill it; call the core function or `Scripts/*.py` with arguments instead. |
| `chord analysis failed -- not a stem folder or audio` (exit 1) | Expected for a non-stem directory. An acapella split is analyzed via its `no_vocals.wav`; anything else is rejected. |
| Frame is blank or unchanged after a key | The key did not register. Re-read the whole frame without `tail`; for a ratatui app confirm you did not send Enter. |
| `no session — run tui-start` | A `tui-send`/`tui-screen` outside a session. Start one, or use the one-shot `tui <app> <keys…>` form. |
| A stale `music-drv` tmux session | `./.claude/skills/run-music/driver.sh tui-stop`, or `tmux kill-session -t music-drv`. |

## Edge cases

- **No tmux** → run `smoke` and the direct-invocation commands; report that the
  TUI surfaces were not exercised rather than implying they passed.
- **Empty catalog** (`catalog.py stats` shows 0 tracks) → `mix` exits non-zero by
  design. Run a `deconstruct` first, or accept it as the sparse-catalog path.
- **Fixture missing** → `smoke` fails the chords checks by design. Override with
  `MUSIC_FIXTURE=<a Stems/<model>/<track> dir>` rather than editing the driver.
