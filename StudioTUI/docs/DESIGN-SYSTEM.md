# StudioTUI — Design System & Developer Handoff

The visual language for the Music Studio terminal UI (ratatui 0.29 + crossterm). Single source of
truth for tokens, components, and interaction rules. **If it's not here, it isn't a pattern yet.**

Terminal realities that shape everything below: cells are monospace and fixed-height (1 row), there
is **no hover** (keyboard-only, so "hover" ≡ "cursor/selected"), and **emoji are often double-width
or unsupported** — they break column alignment. Prefer 1-cell glyphs.

---

## 1. Design tokens

All tokens live in `src/theme.rs` as the `Theme` struct. **Rule: never construct a `Color::Rgb(...)`
outside `theme.rs`.** Widgets borrow `&Theme` and reference fields/methods only.

### Color — palette: Atom One Light

| Token | Hex | Role |
|-------|-----|------|
| `bg` | `#FAFAFA` | Page / body background |
| `surface` | `#EFEFEF` | Panel & control-field fill |
| `surface_dark` | `#DEDEDE` | Header & hint-bar fill (chrome) |
| `border` | `#C1C1C1` | Default panel border / dividers |
| `border_hi` | `#4078F2` | Focused/active panel border |
| `fg` | `#383A42` | Primary text |
| `fg_muted` | `#A0A1A7` | Labels, secondary text, disabled |
| `accent` | `#4078F2` | Selection bg, titles, primary action |
| `accent_fg` | `#FAFAFA` | Text on accent bg |
| `success` | `#50A14F` | Ok logs, online, play, playhead-num |
| `error` | `#E45649` | Error logs, offline, stop/record |
| `warning` | `#C18401` | Worker-busy, cautions |
| `seq_pad_off` | `#D7D7D7` | Sequencer inactive pad |
| `seq_pad_on` | `#4078F2` | Sequencer active pad |
| `seq_playhead` | `#C8E6C8` | Sequencer current-step wash |
| `seq_hit` | `#50A14F` | Active pad under playhead |

### Style constructors (semantic — prefer these over raw `.fg().bg()`)
`t.normal()` · `t.muted()` · `t.surface()` · `t.accent()` · `t.success()` · `t.error()` ·
`t.warning()` · `t.border()` · `t.border_hi()`.

### Spacing & layout
- Ratatui `Layout` only; no manual padding math except inside grids (sequencer).
- Frame vertical rhythm: header `Length(1)` · tab bar `Length(2)` · body `Fill(1)` · console `Length(8)`.
- Panels use `Borders::ALL` + a `Length`-sized region; absorb leftover space with a trailing
  `Fill(1)` gap, **not** by stretching a panel (avoids dead space inside a box).
- Sub-dividers between columns/cells: `Borders::LEFT` with `t.border()` — never a full box per cell.

### Typography (terminal has one font; "weight" = modifier)
- Emphasis = `Modifier::BOLD`. Selection = `Modifier::BOLD` on accent bg.
- Focused text input = `Modifier::UNDERLINED | BOLD` in `accent`.
- Never `REVERSED` for selection on wide rows (it inverts the whole cell run unpredictably); reserve
  `REVERSED` only for the single-cell sequencer cursor.

### Glyphs (1-cell, alignment-safe)
Action icons: `⭳ ⚙ ▤ ⟳ ◈ ▦ ◉ ▥ ✦ ♪ ♫ ⌂`. Markers: `▸` (selected), `│` (divider), `●/○`
(online/offline). Sequencer pads: `██` on · `··` off · `░░` playhead · `▓▓` hit.
**Avoid** multi-width emoji (🎧💾📄⏏⇩ etc.) in fixed-width button rows — they shift columns.

---

## 2. Components

### Tab bar (`ui/mod.rs`)
Top-level nav. Active tab = `accent` bg + `accent_fg` + BOLD; inactive = `fg_muted` on `surface`.
Keys `1–4` select. Divider `"  "`.

### Panel (Block) — base container
`Block::new().title(" TITLE ").borders(ALL).border_style(t.border()).style(bg)`.
- Title: `accent`, often BOLD, padded with spaces ` TITLE `.
- Variant **focused/active**: `border_style(t.border_hi())` (e.g. Library file list, busy Console).
- Fill: `bg` for content panels, `surface` for parameter/control panels.

