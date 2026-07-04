# Build Logic Project from Stems Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a way to create a new Logic Pro project with a track's 4 stems loaded as audio tracks — as a music-menu option `P)` and as an offer at the end of Deconstruct.

**Architecture:** All Logic automation lives in `logic-pro-mcp`. A new `tools/build.py` holds a pure stem-collector plus a best-effort UI-scripting function that drives Logic (new empty project + one Import Audio dialog). A thin CLI entry `build_project.py` exposes it to the shell menu; the same function registers as MCP tool `logic_new_project_with_stems`. The music toolkit gets a `build_logic_project` core fn and menu wiring.

**Tech Stack:** Python 3 + FastMCP, macOS System Events / AppleScript via `executor.run_applescript`, zsh (music toolkit).

## Global Constraints

- Logic Pro has no AppleScript dictionary — control only via System Events; never `tell application "Logic Pro" to play`.
- AppleScript process name is `"Logic Pro Creator Studio"`; `tell application "Logic Pro"` is used only for `activate`/`open`.
- AppleScript variable names must NOT start with `_`.
- Always `tell application "Logic Pro" to activate` before sending keystrokes.
- All osascript runs through `executor.run_applescript(script, timeout=...)` — never `os.system` or inline subprocess in tool functions.
- Data-returning tools return Python types; action tools return human-readable `str`. This tool is an action → returns `str`.
- Genuine errors `raise ToolError` (`from fastmcp.exceptions import ToolError`).
- No emoji anywhere (code, comments, commit messages, output). Use ASCII (`->`, `[ok]`).
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Reliability tier of the Logic-side path: best-effort UI scripting (same as `bounce.py`); document re-deriving selectors with `entire contents of front window`.
- v1 reports tempo/key in the summary but does NOT set them in Logic (deferred until the LCD/key selectors are verified against a live build).

Paths (absolute):
- MCP repo: `/Users/home/Developer/music/logic-pro-mcp`
- Music repo: `/Users/home/Developer/music`

---

### Task 1: Pure stem collector

**Files:**
- Create: `logic-pro-mcp/tools/build.py`
- Test: `logic-pro-mcp/tests/test_studio.py` (append)

**Interfaces:**
- Produces: `collect_stems(stems_dir: str) -> list[str]` — absolute paths to the stem WAVs to import. Prefers canonical `drums/bass/other/vocals.wav`; falls back to all `*.wav` sorted; raises `ToolError` if the folder is missing or has no `.wav`.

- [ ] **Step 1: Write the failing tests**

Append to `logic-pro-mcp/tests/test_studio.py`:

```python
# ---- build: stem collection (pure) ----

from fastmcp.exceptions import ToolError
from tools import build


def test_collect_stems_canonical_order(tmp_path):
    for n in ("vocals.wav", "drums.wav", "bass.wav", "other.wav"):
        (tmp_path / n).write_bytes(b"RIFF")
    got = build.collect_stems(str(tmp_path))
    assert [Path(p).name for p in got] == ["drums.wav", "bass.wav", "other.wav", "vocals.wav"]


def test_collect_stems_fallback_all_wavs(tmp_path):
    (tmp_path / "guitar.wav").write_bytes(b"RIFF")
    (tmp_path / "piano.wav").write_bytes(b"RIFF")
    got = build.collect_stems(str(tmp_path))
    assert sorted(Path(p).name for p in got) == ["guitar.wav", "piano.wav"]


def test_collect_stems_no_wavs_raises(tmp_path):
    with pytest.raises(ToolError):
        build.collect_stems(str(tmp_path))


def test_collect_stems_missing_dir_raises(tmp_path):
    with pytest.raises(ToolError):
        build.collect_stems(str(tmp_path / "nope"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/home/Developer/music/logic-pro-mcp && .venv/bin/python -m pytest tests/test_studio.py -k collect_stems -q`
Expected: FAIL (`ModuleNotFoundError: tools.build` or `AttributeError: collect_stems`).

