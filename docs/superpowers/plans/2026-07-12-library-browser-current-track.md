# Library Browser + Persistent Current Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the `music` menu's `L` browser into a catalog-backed track search whose selection becomes a persistent "current track" that every pipeline step reuses, with status awareness so work isn't blindly redone.

**Architecture:** Add a `search` subcommand to `Scripts/catalog.py` (the data backbone; stdlib sqlite). Rewrite the `L` case arm in `music` to call it, display results, and set current-track shell globals shown in a menu header. A shared resolver lets steps 2/3/4/5/7/8 and M/P reuse the current track instead of re-dragging; status guards prevent redoing deconstructs.

**Tech Stack:** zsh (`music`, `lib/music-core.sh`), Python 3 stdlib (`Scripts/catalog.py`), hand-rolled zsh + Python test assertions (no framework).

## Global Constraints

- No `set -e` in `music` — a failed step returns to the menu, never exits (see `music:2-3`).
- Python steps run via `/opt/homebrew/bin/python3`; `catalog.py` is stdlib-only (no venv needed to import it). In-shell, invoke it exactly as the existing call does: `"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/Scripts/catalog.py"` (mirrors `lib/music-core.sh:253`).
- Asset `kind` values in the catalog are singular: `stem`, `oneshot`, `kit`, `chop`, `vocal`.
- Stems live at `Stems/<model>/<name>/` where `<model>` is `htdemucs` (4/2-stem) or `htdemucs_6s` (6-stem); prefer `htdemucs`, fall back to `htdemucs_6s` (matches `music:96-98`).
- No emoji anywhere. Match existing file style; no comments restating what code does.
- Out of scope (do NOT build): query operators (`bpm:120`), pagination beyond the 40-row cap, any rename/tag/delete, status-grouped triage browsing.

---

### Task 1: `catalog.py search` subcommand

**Files:**
- Modify: `Scripts/catalog.py` (add `_search_rows`, `_label`, `cmd_search`; argparse + dispatch wiring near `Scripts/catalog.py:329` and `:355`)
- Test: `tests/test-catalog.py` (create)

**Interfaces:**
- Consumes: existing `init(con)`, `_counts_for(con, name)` (returns `{kind: count}` dict), `connect()`.
- Produces:
  - `_search_rows(con, query) -> list[dict]` — each dict has keys `name, source_path, artist, album, bpm, key, model, deconstructed_at, stems, kit, oneshots, chops, vocals`. Sorted deconstructed-first (`model IS NOT NULL`) by `deconstructed_at DESC`, then by `name`.
  - `_label(row) -> str` — one-line human label.
  - `cmd_search(con, query, as_json, menu)` — prints `--json` array, tab-delimited `--menu` feed (`name\tsource_path\tlabel`), or a numbered human table.
  - CLI: `catalog.py search <query> [--json] [--menu]` (query optional; blank = all).

- [ ] **Step 1: Write the failing test**

Create `tests/test-catalog.py`:

```python
#!/opt/homebrew/bin/python3
import sqlite3, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Scripts"))
import catalog

con = sqlite3.connect(":memory:")
con.row_factory = sqlite3.Row
catalog.init(con)
con.execute(
    "INSERT INTO tracks(name,source_path,artist,album,bpm,key,model,deconstructed_at,first_seen) "
    "VALUES(?,?,?,?,?,?,?,?,?)",
    ("One More Time", "Apple Music/One More Time.m4a", "Daft Punk", "Discovery",
     123, "F#m", "htdemucs", "2026-07-12T00:00:00", "2026-07-11T00:00:00"),
)
con.execute(
    "INSERT INTO tracks(name,source_path,first_seen) VALUES(?,?,?)",
    ("Random Track", "Downloads/Random Track.mp3", "2026-07-11T00:00:00"),
)
con.execute("INSERT INTO assets(track,kind,subtype,path,mtime) "
            "VALUES('One More Time','stem','vocals','x/vocals.wav',0)")
con.commit()

hit = catalog._search_rows(con, "daft")
assert len(hit) == 1 and hit[0]["name"] == "One More Time", hit
assert hit[0]["stems"] == 1, hit[0]

nohit = catalog._search_rows(con, "zzz")
assert nohit == [], nohit

allrows = catalog._search_rows(con, "")
assert len(allrows) == 2, allrows
assert allrows[0]["model"] is not None, "deconstructed must sort first"

label = catalog._label(hit[0])
assert "Daft Punk" in label and "123 BPM" in label and "F#m" in label, label
assert "deconstructed" in label, label

print("ok: catalog search")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3 tests/test-catalog.py`
Expected: FAIL with `AttributeError: module 'catalog' has no attribute '_search_rows'`

