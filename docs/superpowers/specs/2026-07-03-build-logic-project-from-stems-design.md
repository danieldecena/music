# Build Logic Project from Stems — Design

Date: 2026-07-03
Status: Approved, pending implementation plan

## Context

The music toolkit deconstructs a song into stems, one-shots, kit, snippets, and
vocal chops. Getting those back into Logic Pro to start a flip is currently
manual: open Logic, make a project, drag stems onto tracks, set tempo. This
feature adds a one-step "create a new Logic Pro project with the stems already
loaded as tracks."

Deconstruct produces very different asset types (4 stems vs. hundreds of
one-shots/snippets/vocal chops). Loading everything as tracks is rarely useful,
so this feature imports **only the 4 stems** (`drums/bass/other/vocals`) as 4
audio tracks and presets the analyzed tempo/key as guidance. Other assets stay
on disk.

Logic Pro has no AppleScript dictionary; all control is System Events + keyboard
UI scripting (see `logic-pro-mcp/CLAUDE.md`). Every Logic-side step here is
therefore best-effort UI scripting and requires Logic to be open. The stems
folder `Stems/htdemucs/<track>/` already contains exactly the 4 stem WAVs and
nothing else, which makes a single "Import Audio File" dialog (select-all →
import to new tracks) viable instead of brittle per-file scripting.

## Architecture

All Logic automation lives in the repo that owns it (`logic-pro-mcp`); the music
shell menu calls into it. Three pieces:

1. `logic-pro-mcp/tools/build.py` — a pure function plus MCP registration.
2. `logic-pro-mcp/build_project.py` — a thin CLI entry the shell menu invokes.
3. `lib/music-core.sh` + `music` — a core function and menu wiring.

### 1. `tools/build.py`

`build_project_with_stems(stems_dir: str, tempo: float | None = None, key: str | None = None) -> str`

Steps:
1. Validate `stems_dir` exists. Collect stem WAVs: prefer the canonical
   `drums.wav, bass.wav, other.wav, vocals.wav`; if none of those exist, fall
   back to all `*.wav` in the folder. Raise `ToolError` if the folder has no
   `.wav` files.
2. Ensure Logic running: if `executor.logic_is_running()` is false, launch with
   `open -a "Logic Pro"` and poll `logic_is_running()` up to ~30s. Raise
   `ToolError` on timeout.
3. New empty project: `tell application "Logic Pro" to activate`, Cmd+N to open
   the template chooser, best-effort select "Empty Project" and confirm, then
   Escape the "New Tracks" sheet so the subsequent import creates the tracks.
4. Go to start (playhead to bar 1), then one import:
   `File > Import > Audio File…` → Cmd+Shift+G → type `stems_dir` → Return →
   Cmd+A (select all) → Import/Open → confirm the "add to new tracks" sheet.
   Result: each stem lands on its own new audio track at bar 1.
5. Tempo: if `tempo` given, best-effort set it in the LCD (non-fatal on
   failure). Key: reported in the return string only — Logic's key control is
   not cleanly settable via UI, and scripting the score editor is out of scope
   (YAGNI).
6. Return a human-readable summary: what was imported, and the tempo/key to set
   manually if auto-set did not stick.

`register_build_tools(mcp)` wraps the function as MCP tool
`logic_new_project_with_stems` (annotations: not read-only, not destructive,
openWorld). Registered in `server.py` alongside the other 8 modules.

The AppleScript follows existing conventions: process name
`"Logic Pro Creator Studio"`, no leading-underscore AppleScript variables,
`activate` before keystrokes, all osascript via `executor.run_applescript`.

### 2. `build_project.py` (CLI entry)

Argparse: `stems_dir` (positional), `--tempo` (float, optional), `--key`
(str, optional). Calls `build_project_with_stems(...)`, prints the summary,
exits non-zero on `ToolError`. This is the shell-callable surface so the menu
does not need an MCP client.

### 3. Music toolkit wiring

`lib/music-core.sh`:
- New `build_logic_project(stems_dir, tempo, key)` — invokes
  `"$LOGIC_MCP_DIR/.venv/bin/python" "$LOGIC_MCP_DIR/build_project.py" "$stems_dir" [--tempo …] [--key …]`,
  where `LOGIC_MCP_DIR="$MUSIC_DIR/logic-pro-mcp"`. Prints a clear message if
  that venv/script is missing.

`music` (interactive menu):
- New option `P) Build Logic project from stems`: prompt for a track that has
  stems (reuse the existing `Stems/<model>/<track>` resolution used by option 4
  and the library picker), run `analyze_track` to display tempo/key for
  guidance, then call `build_logic_project`.
- Case 8 (Deconstruct): after `deconstruct` returns, prompt
  `Build Logic project now? [y/N]`; on yes, call `build_logic_project` on
  `Stems/htdemucs/<track>` (the 4stem model deconstruct uses).

The "offer after deconstruct" prompt lives in the interactive menu layer, not in
the non-interactive `deconstruct()` core function.

## Error Handling / Degradation

- Logic not installed or launch times out → `ToolError` with a clear message; no
  project created.
- No `.wav` in `stems_dir` → `ToolError`.
- Template chooser / import dialog shape differs across Logic builds → best-effort
  UI scripting; the tool docstring and module header note re-deriving selectors
  with `entire contents of front window`, matching `tracks.py` / `bounce.py`.
- Tempo auto-set failure → non-fatal; the analyzed tempo is always printed for
  manual entry.

Reliability tier: ★ best-effort (same as `logic_bounce`). Documented as such in
the module header and `logic-pro-mcp/CLAUDE.md` tool-tier table.

## Testing

- pytest (`logic-pro-mcp/tests/`) covers the pure, non-UI parts:
  - stem-WAV collection (canonical names present; fallback to all `*.wav`;
    empty folder raises `ToolError`) using a temp directory of dummy files.
  - `build_project.py` CLI arg parsing.
- The UI-scripting path is verified manually against a live Logic session (Logic
  open, run the `P)` option on a real stems folder, confirm 4 tracks appear).
  It cannot be unit-tested.
- `zsh -n music` and `zsh -n lib/music-core.sh` syntax checks; existing
  `tests/test-core.sh` remains green (unchanged core arg helpers).

## Out of Scope (YAGNI)

- Importing one-shots / snippets / vocal chops as tracks or staging them.
- Auto-saving the project to `Projects/<track>.logicx` (user saves with Cmd+S).
- Scripting Logic's key signature.
- A Logic project template beyond the built-in Empty Project.