- [ ] **Step 3: Write the module with the pure function**

Create `logic-pro-mcp/tools/build.py`:

```python
"""Build a new Logic Pro project pre-loaded with a track's stems.

Reliability: BEST-EFFORT UI scripting. Logic has no AppleScript dictionary, so
this drives the template chooser and a single Import Audio dialog via System
Events. Requires Logic to be running (the tool launches it if needed). If a
Logic update moves a dialog, re-derive selectors with
`entire contents of front window`. Process name is "Logic Pro Creator Studio".

v1 reports the analyzed tempo/key in the summary but does not set them in Logic.
"""

import subprocess
import time
from pathlib import Path

import executor
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

_PROC = 'tell process "Logic Pro Creator Studio"'
_CANONICAL = ("drums.wav", "bass.wav", "other.wav", "vocals.wav")


def collect_stems(stems_dir: str) -> list[str]:
    """Absolute paths of the stem WAVs to import from a Stems/<model>/<track> folder.

    Prefers the canonical drums/bass/other/vocals.wav in that order; falls back
    to every *.wav (sorted). Raises ToolError if the folder is missing or empty.
    """
    d = Path(stems_dir).expanduser()
    if not d.is_dir():
        raise ToolError(f"Not a folder: {stems_dir}")
    canonical = [str(d / n) for n in _CANONICAL if (d / n).exists()]
    if canonical:
        return canonical
    wavs = sorted(str(p) for p in d.glob("*.wav"))
    if not wavs:
        raise ToolError(f"No .wav files in {stems_dir}")
    return wavs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/home/Developer/music/logic-pro-mcp && .venv/bin/python -m pytest tests/test_studio.py -k collect_stems -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/home/Developer/music/logic-pro-mcp
git add tools/build.py tests/test_studio.py
git commit -m "Add collect_stems pure helper for Logic project builder

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: UI-scripting build function + MCP tool

**Files:**
- Modify: `logic-pro-mcp/tools/build.py` (add build fn + register fn)
- Modify: `logic-pro-mcp/server.py` (register the module)
- Test: `logic-pro-mcp/tests/test_studio.py` (append a registration smoke test)

**Interfaces:**
- Consumes: `collect_stems` (Task 1); `executor.run_applescript`, `executor.logic_is_running`, `executor.as_applescript_str`.
- Produces:
  - `build_project_with_stems(stems_dir: str, tempo: float | None = None, key: str | None = None) -> str` — launches/uses Logic, creates an empty project, imports the stems as tracks, returns a summary string. Raises `ToolError` if Logic can't be launched or no stems found.
  - `register_build_tools(mcp: FastMCP) -> None` — registers MCP tool `logic_new_project_with_stems`.

Note: the Logic-side automation cannot be unit-tested (needs a live session). The test here only asserts the tool registers. The osascript sequences are verified manually (see Task 4 live-verification note).

- [ ] **Step 1: Write the failing registration test**

Append to `logic-pro-mcp/tests/test_studio.py`:

```python
def test_build_tool_registers():
    from fastmcp import FastMCP
    m = FastMCP("t")
    build.register_build_tools(m)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/home/Developer/music/logic-pro-mcp && .venv/bin/python -m pytest tests/test_studio.py -k build_tool_registers -q`
Expected: FAIL (`AttributeError: register_build_tools`).

- [ ] **Step 3: Add the build function and registration to `tools/build.py`**

Append to `logic-pro-mcp/tools/build.py`:

```python
def _ensure_logic_running(timeout: float = 30.0) -> None:
    """Launch Logic Pro if needed and wait until System Events sees it."""
    if executor.logic_is_running():
        return
    subprocess.run(["open", "-a", "Logic Pro"], check=False)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if executor.logic_is_running():
            return
        time.sleep(1.0)
    raise ToolError("Logic Pro did not start within 30s — open it and retry.")