- [ ] **Step 3: Add the implementation**

In `Scripts/catalog.py`, add these functions above `def main(argv):` (after `cmd_stats`):

```python
def _search_rows(con, query):
    init(con)
    params = []
    where = ""
    if query:
        like = f"%{query.lower()}%"
        where = ("WHERE lower(name) LIKE ? OR lower(coalesce(artist,'')) LIKE ? "
                 "OR lower(coalesce(album,'')) LIKE ? ")
        params = [like, like, like]
    sql = ("SELECT name, source_path, artist, album, bpm, key, model, deconstructed_at "
           f"FROM tracks {where}"
           "ORDER BY (model IS NULL), deconstructed_at DESC, name")
    out = []
    for r in con.execute(sql, params).fetchall():
        c = _counts_for(con, r["name"])
        out.append({
            "name": r["name"], "source_path": r["source_path"],
            "artist": r["artist"], "album": r["album"],
            "bpm": r["bpm"], "key": r["key"], "model": r["model"],
            "deconstructed_at": r["deconstructed_at"],
            "stems": c.get("stem", 0), "kit": c.get("kit", 0),
            "oneshots": c.get("oneshot", 0), "chops": c.get("chop", 0),
            "vocals": c.get("vocal", 0),
        })
    return out


def _label(row):
    title = row["name"]
    who = f"{row['artist']} / {title}" if row["artist"] else title
    bpm = f"{row['bpm']} BPM" if row["bpm"] else "? BPM"
    key = row["key"] or "?"
    if row["model"]:
        segs = []
        if row["stems"]:
            segs.append(f"{row['stems']} stems")
        if row["kit"]:
            segs.append("kit")
        if row["oneshots"]:
            segs.append(f"{row['oneshots']} shots")
        badge = "deconstructed" + (": " + ", ".join(segs) if segs else "")
    else:
        badge = "source only"
    return f"{who}  {bpm}  {key}  [{badge}]"


def cmd_search(con, query, as_json, menu):
    rows = _search_rows(con, query)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False))
    elif menu:
        for r in rows:
            print(f"{r['name']}\t{r['source_path'] or ''}\t{_label(r)}")
    else:
        for i, r in enumerate(rows, 1):
            print(f"{i:3d}) {_label(r)}")
        if not rows:
            print("(no matches)")
```

Then wire the subcommand. After `Scripts/catalog.py:329` (`backfill` parser) add:

```python
    p = sub.add_parser("search"); p.add_argument("query", nargs="?", default=""); p.add_argument("--json", action="store_true"); p.add_argument("--menu", action="store_true")
```

And in the dispatch chain, after the `backfill` branch (`Scripts/catalog.py:355-356`) add:

```python
        elif ns.cmd == "search":
            cmd_search(con, ns.query, ns.json, ns.menu)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/opt/homebrew/bin/python3 tests/test-catalog.py`
Expected: `ok: catalog search`

Also smoke-test the CLI end to end:
Run: `/opt/homebrew/bin/python3 Scripts/catalog.py search "" --menu`
Expected: tab-delimited lines (or nothing if the real catalog is empty; no traceback).

- [ ] **Step 5: Commit**

```bash
git add Scripts/catalog.py tests/test-catalog.py
git commit -m "catalog: add search subcommand for the library browser

Substring search over name/artist/album returning bpm/key/status and
asset counts, sorted deconstructed-first. --json for tests, --menu for
the zsh browser, default a numbered human table.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Catalog-backed `L` browser + current-track globals + header

**Files:**
- Modify: `music` — rewrite the `L|l)` case arm (`music:65-106`); add the current-track header to the menu print block (before `music:15`); add a `C|c)` clear arm; declare globals near the top.

**Interfaces:**
- Consumes: `catalog.py search --menu` from Task 1 (tab-delimited `name\tsource_path\tlabel`).
- Produces: shell globals `CUR_SRC` (absolute source path), `CUR_NAME` (track stem = catalog `name`), `CUR_LABEL` (display string) — read by Tasks 3 and 4.

- [ ] **Step 1: Add current-track globals and header**

Near the top of `music`, after `read_path() { ... }` (`music:11`), add:

```zsh
CUR_SRC=""; CUR_NAME=""; CUR_LABEL=""
```

In the menu print block, insert the header immediately after `echo ""` at `music:14` (before `echo "Music Toolkit"`):

```zsh
  if [[ -n "$CUR_NAME" ]]; then
    echo "Current: $CUR_LABEL"
    echo "------------------------------------------------------------"
  fi
