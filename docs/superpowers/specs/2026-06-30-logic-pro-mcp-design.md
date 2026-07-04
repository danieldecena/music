# Logic Pro Creator Studio — MCP Server Design

**Date:** 2026-06-30
**Server (exists):** `~/Developer/projects/logic-pro-mcp/`
**Skill (exists):** `~/.claude/skills/logic-pro-mcp/` (`SKILL.md` + `references/automation.md`)
**Asset pipeline (this repo):** `~/Developer/music/` (`lib/music-core.sh`, `Scripts/chop.py`)
**Framework:** Python + FastMCP, stdio, local. **App:** Logic Pro 12 **Creator Studio** edition.
**Status:** BUILT (2026-06-30) — Phases A–D done, unified into one server (34 tools, 11 tests
passing). App-control tools await a live-session smoke test. Not yet committed to git.

> **Build log:** doc-drift fixed; added `tracks.py` (4), `bounce.py` (2), `config.py`,
> `pipeline.py` (4: download/separate_stems/chop_vocals/run_full), `library.py` (7), hardened
> executor/project/session; `tests/test_studio.py` (11 pass), `evals/logic_studio_eval.xml`.
> Decision taken: **one unified studio MCP**. Verified loading under FastMCP 3.4.2 / Python 3.14.

---

## 1. Reality check — what already exists

This is **not** a greenfield build. A working FastMCP server is already on disk and partially
implemented. The job is to **extend and harden it**, not recreate it.

### 1.1 The hard constraint (confirmed by the skill + Apple docs)
Logic Pro ships **no AppleScript dictionary** (`.sdef`). `tell application "Logic Pro" to play`
does nothing. All interactive control goes through **System Events (Accessibility API) +
keyboard shortcuts**. `tell application "Logic Pro"` still works for `open`/`activate` only.

**Creator Studio specifics:** the System Events **process name is `"Logic Pro Creator Studio"`**
(Logic Pro 12 Creator Studio edition), already hardcoded throughout the server.

### 1.2 Automation tiers (from `references/automation.md`, in priority order)
1. **Keystroke** — transport, undo, navigation (`keystroke " "` = play/stop).
2. **Menu navigation** — actions with no shortcut (`click menu item … of menu bar 1`).
3. **Accessibility read** — state queries (tempo/key/position via text-field scraping).
4. **`.logicx` bundle XML** — inspect a project when Logic isn't even open (`projectData` file).

### 1.3 Current server inventory (`~/Developer/projects/logic-pro-mcp/`)
```text
server.py        FastMCP("logic-pro") + 4 register_* calls
executor.py      run_applescript(script, timeout) + logic_is_running()
tools/
  transport.py   ✅ logic_play, logic_stop, logic_record, logic_go_to_start,
                    logic_rewind, logic_fast_forward
  project.py     ✅ logic_get_current_project, logic_open_project, logic_save, logic_new_project
  session.py     ✅ logic_get_tempo, logic_get_key, logic_get_bar_position
  utility.py     ✅ logic_undo, logic_redo, logic_navigate_menu, logic_get_status
requirements.txt fastmcp>=2.0.0, mcp>=1.0.0
.mcp.json        registers server as "logic-pro"
CLAUDE.md        run/setup/structure notes
```
~17 tools, all implemented and routed through `executor.run_applescript()`. Has `.venv` + git.

## 2. Gap analysis — existing vs. desired "Creator Studio" MCP

| Area | Now | Gap to close |
|---|---|---|
| Transport | ✅ full | — |
| Project open/save/new | ✅ basic | new_project just sends Cmd+N (leaves a dialog); no template selection, no `.logicx` inspection |
| Session read | ✅ tempo/key/position | brittle: scrapes *every* text field and pattern-matches. No `.logicx` fallback when app is closed |
| Utility | ✅ undo/redo/menu/status | — |
| **Tracks** | ❌ none | `SKILL.md` claims a `tracks.py` that does **not exist**: list/add/mute/solo |
| **Bounce / export** | ❌ none | no `File > Bounce…` / `Export` driver |
| **Mixer** | ❌ none | show/hide mixer, basic channel ops |
| **Asset pipeline** | ❌ separate repo | download/stems/chop live in `music/` shell, not exposed as MCP tools |
| **Library** | ❌ none | no Projects/Samples/Stems/Exports listing or organize ops |
| Tests | ❌ none | no `tests/`; pipeline shell has `tests/test-core.sh` to mirror |
| Eval | ❌ none | no Phase-4 eval per mcp-builder |
| Annotations | ❌ none | tools lack `readOnlyHint`/`destructiveHint` etc. |
| Doc drift | ⚠️ | `SKILL.md` mislabels project/session as stubs and lists nonexistent `tracks.py` |