def _new_empty_project() -> None:
    """Cmd+N -> best-effort pick 'Empty Project' -> escape the New Tracks sheet.

    The template chooser is the most build-fragile step. If it moves, re-derive
    with `entire contents of front window` and update the click target.
    """
    script = f"""
tell application "Logic Pro" to activate
tell application "System Events"
    {_PROC}
        keystroke "n" using {{command down}}
        delay 1.2
        set picked to false
        try
            repeat with el in (entire contents of front window)
                try
                    set d to (description of el) as string
                    if d contains "Empty Project" then
                        click el
                        set picked to true
                        exit repeat
                    end if
                end try
            end repeat
        end try
        delay 0.4
        try
            click button "Choose" of front window
        end try
        delay 1.0
        key code 53
    end tell
end tell
"""
    executor.run_applescript(script, timeout=20)


def _import_stems(stems_dir: str) -> None:
    """Drive one File > Import > Audio File dialog to add every file in
    stems_dir to new tracks at the playhead."""
    folder = executor.as_applescript_str(str(Path(stems_dir).expanduser()))
    script = f"""
tell application "Logic Pro" to activate
tell application "System Events"
    {_PROC}
        key code 36
        delay 0.3
        click menu item "Audio File..." of menu "Import" of menu item "Import" of menu "File" of menu bar 1
        delay 1.0
        keystroke "g" using {{command down, shift down}}
        delay 0.5
        keystroke "{folder}"
        delay 0.3
        key code 36
        delay 0.6
        key code 36
        delay 0.6
        keystroke "a" using {{command down}}
        delay 0.3
        key code 36
        delay 1.2
        key code 36
    end tell
end tell
"""
    executor.run_applescript(script, timeout=30)


def build_project_with_stems(
    stems_dir: str, tempo: float | None = None, key: str | None = None
) -> str:
    """Create a new Logic project with the stems in stems_dir as audio tracks.

    Best-effort UI scripting: launches Logic if needed, opens an empty project,
    and imports the stems in one dialog. tempo/key are reported for manual entry
    (v1 does not set them). Returns a summary string.
    """
    stems = collect_stems(stems_dir)
    _ensure_logic_running()
    _new_empty_project()
    _import_stems(stems_dir)
    names = ", ".join(Path(s).name for s in stems)
    lines = [
        f"Created a new Logic project and imported {len(stems)} stems as tracks: {names}.",
        "Verify the tracks appear at bar 1; if the import sheet differed, re-run "
        "or complete it in Logic.",
    ]
    if tempo is not None:
        lines.append(f"Set the project tempo to {tempo} (not auto-set in v1).")
    if key:
        lines.append(f"Analyzed key: {key} (set manually if you want it labeled).")
    lines.append("Save with Cmd+S when it looks right.")
    return " ".join(lines)


def register_build_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        annotations={
            "title": "New Logic project from stems",
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": True,
        }
    )
    def logic_new_project_with_stems(
        stems_dir: str, tempo: float | None = None, key: str | None = None
    ) -> str:
        """Create a new Logic Pro project with a folder of stems loaded as tracks.

        stems_dir is a Stems/<model>/<track> folder. Best-effort UI scripting;
        Logic is launched if not already open. tempo/key are reported, not set.
        """
        return build_project_with_stems(stems_dir, tempo, key)
```

- [ ] **Step 4: Register the module in `server.py`**

Modify `logic-pro-mcp/server.py` — add the import next to the others and the register call after `register_library_tools(mcp)`:

```python
from tools.build import register_build_tools
```

```python
register_build_tools(mcp)
```

- [ ] **Step 5: Run tests to verify pass + server imports**

Run: `cd /Users/home/Developer/music/logic-pro-mcp && .venv/bin/python -m pytest tests/test_studio.py -q && .venv/bin/python -c "import server; print('[ok] server imports')"`
Expected: all tests PASS and `[ok] server imports`.

- [ ] **Step 6: Commit**

```bash
cd /Users/home/Developer/music/logic-pro-mcp
git add tools/build.py server.py tests/test_studio.py
git commit -m "Add logic_new_project_with_stems (best-effort UI import)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: CLI entry for the shell menu