### Action row (list item) — `ui/pipeline.rs`, `ui/library.rs`
One selectable line: `{marker} {glyph}  {label}`.
| State | Style |
|-------|-------|
| Default | `fg` on panel fill |
| Selected | `accent` bg + `accent_fg` + BOLD, `▸` marker |
| Disabled/unmapped | `fg_muted`, trailing ` ·` |

### Param cell — `ui/pipeline.rs`
Compact 2-line label/value chip: label in `fg_muted`, value in `accent` BOLD. First cell no divider;
rest get `Borders::LEFT`. Used for STEM MODE / DENSITY / CHOP / TEMPO.

### Button — `ui/logic.rs`
Bordered box with a **key hint prefix**: `[key] glyph Label`. This is the convention for
non-list actions — every button advertises its shortcut inline.
| State | Style |
|-------|-------|
| Enabled | `accent` bg (primary) / `surface` (secondary) |
| Danger (stop/record) | `error` bg |
| Disabled (offline) | `fg_muted` on `surface_dark` |

### Sequencer pad grid — `ui/sequencer.rs`
16 columns × 6 rows. 4/4 beat-group `│` dividers every 4 steps. Cursor = `REVERSED` (single cell).
Playhead column tinted `seq_playhead`; active+playhead = `seq_hit`.

### Console log — `ui/pipeline.rs::ConsoleLog`
Bottom strip, last N lines. Level colors: Ok→`success`, Err→`error`, Info→`fg_muted`, Plain→`fg`.
Border goes `border_hi` while a worker runs; title shows `⏳ running…`.

### Hint bar — `ui/pipeline.rs::render_hint` (shared)
One line on `surface_dark`, `fg_muted`. Format: `key action · key action · … · q quit`. Every tab
ends with one. **All interactive tabs must render a hint bar.**

### Status line — `ui/logic.rs`
`●/○` + label + `key: value` pairs in `fg_muted`/`fg`. Online border tints `success`.

---

### Help overlay (`ui/mod.rs`) — `?`
Centered floating panel over the body (`Clear` then Block with `border_hi`), two columns:
global keys · active-tab keys. Closes on `?`/`Esc`. Single source: `app::keymap_for(tab)`.

### Badge — `ui/library.rs`
Inline metadata chip appended to a row: ` ⟨93·F min⟩ ` in `fg_muted` (selected rows:
`accent_fg`). Sourced from the catalog map; absent when unknown. Never truncate the badge —
truncate the path instead.

### Filter field — `ui/library.rs`
One line above the file list: `/ pattern` in `accent` + UNDERLINED while focused, `fg_muted`
otherwise. Empty + unfocused = hidden (zero height).

### Queue indicator — header (`ui/mod.rs`)
`⧗ N queued` in `warning` on `surface_dark` when the job queue is non-empty; joins the
existing `⏳ running…` worker indicator. Watch mode shows `◉ watch` in `success`.

---

## 3. Interaction conventions

- **Key routing:** input focus (captures all printable keys) → tab handler → global fallback.
  A tab may claim a "global" key (Logic claims `c` for connect); hints must reflect it.
- **Global:** `1–4` tabs · `q` quit · `?` help overlay · `0` theme toggle · `c` clear console ·
  `r` refresh · `W` watch mode.
- **Lists:** `j/k` or `↑/↓` move · `Enter`/`Space` primary action.
- **Categories/params:** `←/→` (and `h/l`) cycle. Number keys are reserved for tabs.
- **Text inputs:** enter with a mnemonic key (`u` URL, `t` tempo, `n` name, `b` BPM, `/` filter),
  `Enter`/`Esc` commits/leaves. Focus style = `accent` + UNDERLINED|BOLD.
- **Buttons advertise their key** in the label (`[x] ■ Stop`). List rows do not (they use `Enter`).
- **Selection is always** accent bg + accent_fg + BOLD.
- Destructive/record actions use `error` color, never a confirm dialog (terminal) — rely on color.

---

## 3b. Functions & automations

The TUI shells out to `lib/music-core.sh` functions directly (never the interactive `*.sh`
wrappers — they `read` from stdin and would hang the app). `worker::run_zsh` runs
`zsh -c 'source lib/music-core.sh; <fn> <quoted args> 2>&1'` with `stdin` nulled; all output
streams to the console panel.