```

Add a `C) Clear current track` line to the Tools group; change the `Q) Quit` line (`music:30`) to:

```zsh
  echo "                              C) Clear current track   Q) Quit"
```

- [ ] **Step 2: Rewrite the `L` case arm**

Replace the whole `L|l)` arm (`music:65-106`) with:

```zsh
    L|l)
      "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/Scripts/catalog.py" scan >/dev/null 2>&1
      read "q?Search (blank = all, name/artist)> "
      lines=("${(@f)$("$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/Scripts/catalog.py" search "$q" --menu 2>/dev/null)}")
      lines=("${(@)lines:#}")
      [[ ${#lines} -eq 0 ]] && { echo "No matches. (Download or Scan first if the library is new.)"; continue; }
      total=${#lines}
      shown=$(( total > 40 ? 40 : total ))
      echo "Music library:"
      for i in {1..$shown}; do
        printf " %2d) %s\n" "$i" "${${(s:	:)lines[$i]}[3]}"
      done
      (( total > shown )) && echo "  ... +$(( total - shown )) more — refine your search."
      read "n?Pick a file #> "
      if [[ -z "$n" || ! "$n" == <-> || "$n" -lt 1 || "$n" -gt $shown ]]; then echo "Cancelled."; continue; fi
      picked=("${(s:	:)lines[$n]}")
      CUR_NAME="${picked[1]}"
      CUR_SRC="$SCRIPT_DIR/${picked[2]}"
      CUR_LABEL="${picked[3]}"
      echo "Selected: $CUR_LABEL"
      ;;
    C|c)
      CUR_SRC=""; CUR_NAME=""; CUR_LABEL=""
      echo "Current track cleared."
      ;;
```

Note: `source_path` from the catalog is repo-relative (`_rel`), so prefix `$SCRIPT_DIR/`. The literal tabs in `(s:	:)` and `${...:#}` splitting must be real tab characters.

- [ ] **Step 3: Verify the browser end to end**

Run: `printf 'L\n\n\nC\nQ\n' | ./music` (search blank, then a pick attempt, clear, quit)
Expected: prints "Music library:" with numbered rows if the catalog has tracks, or the "No matches" line on an empty catalog; no zsh errors. Then re-run picking row 1 and confirm the header `Current: ...` appears on the next menu render:
Run: `printf 'L\n\n1\nQ\n' | ./music` — expect a `Current: <label>` line before the second `Music Toolkit`.

Also confirm syntax: `zsh -n music` prints nothing.

- [ ] **Step 4: Commit**

```bash
git add music
git commit -m "music: catalog-backed L browser + persistent current track

L now searches the catalog (name/artist/album) showing bpm/key/status
instead of a raw find, and the picked track persists as a Current-track
header carried across menu loops. Adds C) to clear it.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Resolver + source-input steps reuse (2, 7, 8) with status guard

**Files:**
- Modify: `lib/music-core.sh` — add `stems_dir_for` helper.
- Modify: `music` — add `resolve_input` shell function; thread it through the `2)`, `7)`, `8)` arms; add the already-deconstructed guard to `2)` and `8)`.
- Test: `tests/test-core.sh` — add assertions for `stems_dir_for`.

**Interfaces:**
- Consumes: `CUR_SRC`, `CUR_NAME` globals from Task 2.
- Produces:
  - `stems_dir_for <name>` (in `music-core.sh`) — echoes the existing `Stems/<model>/<name>` dir (`htdemucs` preferred, else `htdemucs_6s`), or empty string if none exists. Uses `$MUSIC_DIR` (already defined in music-core).
  - `resolve_input <mode>` (in `music`) — `mode=source`: prompts `Input: [Enter] = <CUR_LABEL> (or drag a different file)>`, echoes `CUR_SRC` on empty input else the dragged path; when no current track, falls back to the plain `read_path` drag prompt. Echoes chosen path (may be empty).

- [ ] **Step 1: Write the failing test for `stems_dir_for`**

Add to `tests/test-core.sh` before `exit $fail`:

```zsh
# stems_dir_for: prefers htdemucs, falls back to htdemucs_6s, empty when none
MUSIC_DIR=$(mktemp -d)
mkdir -p "$MUSIC_DIR/Stems/htdemucs_6s/Song"
assert_eq "$(stems_dir_for Song)" "$MUSIC_DIR/Stems/htdemucs_6s/Song" "stems_dir_for falls back to 6s"
mkdir -p "$MUSIC_DIR/Stems/htdemucs/Song"
assert_eq "$(stems_dir_for Song)" "$MUSIC_DIR/Stems/htdemucs/Song" "stems_dir_for prefers htdemucs"
assert_eq "$(stems_dir_for Missing)" "" "stems_dir_for empty when none"
rm -rf "$MUSIC_DIR"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `zsh tests/test-core.sh`
Expected: FAIL — `stems_dir_for: command not found` (non-zero exit).