**Files:**
- Create: `logic-pro-mcp/build_project.py`
- Test: `logic-pro-mcp/tests/test_studio.py` (append arg-parse test)

**Interfaces:**
- Consumes: `tools.build.build_project_with_stems`.
- Produces: `build_project.parse_args(argv: list[str])` returning a namespace with `stems_dir: str`, `tempo: float | None`, `key: str | None`; and a `main(argv)` that prints the summary and returns an exit code.

- [ ] **Step 1: Write the failing arg-parse test**

Append to `logic-pro-mcp/tests/test_studio.py`:

```python
def test_build_cli_parses_args():
    import build_project
    ns = build_project.parse_args(["/x/Stems/htdemucs/Song", "--tempo", "161.5", "--key", "Am"])
    assert ns.stems_dir == "/x/Stems/htdemucs/Song"
    assert ns.tempo == 161.5
    assert ns.key == "Am"


def test_build_cli_defaults():
    import build_project
    ns = build_project.parse_args(["/x/Stems/htdemucs/Song"])
    assert ns.tempo is None and ns.key is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/home/Developer/music/logic-pro-mcp && .venv/bin/python -m pytest tests/test_studio.py -k build_cli -q`
Expected: FAIL (`ModuleNotFoundError: build_project`).

- [ ] **Step 3: Write `build_project.py`**

Create `logic-pro-mcp/build_project.py`:

```python
#!/usr/bin/env python3
"""CLI wrapper: build a new Logic project from a stems folder.

Invoked by the music toolkit menu so the shell does not need an MCP client.
Usage: build_project.py <stems_dir> [--tempo BPM] [--key KEY]
"""

import argparse
import sys

from fastmcp.exceptions import ToolError
from tools.build import build_project_with_stems


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build a Logic project from a stems folder")
    ap.add_argument("stems_dir")
    ap.add_argument("--tempo", type=float, default=None)
    ap.add_argument("--key", default=None)
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    try:
        print(build_project_with_stems(ns.stems_dir, ns.tempo, ns.key))
    except ToolError as exc:
        print(f"build_project: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/home/Developer/music/logic-pro-mcp && .venv/bin/python -m pytest tests/test_studio.py -k build_cli -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Verify the error path end-to-end (no Logic needed)**

Run: `cd /Users/home/Developer/music/logic-pro-mcp && .venv/bin/python build_project.py /tmp/definitely-not-a-stems-dir; echo "exit=$?"`
Expected: prints `build_project: Not a folder: ...` to stderr and `exit=1`.

- [ ] **Step 6: Commit**

```bash
cd /Users/home/Developer/music/logic-pro-mcp
git add build_project.py tests/test_studio.py
git commit -m "Add build_project.py CLI entry for the music menu

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Music toolkit wiring (core fn + menu)

**Files:**
- Modify: `lib/music-core.sh` (add `build_logic_project`)
- Modify: `music` (add `P)` header line + case; add post-Deconstruct offer to case 8)

**Interfaces:**
- Consumes: `build_project.py` CLI (Task 3); existing `analyze_track` core fn; existing Stems-folder resolution pattern used by menu option 4 / the library picker.
- Produces: `build_logic_project(stems_dir, tempo="", key="")` core fn.

- [ ] **Step 1: Add the core function**

In `lib/music-core.sh`, after `bass_to_midi() { ... }`, add:

```bash
build_logic_project() {
  # $1 = a Stems/<model>/<track> folder, $2 = tempo (optional), $3 = key (optional).
  # Shells out to the logic-pro-mcp CLI, which drives Logic Pro (best-effort UI
  # scripting; Logic is launched if not already open).
  local stems="$1" tempo="$2" key="$3"
  local mcp="$MUSIC_DIR/logic-pro-mcp"
  local py="$mcp/.venv/bin/python"
  [[ ! -x "$py" ]] && { echo "logic-pro-mcp venv not found at $py — set it up first." >&2; return 1; }
  local -a args=("$mcp/build_project.py" "$stems")
  [[ -n "$tempo" ]] && args+=(--tempo "$tempo")
  [[ -n "$key" ]] && args+=(--key "$key")
  "$py" "${args[@]}"
}
```