| Function | Core call | Params from UI |
|----------|-----------|----------------|
| Download | `download_url url out` | URL field |
| Analyze BPM+Key | `analyze_track src` | source track |
| Separate Stems | `separate_stems src mode Stems` | STEM MODE |
| Full Pipeline | queue: analyze → separate → chop_vocals | STEM MODE, DENSITY |
| Chop Drums | `chop_drums stemdir Samples/One-Shots dens` | stem folder, DENSITY |
| Sort Kit | `sort_kit Samples/One-Shots/<track>` | stem folder |
| Chop Vocals | `chop_vocals stemdir/vocals.wav … dens` | stem folder, DENSITY |
| Chop Stems | `chop_stems stemdir Samples/Chops secs` | stem folder, CHOP |
| Deconstruct | `deconstruct src dens` | source, DENSITY |
| Bass → MIDI / Re-voice / Build Logic | arg-accepting wrappers | stem folder |

**Automations**

- **Job queue** — every action enqueues; jobs run serially, auto-advancing on `Done`.
  `Esc` (Pipeline) cancels pending jobs. Header shows `⧗ N queued`.
- **Batch deconstruct** — `a` on Pipeline enqueues `deconstruct` for every source track.
- **Watch mode** — `W` toggles a 2-second rescan of `Apple Music/`, `SoundCloud/`,
  `Downloads/`; new audio files are logged and auto-queued for deconstruct (the local twin
  of the scheduled `auto-deconstruct-new-tracks` task).
- **Catalog integration** — startup reads `Scripts/catalog.py ready --json` into a
  `track → (bpm, key)` map; Library Stems rows show `⟨bpm·key⟩` badges.
- **Pattern persistence** — sequencer `S`/`L` saves/loads `Samples/Patterns/<name>.pattern`
  (plain text: `bpm=`, `bars=`, `kit=`, six 16-char 0/1 rows).
- **Kit-aware WAV export** — `K` cycles kits (subfolders of `Samples/One-Shots`); sample
  lookup for the sequencer's WAV bounce is scoped to the selected kit.

---

## 4. Audit — current state

**Score: 82/100.** Solid token discipline; a few alignment and parity gaps.

| Area | Status | Note |
|------|--------|------|
| Color tokens | ✅ | Centralized in `theme.rs`; no hardcoded RGB in widgets. |
| Selection highlight | ✅ | Consistent accent-bg convention across panels. |
| Hint bars | ✅ | Present on all four tabs. |
| Glyph consistency | ⚠️ | Pipeline uses the 1-cell set; **Logic buttons still use double-width emoji** (💾📄⏏⇩🎧) → column drift. Replace with 1-cell glyphs. |
| Dead space | ⚠️ | Pipeline actions panel leaves a gap below; acceptable but could host a preview/BPM readout. |
| Theme flexibility | ⚠️ | Only `Theme::light()` exists; header hardcodes the label "Atom One Light". No dark variant. |
| Dead-code | ⚠️ | 4 unused `Theme` style methods (`success/error/...`) warn on build — keep (they're the API) or `#[allow(dead_code)]`. |
| Functional parity | ⚠️ | Params render but aren't editable/wired; sequencer name/bars/kit static; library reveal + BPM badges absent; `?` help overlay missing. (Tracked in `docs/PLAN.md` pass 2.) |

### Roadmap (executed in docs/PLAN.md pass 3)
1. **Fix key routing** — input focus → tab handler → global; unshadows Logic `c`,
   removes Library's dead number keys.
2. **Swap Logic-button emoji for 1-cell glyphs** — the single most visible alignment fix.
3. **Wire params + sequencer fields** — stem mode / density / chop / tempo cycle and reach
   the core functions; sequencer name/bpm/bars/kit editable.
4. **Automations** — job queue, batch deconstruct, watch mode, catalog badges,
   pattern save/load (§3b).
5. **Add a `?` help overlay** — centralizes the keymap that's currently only in hint bars.
6. **`Theme::dark()` behind `0`** — dynamic palette name in the header.
7. **Use the Theme style ctors in widgets** — removes dead-code warnings for real.

---

## 5. Rules for contributors
1. New color? Add a `Theme` field — never inline `Color::Rgb`.
2. New action button? Prefix its shortcut `[k]` and use a 1-cell glyph.
3. New selectable list? Use the accent-bg selection convention and add its keys to the tab's hint bar.
4. Keep each `ui/<tab>.rs` self-contained; the entry point is `Tab { app }.render(area, buf)` — don't
   change that signature (it's the seam `mod.rs` renders through).
5. Verify visually in tmux: `tmux new -d -s s -x132 -y44 './target/debug/studio-tui'; tmux capture-pane -t s -p`.