- [ ] **Step 3: Implement `stems_dir_for`**

Add to `lib/music-core.sh` (near the other small helpers):

```zsh
stems_dir_for() {  # echoes existing Stems/<model>/<name> dir, htdemucs preferred
  local name="$1" m
  for m in htdemucs htdemucs_6s; do
    if [[ -d "$MUSIC_DIR/Stems/$m/$name" ]]; then
      print -- "$MUSIC_DIR/Stems/$m/$name"; return 0
    fi
  done
  return 0
}
```

Confirm `MUSIC_DIR` is defined in `music-core.sh` (grep it); if the surrounding helpers use `$MUSIC_DIR`, reuse it as-is.

- [ ] **Step 4: Run test to verify it passes**

Run: `zsh tests/test-core.sh`
Expected: all `ok:` lines including the three new `stems_dir_for` assertions; exit 0.

- [ ] **Step 5: Add `resolve_input` and thread through steps 2, 7, 8**

In `music`, after the `read_path()` helper, add:

```zsh
resolve_input() {  # mode=source: current track's source, else a dragged path
  if [[ -n "$CUR_SRC" ]]; then
    local p; read "p?Input: [Enter] = $CUR_LABEL  (or drag a different file)> "
    if [[ -z "$p" ]]; then print -- "$CUR_SRC"; return; fi
    p="${p//\\ / }"; print -- "${p%"${p##*[! ]}"}"
  else
    echo "Drag a file or folder:"; read_path
  fi
}
```

In the `2)` arm (`music:158-170`), replace `echo "Drag a file or folder:"; INPUT=$(read_path)` with:

```zsh
      INPUT=$(resolve_input source)
```

Then, still in `2)`, before running separation, add the guard (only when acting on the current track):

```zsh
      if [[ "$INPUT" == "$CUR_SRC" && -n "$CUR_NAME" ]] && [[ -n "$(stems_dir_for "$CUR_NAME")" ]]; then
        read "yn?$CUR_NAME already has stems. Re-run? [y/N]> "
        [[ "$yn" == (y|Y|yes) ]] || continue
      fi
```

In the `7)` arm (`music:198-202`), replace the drag prompt with `INPUT=$(resolve_input source)`.

In the `8)` arm (`music:203-213`), replace `echo "Drag an audio file to deconstruct:"; INPUT=$(read_path)` with `INPUT=$(resolve_input source)`, and add the same guard block as in `2)` (using `stems_dir_for "$CUR_NAME"` / the `deconstructed` check) right after the `[[ ! -f "$INPUT" ]]` validation.

- [ ] **Step 6: Verify**

Run: `zsh -n music` (syntax) — no output.
Run: `printf 'L\n\n1\n7\n\nQ\n' | ./music` — after picking row 1, choosing 7 (Analyze) should show the `Input: [Enter] = <label>` prompt and, on Enter, analyze the current track without a drag. Confirm no "Invalid path".

- [ ] **Step 7: Commit**

```bash
git add lib/music-core.sh music tests/test-core.sh
git commit -m "music: source-input steps reuse current track + stem guard

Adds resolve_input so Separate/Analyze/Deconstruct default to the current
track instead of forcing a drag, plus stems_dir_for (dedupes the existing
model-lookup) and an already-has-stems guard to prevent blind redoes.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Stems-input steps reuse (3, 4, 5, M, P) with "no stems yet" guard

**Files:**
- Modify: `music` — thread current-track resolution through the `3)`, `4)`, `5)`, `M|m)`, `P|p)` arms; refactor the `L` chop-vocals stem lookup to `stems_dir_for`.

**Interfaces:**
- Consumes: `CUR_NAME`, `CUR_LABEL` globals (Task 2); `stems_dir_for <name>` (Task 3).
- Produces: none (leaf UI wiring).

- [ ] **Step 1: Add a stems-resolution helper**

In `music`, after `resolve_input`, add:

```zsh
resolve_stems() {  # echoes current track's Stems dir, or a dragged path; empty if unavailable
  if [[ -n "$CUR_NAME" ]]; then
    local d; d="$(stems_dir_for "$CUR_NAME")"
    if [[ -n "$d" ]]; then
      local p; read "p?Stems: [Enter] = $CUR_NAME  (or drag a folder/stem)> "
      if [[ -z "$p" ]]; then print -- "$d"; return; fi
      p="${p//\\ / }"; print -- "${p%"${p##*[! ]}"}"
      return
    fi
    echo "No stems for $CUR_NAME yet — run Separate (2) or Deconstruct (8) first." >&2
  fi
  read_path
}
```

- [ ] **Step 2: Thread through steps 3, 4, 5**

In `3)` (`music:171-178`), `4)` (`music:179-186`), `5)` (`music:187-192`), replace each `echo "Drag ..."; INPUT=$(read_path)` (and, in 3/4, the blank→`Stems` default line) with:

```zsh
      INPUT=$(resolve_stems)
      [[ -z "$INPUT" ]] && continue