- [ ] **Step 2: Syntax-check the core lib**

Run: `cd /Users/home/Developer/music && zsh -n lib/music-core.sh && echo "[ok] core syntax"`
Expected: `[ok] core syntax`.

- [ ] **Step 3: Add the `P)` menu header line**

In `music`, in the header `echo` block, add after the `O) Open outputs in Finder` line:

```bash
  echo "P) Build Logic project from stems"
```

- [ ] **Step 4: Add the `P)` case**

In `music`, add a new case before `1)` (next to the other letter cases `M|m` / `O|o`):

```bash
    P|p)
      echo "Drag a Stems track folder (with drums/bass/other/vocals.wav):"; INPUT=$(read_path)
      if [[ ! -d "$INPUT" ]]; then
        echo "Need a Stems track folder."; continue
      fi
      echo "Analyzing for tempo/key…"
      analyze_track "$INPUT"
      build_logic_project "$INPUT"
      ;;
```

- [ ] **Step 5: Add the post-Deconstruct offer to case 8**

In `music`, replace the body of case `8)` deconstruct call so it offers to build after:

Find:

```bash
      deconstruct "$INPUT" "$DENS"
      ;;
```

Replace with:

```bash
      deconstruct "$INPUT" "$DENS"
      read "yn?Build Logic project from these stems now? [y/N]> "
      if [[ "$yn" == (y|Y|yes) ]]; then
        build_logic_project "$SCRIPT_DIR/Stems/htdemucs/${INPUT:t:r}"
      fi
      ;;
```

- [ ] **Step 6: Syntax-check the menu**

Run: `cd /Users/home/Developer/music && zsh -n music && echo "[ok] menu syntax"`
Expected: `[ok] menu syntax`.

- [ ] **Step 7: Verify the menu shows the option and the missing-venv guard (no Logic needed)**

Run: `cd /Users/home/Developer/music && printf 'P\n/tmp\n10\n' | ./music 2>&1 | grep -E "Build Logic project|Need a Stems"`
Expected: shows the `P) Build Logic project from stems` header line and the `Need a Stems track folder.` guard (since `/tmp` is not a stems folder → after the drag prompt it rejects). If instead you pass a real stems folder without Logic set up, expect the `logic-pro-mcp venv not found` message.

- [ ] **Step 8: Commit**

```bash
cd /Users/home/Developer/music
git add music lib/music-core.sh
git commit -m "Add P) Build Logic project from stems menu option + Deconstruct offer

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Live Verification (manual, after Task 4)

Requires Logic Pro installed and Accessibility permission granted to the terminal.

1. Deconstruct or otherwise produce a `Stems/htdemucs/<track>/` folder with the 4 stems.
2. Run `./music` -> `P` -> drag that folder.
3. Confirm: Logic launches (if closed), a new empty project opens, and the 4 stems appear as 4 audio tracks starting at bar 1.
4. If the template chooser or import sheet behaves differently, re-derive the selector in `_new_empty_project` / `_import_stems` using
   `osascript -e 'tell application "System Events" to tell process "Logic Pro Creator Studio" to get entire contents of front window'`
   and update the click targets. This is expected best-effort maintenance.

## Self-Review Notes

- Spec coverage: build tool (Task 2), CLI (Task 3), menu `P)` + Deconstruct offer (Task 4), pure stem collection + tests (Task 1), degradation/ToolError (Tasks 1-3), tier docs in module header (Task 2). Tempo/key auto-set intentionally deferred per Global Constraints (reported only).
- No placeholders; every code step is complete.
- Type consistency: `collect_stems` / `build_project_with_stems` / `register_build_tools` / `parse_args` signatures match across Tasks 1-4.