## 3. Doc-drift fixes (cheap, do first)

`SKILL.md` and reality disagree. Correct `SKILL.md` so it documents what's actually there:
- project.py / session.py / utility.py are **implemented**, not stubs.
- Remove the phantom `tracks.py` from the tree (or keep it listed as *planned*, clearly marked).
- Keep `references/automation.md` as the source of truth for recipes — it's accurate.

## 4. Phased plan

### Phase A — Track management + bounce (the biggest functional gap) ★ highest value
New `tools/tracks.py`: `logic_list_tracks`, `logic_add_track`, `logic_mute_track`,
`logic_solo_track` — built from the accessibility/menu recipes already in `automation.md`.
New `tools/bounce.py`: `logic_bounce` (drives `File > Bounce > Project or Section…`, best-effort
UI, returns the expected Exports path to poll). Register both in `server.py`.

### Phase B — Harden what exists
- `session.py`: add `.logicx` `projectData` XML fallback so tempo/key work with Logic closed.
- `project.py`: `logic_open_project` — validate path + `.logicx` existence with an actionable error.
- Add MCP **annotations** to every tool (read-only vs destructive vs open-world).
- `executor.py`: distinguish "Accessibility not granted" from "Logic not running" in errors.

### Phase C — Unify the studio (bring the `music/` pipeline in) ★ the "creator studio" vision
New `tools/pipeline.py` shelling out to `~/Developer/music/lib/music-core.sh`:
`pipeline_download`, `pipeline_separate_stems`, `pipeline_chop_vocals`, `pipeline_run_full`.
New `tools/library.py`: list/organize `Projects/{Active,Archive,Templates}`,
`Samples/*`, `Stems`, `Exports/{Drafts,Finals}`; `new_project_from_template`,
`archive_project`, `promote_export` (write-once guard). `MUSIC_ROOT` from config/env.
> Decision needed (§6 Q1): one unified server, or keep app-control and pipeline as two MCPs.

### Phase D — Tests + eval
- `tests/` (pytest): pipeline arg-mapping (mirror `tests/test-core.sh`), library ops on a temp
  root, executor error handling. App-control tools verified manually against a live session.
- `evals/logic_studio_eval.xml`: 10 read-only questions (mostly library/`.logicx` inspection,
  since they must be stable + verifiable per mcp-builder Phase 4).
- MCP Inspector smoke test; `npx @modelcontextprotocol/inspector` or `claude mcp list`.

## 5. Conventions to keep (from the skill, hard-won)
- AppleScript variables must **not** start with `_`.
- Always `tell application "Logic Pro" to activate` before keystrokes.
- One osascript call per action (no shell state between calls).
- `key code` (numeric) for non-letters; `keystroke` for letters (locale-safe).
- All osascript goes through `executor.run_applescript()` — never inline subprocess.
- Process name is `"Logic Pro Creator Studio"` for System Events.

## 6. Open questions
1. **One server or two?** Fold the `music/` pipeline into `logic-pro-mcp` (one "studio" MCP), or
   keep DAW-control and asset-pipeline as separate servers that an agent composes?
2. **Start where?** Recommend **Phase A** (tracks + bounce) — it's the largest capability gap and
   pure DAW value. Phase C is the bigger "creator studio" vision but depends on Q1.
3. **Track ops fragility** — list/add/mute/solo rely on accessibility tree + selection state, which
   shift by Logic version. OK to ship them clearly labeled best-effort, with a UI-tree dump helper
   for re-deriving selectors when they break?

## 7. Recommendation
Do the **doc-drift fixes (§3)** + **Phase A** first: corrects the skill, closes the biggest gap,
and needs no architectural decision. Resolve Q1 before Phase C.

---

### Sources on Logic scriptability
- Apple Developer Forums — AppleScript for Logic Pro X: https://developer.apple.com/forums/thread/115355
- Apple Support — Use Scripter in Logic Pro: https://support.apple.com/guide/logicpro/use-scripter-lgce728c68f6/mac
- Apple Support — Supported control surfaces: https://support.apple.com/guide/logicpro/supported-control-surfaces-ctls718dd5b2/mac