```

Keep each arm's existing `[[ ! -e "$INPUT" ]]` validation and the rest of its body unchanged.

- [ ] **Step 3: Thread through M and P**

In `M|m)` (`music:107-120`), replace `echo "Drag a bass.wav or a Stems track folder:"; INPUT=$(read_path)` with `INPUT=$(resolve_stems); [[ -z "$INPUT" ]] && continue`. The existing `if [[ -d "$INPUT" ]]` bass.wav-finding logic still applies.

In `P|p)` (`music:124-130`), replace `echo "Drag a Stems track folder ...:"; INPUT=$(read_path)` with `INPUT=$(resolve_stems); [[ -z "$INPUT" ]] && continue`. Keep the `[[ ! -d "$INPUT" ]]` check.

- [ ] **Step 4: Refactor the `L` chop-vocals stem lookup to `stems_dir_for`**

If the `L` action submenu still contains the inline `for m in htdemucs htdemucs_6s` vocals lookup (originally `music:96-98`), and Task 2 preserved a chop-vocals action, replace that loop's directory discovery with `stems_dir_for "$track"` + `/vocals.wav`. If Task 2's rewrite removed that submenu entirely, skip this step.

- [ ] **Step 5: Verify**

Run: `zsh -n music` — no output.
Run: `printf 'L\n\n1\n4\nQ\n' | ./music` — after picking a *deconstructed* row 1, choosing 4 (Split drums) shows `Stems: [Enter] = <name>` and proceeds without a drag. Pick a *source-only* track instead and choose 4: expect `No stems for <name> yet — run Separate (2) or Deconstruct (8) first.` and a clean return to the menu.

- [ ] **Step 6: Commit**

```bash
git add music
git commit -m "music: stem-input steps reuse current track

Chop vocals/drums/stems and Bass->MIDI/Build-Logic now default to the
current track's Stems folder via resolve_stems, with a clear 'no stems
yet' message instead of an invalid-path error. Dedupes the model lookup
onto stems_dir_for.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §1 Data source (catalog-backed, scan-on-entry, `search` subcommand) → Task 1 (subcommand) + Task 2 (browser calls it). NOTE: the spec calls for `catalog.py scan` on `L` entry; Task 2's browser calls `search` directly. Scan-on-entry is added as **Task 2, Step 2**: prepend `"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/Scripts/catalog.py" scan >/dev/null 2>&1` before the `search` call so freshly-downloaded tracks appear. (Folded into Task 2 to keep the browser self-contained.)
- §2 Browser UX (search prompt, 40 cap, columns, status badge, cancel) → Task 1 `_label` + Task 2 arm.
- §3 Persistent current track (globals, header, clear) → Task 2.
- §4 Steps reuse (resolver, source vs stems, no-stems message) → Task 3 (source: 2/7/8) + Task 4 (stems: 3/4/5/M/P). R left as-is per spec's "lowest priority / fine to leave."
- §5 Status guards (already-deconstructed re-run prompt) → Task 3, Step 5.

**Placeholder scan:** No TBD/TODO; every code step shows full code. The one conditional (Task 4 Step 4) is gated on Task 2's outcome with an explicit skip condition, not a placeholder.

**Type consistency:** `_search_rows`/`_label`/`cmd_search` signatures match between Task 1's definition and Task 2's `--menu` consumption (tab fields `name\tsource_path\tlabel`). `stems_dir_for` defined in Task 3, consumed in Tasks 3 and 4 with the same single-arg `<name>` signature. Globals `CUR_SRC/CUR_NAME/CUR_LABEL` named identically across Tasks 2–4.

**Correction applied inline:** Added the scan-on-entry step to Task 2 (was implied by the spec but missing from the first task draft).
