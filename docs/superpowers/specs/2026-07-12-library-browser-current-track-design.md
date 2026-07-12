# Library browser + persistent current track — design

**Date:** 2026-07-12
**Status:** Approved, pending implementation plan

## Problem

The `music` menu's `L` (Browse music library) is a raw filesystem `find` across
`Apple Music/`, `SoundCloud/`, `Downloads/` with an optional substring filter. As the
collection grows this breaks down:

1. **The library never feeds the pipeline.** `L`'s action submenu only offers 4 of the
   steps (deconstruct / separate / analyze / chop vocals). Split drums, chop stems, sort
   kit, MIDI, revoice, Logic-build are drag-from-Finder only — so locating a track
   dead-ends.
2. **No persistent selection.** Every menu loop forgets `INPUT`. Running two steps on one
   track means dragging it from Finder twice.
3. **No status awareness.** Selecting a track never surfaces that it's already
   deconstructed or already has stems, so work gets silently redone.

The repo already has the data to fix all three: `Scripts/catalog.py` / `catalog.sqlite`
stores per-track `artist`, `album`, `bpm`, `key`, `model`, `deconstructed_at`, plus asset
counts. `catalog.py scan` indexes **every** source file into `tracks` (deconstructed ones
have `model` set; source-only ones do not), so the catalog is a complete library index
after a scan.

## Goal

Optimize `L` for **finding a specific track**, make the picked track a **persistent
current track** that every pipeline step reuses, and surface **status** so nothing gets
redone blindly.

## Design

### 1. Data source — catalog-backed `L`

- On entering `L`, run `catalog.py scan` (cheap sqlite; picks up freshly-downloaded
  tracks) before querying, so the browser is never stale.
- Add one new catalog subcommand so no SQL leaks into the zsh script:

  ```
  catalog.py search <query> [--json]
  ```

  - Substring-matches `<query>` (case-insensitive) against `name`, `artist`, `album`.
  - Blank/empty query returns all tracks.
  - Returns, per row: `name`, `source_path`, `artist`, `album`, `bpm`, `key`, `model`
    (null = source-only), and asset counts (`stems`, `kit`, `oneshots`, `chops`,
    `vocals`) — reuse the existing `_counts_for` helper.
  - Sort: deconstructed tracks first by `deconstructed_at DESC`, then source-only by
    name.
  - `--json` emits a JSON array (the shell parses this); default prints a human table.

### 2. Browser UX

```
Search (blank = all, /text to refine, Enter = back)> daft
 1) Daft Punk / One More Time     123 BPM  F#m  [deconstructed: 4 stems, kit, 812 shots]
 2) Daft Punk / Harder Better...  123 BPM  Em   [source only]
Pick #>
```

- Blank search lists all, capped at **40** rows with a `+N more — refine search` note.
- Columns: index, `artist / title`, bpm, key, status badge.
  - Status badge: `[deconstructed: N stems, kit, M shots]` when `model` is set (compact,
    drop zero-count segments), else `[source only]`. `?` for unknown bpm/key.
- At the `Pick #>` prompt:
  - a number selects that row and sets the current track (see §3),
  - `/text` re-runs the search with a new query,
  - empty Enter returns to the main menu.
- Empty result set: `No matches for '<query>'.` and re-prompt for search.

### 3. Persistent current track

- Selecting a row sets shell globals `CUR_SRC` (absolute source path) and `CUR_NAME`
  (track stem, i.e. filename without extension — the catalog `name` / `Stems/<model>/`
  folder key). Also cache `CUR_LABEL` (`artist / title  bpm key  [status]`) for the
  header.
- The main menu prints a header line above `Music Toolkit` **only when a current track is
  set**:

  ```
  Current: Daft Punk / One More Time  123 BPM F#m  [deconstructed]
  ─────────────────────────────────────────────────────────────
  ```

- Add a `C) Clear current track` entry to the Tools & shortcuts group (visible only when a
  track is set is acceptable but not required; simplest is always-listed). Re-picking via
  `L` replaces the current track.

### 4. Steps reuse the current track

A small resolver decides each step's input. When a current track is set, it becomes the
default; dragging/typing a path still overrides for that one invocation.

Prompt shape:

```
Input: [Enter] = Daft Punk / One More Time   (or drag a different file)>
```

Resolution by step:

- **2 Separate, 7 Analyze, 8 Deconstruct** → resolve to `CUR_SRC` (the source audio).
- **3 Chop vocals, 4 Split drums, 5 Chop stems, M Bass→MIDI, P Build Logic** → resolve to
  the stems location `Stems/<model>/<CUR_NAME>/` (prefer `htdemucs`, fall back to
  `htdemucs_6s`, matching the existing lookup in the `L` chop-vocals branch).
  - If no stems exist yet for `CUR_NAME`:
    `No stems for <CUR_NAME> yet — run Separate (2) or Deconstruct (8) first.` and return
    to the menu.
- **R Re-voice** keeps its drag-only flow (it operates on an arbitrary monophonic stem,
  not a whole-track concept) but still accepts `[Enter]` = current track's stems folder if
  a sensible default exists; otherwise unchanged. Lowest priority — fine to leave R as-is
  if it complicates the resolver.
- When **no** current track is set, every step behaves exactly as today (drag prompt).

The resolver is a single helper (e.g. `resolve_input <mode>` where mode is `source` or
`stems`) that echoes the chosen path or empty; callers keep their existing validation.

### 5. Status guards

Before **Separate (2)** or **Deconstruct (8)** run on a track whose catalog row already
has `model` set:

```
<CUR_NAME> already deconstructed (htdemucs). Re-run? [y/N]>
```

Default No. Only guards when acting on the current track (we know its status); a dragged
arbitrary path is not looked up. Prevents blind, expensive redoes.

## Out of scope (YAGNI)

- Query operators (`bpm:120`, `key:Am`) — plain substring only. Revisit if needed.
- Pagination beyond the 40-row cap + count note.
- Any rename / tag / delete from the browser — read + select only.
- Triage/status-grouped browsing (the "decide what to work on" mode) — this spec is the
  "find a specific track" mode.

## Affected files

- `Scripts/catalog.py` — add `search` subcommand (+ argparse wiring); reuse `_counts_for`.
- `music` — rewrite the `L` case arm (catalog-backed search + select); add the current-
  track header + globals; add `C` clear arm; thread the resolver through the `2,3,4,5,7,8`
  and `M,P` case arms; add the status-guard prompt to `2` and `8`.

## Testing

- `tests/test-core.sh` covers pure arg-mapping helpers; the new `search` output is a good
  candidate for a lightweight assertion (seed a temp catalog, assert JSON shape).
- Manual: scan a folder with a mix of deconstructed + source-only tracks; verify search,
  selection, header persistence across a Separate→Split-drums sequence with no re-drag,
  and the already-deconstructed guard.
