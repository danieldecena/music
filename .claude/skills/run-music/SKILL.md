---
name: run-music
description: Launch and drive the music toolkit to verify it actually works. Use whenever running, smoke-testing, or reproducing a bug in the music flip-path app — the interactive `music` menu, a single pipeline step, or one of the analysis Scripts. Trigger even for a one-off "does this step still run?" check.
---

# Running the music toolkit

The app is a zsh flip-path toolkit: an interactive menu (`music`) over
arg-driven core functions (`lib/music-core.sh`), with a thin wrapper per step
(`chords.sh`, `mixmatch.sh`, `analyze-stems.sh`, ...) and Python analysis under
`Scripts/`. "Running" it means launching the menu and driving it to a screen a
user would see, or invoking one step and reading its real output — not importing
a function and printing a return value.

Repo root: `/Users/home/Developer/music`. All commands below assume that cwd.

## The one non-obvious rule

**The interactive menu and every `*.sh` wrapper read stdin.** Piping into them,
or running them where stdin is closed, hangs or misfires. There are two clean
ways to run, depending on what you need:

- **Drive the real menu** → wrap it in `tmux` and use `send-keys` / `capture-pane`.
  This is the only faithful way to exercise the menu's own navigation and prompts.
- **Run one step headless** (a smoke test, a bug repro, CI-style) → call the
  arg-driven `lib/music-core.sh` function or a `Scripts/*.py` entry point
  **directly**, never the interactive wrapper. These take arguments, not stdin.

Python steps except `chop.py`/`catalog.py` need the venv's numpy — invoke
`.venv/bin/python` directly rather than relying on `source activate`.

## Drive the interactive menu (tmux)

Use this to verify menu navigation, a submenu entry, or an end-to-end prompt flow.

1. Start a detached session running the menu:

   ```bash
   tmux new-session -d -s music -x 200 -y 50 \
     "cd /Users/home/Developer/music && ./music"
   ```

2. Send a keystroke, wait for the redraw, then capture the pane:

   ```bash
   tmux send-keys -t music 'T' Enter        # T = "More tools" submenu
   sleep 1
   tmux capture-pane -t music -p | tail -30  # read what a user would see
   ```

3. Look at the captured text before the next key — a blank or unchanged pane
   means the step did not run. Keep driving: e.g. `H` Enter opens Chords,
   `X` Enter opens Mix-match, `B` Enter backs out, `Q` Enter quits.

4. Tear down when done:

   ```bash
   tmux kill-session -t music
   ```

**Menu map** (top level): `1` Download · `8` Deconstruct · `2` Separate stems ·
`7` Tempo & key · `3` Chop vocals · `4` Split drums · `6` Sort kit · `5` Chop
stems · `L` Browse tracks · `O` Open Samples/ · `T` More tools · `Q` Quit.
**Tools submenu** (`T`): `A` Stem levels · `H` Chords · `X` Mix-match ·
`M` Bass→MIDI · `R` Re-voice · `P` Build Logic project · `9` Download+chop ·
`B` Back. Steps that need a file prompt for a dragged path; `L` selects a
current track first so the tools have something to act on.

## Run one step headless

Each of these launches the actual step and produces real output/exit code.
Prefer the direct form for smoke tests and bug repros.

```bash
# Chord chart for a Stems folder or an audio file (writes chords.txt beside it)
.venv/bin/python Scripts/chords.py "Stems/htdemucs_6s/02 Let Em' Know"

# Harmonic mix-match over the catalog (add --lyrics for the LRCLIB re-rank)
.venv/bin/python Scripts/catalog.py mix --limit 15
.venv/bin/python Scripts/catalog.py mix --json --lyrics

# Tempo + key estimate
.venv/bin/python Scripts/analyze_track.py "Apple Music/Frank Ocean/Blonde/02 Ivy.m4a"

# A core function with arguments (the wrappers are interactive; these are not)
zsh -c 'source lib/music-core.sh && analyze_track "Stems/htdemucs_6s/02 Let Em' Know"'
```

Check the **exit code** as well as the text: `analyze_track.py` and `chords.py`
exit non-zero on failure (callers gate on this), so a step that prints an error
must also have returned non-zero.

## Verify, don't just launch

- **Menu** → `capture-pane` after each key and read the frame; confirm the
  screen actually changed to the expected step, not that the process merely
  started.
- **A step with a sidecar output** (chords, deconstruct) → confirm the file was
  written (`chords.txt`, `Samples/...`), not only that stdout looked plausible.
- **Mix-match** → with fewer than 2 analyzed catalog tracks it prints a clean
  message and exits non-zero; that is the correct sparse-catalog behavior, not a
  bug.

## Edge cases

- **No tmux / cannot attach** → fall back to headless single-step runs; report
  that the menu path was not exercised.
- **A wrapper appears to hang** → it is almost certainly blocked on stdin. Kill
  it and switch to the arg-driven `lib/music-core.sh` function or `Scripts/*.py`.
- **`chords.py` on a non-stem directory** → an acapella split (vocals.wav +
  no_vocals.wav) is analyzed via its `no_vocals.wav`; any other directory raises
  a clean error and exits non-zero. Both are expected, not crashes.
- **`ModuleNotFoundError: numpy`** → you invoked system python. Use
  `.venv/bin/python`.
- **`analyze_track.py` prints "analysis failed" on `03 Exchange.m4a`** → a known
  corrupt-mvhd quirk in that one file, faithfully surfaced; not a toolkit bug.
- **Empty / unchanged captured pane** → the key did not register or the step did
  not run. Re-send after a longer `sleep`, or read the pane without `tail` to see
  the whole screen before concluding it worked.
