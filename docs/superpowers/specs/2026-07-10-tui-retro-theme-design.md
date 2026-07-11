# StudioTUI Retro-Terminal Re-theme — Design

## Context

`StudioTUI` (the ratatui-based music-studio TUI at `StudioTUI/`) just finished a
"pass 3" wiring effort: every rendered control is now backed by real behavior
(job queue, live params, watch mode, catalog badges, pattern save/load, a
theme toggle, a help overlay). That work deliberately left the visual design
untouched — it kept the existing Atom One Light/Dark palette and thin
single-line borders from `docs/DESIGN-SYSTEM.md`.

This spec is a follow-up visual-only pass: replace the Atom One Light/Dark
theme pair with a retro-terminal aesthetic, requested directly by the user
during a brainstorming session. No functional behavior changes.

## Goals

- Give the app a distinct retro-terminal identity: pale LCD-green in light
  mode, phosphor-green CRT in dark mode.
- Add a small number of retro flourishes (double-line panel borders, a
  stylized header wordmark, blink on pending-state indicators) without
  compromising the density and legibility the existing multi-panel layout
  depends on.
- Keep the change scoped to `theme.rs` + the `ui/*.rs` render files (plus one
  string comparison in `app.rs`). No changes to `app.rs` state, key routing,
  job queue, or any other functional code from the pass-3 work.

## Non-goals

- No glyph/iconography changes (the existing 1-cell glyph set from
  `docs/DESIGN-SYSTEM.md` §1 already reads as terminal-appropriate).
- No sequencer pad-symbol changes (`██ ·· ▓▓ ░░` stays).
- No layout/panel-position changes.
- No new functional features (this is a pure re-skin).

## Design

### 1. Palette — two new named themes

Both remain `Theme::light()` / `Theme::dark()` (same function signatures,
same fields, same style-constructor methods) so `app.rs`'s `toggle_theme`
logic keeps working unchanged apart from one string literal (see "Touch
points" below). Only the `name` and color values change.

**`Theme::light()` → "LCD Green"** (pale Game-Boy-LCD character, softened for
extended reading):

| Token | Hex | Role |
|---|---|---|
| `bg` | `#C4D9A8` | Page / body background |
| `surface` | `#B8CE98` | Panel & control-field fill |
| `surface_dark` | `#A3BD82` | Header & hint-bar chrome |
| `border` | `#4A6741` | Default panel border |
| `border_hi` | `#1F3D1A` | Focused/active border |
| `fg` | `#1F3D1A` | Primary text |
| `fg_muted` | `#5C7A4E` | Secondary/disabled text |
| `accent` | `#2D5F2A` | Selection bg, titles |
| `accent_fg` | `#E8F0D8` | Text on accent bg |
| `success` | `#2D5F2A` | Ok logs, online, play |
| `error` | `#B33A3A` | Error logs, offline, stop/record |
| `warning` | `#A67C00` | Busy, cautions |
| `seq_pad_off` | `#A3BD82` | Sequencer inactive pad |
| `seq_pad_on` | `#2D5F2A` | Sequencer active pad |
| `seq_playhead` | `#D9E6C0` | Sequencer current-step wash |
| `seq_hit` | `#1F3D1A` | Active pad + playhead |

**`Theme::dark()` → "Phosphor CRT"** (classic green-on-black terminal):

| Token | Hex | Role |
|---|---|---|
| `bg` | `#0A0F0A` | Page / body background |
| `surface` | `#0F1A0F` | Panel & control-field fill |
| `surface_dark` | `#060A06` | Header & hint-bar chrome |
| `border` | `#1F4D1F` | Default panel border |
| `border_hi` | `#33FF33` | Focused/active border |
| `fg` | `#33FF33` | Primary text |
| `fg_muted` | `#1F8F1F` | Secondary/disabled text |
| `accent` | `#66FF66` | Selection bg, titles |
| `accent_fg` | `#0A0F0A` | Text on accent bg |
| `success` | `#33FF33` | Ok logs, online, play |
| `error` | `#FF5555` | Error logs, offline, stop/record |
| `warning` | `#FFB000` | Busy, cautions |
| `seq_pad_off` | `#123312` | Sequencer inactive pad |
| `seq_pad_on` | `#33FF33` | Sequencer active pad |
| `seq_playhead` | `#1F4D1F` | Sequencer current-step wash |
| `seq_hit` | `#66FF66` | Active pad + playhead |

The existing "never construct `Color::Rgb` outside `theme.rs`" rule
(`docs/DESIGN-SYSTEM.md` §1) is unchanged and still applies — these values
only live in `theme.rs`.

### 2. Borders — double-line on main panels only

Add a `pub border_type: ratatui::widgets::BorderType` field to `Theme`, set
to `BorderType::Double` for both new themes (both themes want the retro
double-line look, so this isn't actually theme-differentiated today, but
living on `Theme` keeps the door open and keeps border style centrally
controlled rather than hardcoded per call site).

Apply `t.border_type` (via `.border_type(t.border_type)` on the `Block`) to
exactly these panels:

- Pipeline: PARAMETERS, ACTIONS, CONSOLE
- Sequencer: STEP SEQUENCER grid
- Logic: STATUS
- Library: CATEGORIES, file list
- Help overlay (`ui/mod.rs`)

Everything else — the small BPM/BARS/KIT/NAME control-field boxes, the
sequencer's per-column beat-group dividers, param-cell `Borders::LEFT`
dividers, and every individual Logic button box — stays on the default thin
single-line border. Double-lining every small box would make the dense
multi-panel layout look cluttered; reserving it for the ~8 outer container
panels keeps the retro frame readable while the fine internal structure
stays quiet.

### 3. Header banner

`ui/mod.rs::render_header` currently renders a single `Span::styled(" ♪
Music Studio ", ...)`. Replace with a spaced-caps, block-flanked wordmark,
still a single `Span` fitting the existing `Length(1)` header row, e.g.:

```
▓▓ M U S I C   S T U D I O ▓▓
```

The header row height does not change (stays `Length(1)` in `RootView`'s
vertical layout) — a true multi-line ASCII banner was considered and
rejected because it would permanently cost 2-3 rows out of an already tight
layout (console alone needs `Length(8)`). Theme name / worker / queue /
watch indicators that already follow the wordmark are unchanged in position
and logic, just repainted in the new palette.

### 4. Blink — three pending-state indicators only

Ratatui/crossterm support `Modifier::SLOW_BLINK`. Apply it to exactly:

1. Header `⏳ running…` worker indicator (`ui/mod.rs::render_header`) —
   blinks while `app.worker_rx.is_some()`.
2. Header `◉ watch` indicator (`ui/mod.rs::render_header`) — blinks while
   `app.watch_on`.
3. Logic tab's status dot (`ui/logic.rs::render_status`) — blinks while
   `app.logic_status_pending` (a status check is in flight).

Blink is deliberately *not* applied to anything that changes every frame
(e.g. the sequencer playhead) — a terminal-driven blink cadence fighting a
16th-note playhead would look chaotic, and the existing color/glyph
distinction already communicates that state clearly. Blink here means
"something is pending/ongoing in the background," a narrow, consistent
semantic.

### Touch points (files)

- `theme.rs` — new `Theme::light()`/`Theme::dark()` color values + names
  ("LCD Green" / "Phosphor CRT"), new `border_type` field.
- `ui/mod.rs` — header wordmark + blink on running/watch indicators, help
  overlay border upgraded to `t.border_type`.
- `ui/pipeline.rs` — PARAMETERS/ACTIONS/CONSOLE panels get `t.border_type`.
- `ui/sequencer.rs` — STEP SEQUENCER grid panel gets `t.border_type`.
- `ui/logic.rs` — STATUS panel gets `t.border_type`; status dot blink.
- `ui/library.rs` — CATEGORIES + file list panels get `t.border_type`.
- `app.rs` — one string-literal fix: `toggle_theme` currently compares
  `self.theme.name == "Atom One Light"` to decide which theme to switch to;
  update the literal to the new light-theme name ("LCD Green").

No other `app.rs` logic changes — key routing, job queue, watch mode,
catalog integration, sequencer editing, and library actions are all
untouched.

## Testing / verification

- `cargo build` clean (same bar as the pass-3 work: no new errors, no new
  warnings beyond the pre-existing dead-code set).
- tmux-capture all 4 tabs + help overlay in both themes (`0` toggles),
  confirm double-line borders render on the intended panels only and thin
  borders remain elsewhere, confirm the header wordmark and any active blink
  indicators display correctly.
- Manually trigger each blink condition (start a pipeline job, toggle watch
  mode, connect to Logic while `logic_status_pending`) to confirm all three
  fire and stop correctly.
