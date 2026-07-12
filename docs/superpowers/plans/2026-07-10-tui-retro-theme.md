# StudioTUI Retro-Terminal Re-theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace StudioTUI's Atom One Light/Dark theme with a retro-terminal
aesthetic (pale LCD-green light theme, phosphor-CRT dark theme), double-line
borders on main panels, a stylized header wordmark, and blink on three
pending-state indicators — a pure visual re-skin, no functional changes.

**Architecture:** All color/style data lives in one place (`theme.rs`); every
`ui/*.rs` render function already consumes colors exclusively through `&Theme`
fields and style constructors (never raw `Color::Rgb`), so the re-theme is
almost entirely a `theme.rs` edit. The only other changes are: one string
literal in `app.rs` (theme-name comparison), a border-type + blink pass over
5 `ui/*.rs` files, and a new header wordmark string.

**Tech Stack:** Rust, ratatui 0.29, crossterm 0.28 (no new dependencies).

## Global Constraints

- No `Color::Rgb(...)` outside `theme.rs` (docs/DESIGN-SYSTEM.md §1) — every
  task below only ever reads `t.<field>` in `ui/*.rs`.
- `cargo build` must stay clean of new warnings/errors at the end of every
  task (the codebase currently sits at 3 pre-existing dead-code warnings —
  do not add to that count, and it's fine if this work doesn't reduce it).
- No changes to `app.rs` behavior/state beyond the one string literal in
  Task 2 — key routing, job queue, watch mode, catalog integration,
  sequencer editing, and library actions are all out of scope.
- Verification convention: this codebase has no Rust unit-test harness for
  rendering (verified via `docs/DESIGN-SYSTEM.md`'s own acceptance criteria
  and the prior pass-3 session, both of which used `cargo build` + tmux
  capture, not unit tests) — Task 1 is the one exception, where a pure
  in-file `#[cfg(test)]` module is cheap and directly guards against the
  exact class of bug (a stale theme-name string) already seen once in this
  project. All other tasks verify via `cargo build` + targeted tmux capture.
- tmux capture pattern used throughout: `tmux new -d -s s -x140 -y46
  './target/debug/studio-tui'` from `StudioTUI/`, then `tmux send-keys -t s
  '<key>' ''; sleep 0.3; tmux capture-pane -t s -p`, finishing with `tmux
  send-keys -t s 'q' ''; tmux kill-session -t s`.

---

### Task 1: Theme palette + border type (`theme.rs`)

**Files:**
- Modify: `StudioTUI/src/theme.rs` (entire file — every color value changes,
  plus one new field)

**Interfaces:**
- Consumes: nothing (this is the foundational task).
- Produces: `Theme` struct gains `pub border_type: ratatui::widgets::BorderType`.
  `Theme::light().name == "LCD Green"`, `Theme::dark().name == "Phosphor
  CRT"` (was `"Atom One Light"` / `"Atom One Dark"` — Task 2 depends on the
  new light-theme name). All existing fields (`bg`, `surface`,
  `surface_dark`, `border`, `border_hi`, `fg`, `fg_muted`, `accent`,
  `accent_fg`, `success`, `error`, `warning`, `seq_pad_off`, `seq_pad_on`,
  `seq_playhead`, `seq_hit`) and all style-constructor methods (`normal()`,
  `muted()`, `surface()`, `accent()`, `success()`, `error()`, `warning()`,
  `border()`, `border_hi()`) keep their exact same names/signatures — every
  `ui/*.rs` file keeps compiling unchanged against this task's output.

Struct-field additions mean this can't follow the strict red-test-first
cycle (a test referencing a not-yet-existing field won't compile, not just
fail) — so this task writes the full new file in one step, then verifies
with both `cargo test` and `cargo build`.

- [ ] **Step 1: Replace the full contents of `theme.rs`**

```rust
use ratatui::style::{Color, Style};
use ratatui::widgets::BorderType;

/// Centralised palette. All widget rendering borrows `&Theme` — never
/// hardcodes colours. `name` feeds the header so the label always matches.
pub struct Theme {
    pub name:         &'static str,
    pub border_type:  BorderType,
    // Backgrounds
    pub bg:           Color,
    pub surface:      Color,
    pub surface_dark: Color,
    // Borders / dividers
    pub border:       Color,
    pub border_hi:    Color,
    // Text
    pub fg:           Color,
    pub fg_muted:     Color,
    // Accent / brand
    pub accent:       Color,
    pub accent_fg:    Color, // text on accent bg
    // Status
    pub success:      Color,
    pub error:        Color,
    pub warning:      Color,
    // Sequencer
    pub seq_pad_off:  Color, // inactive pad
    pub seq_pad_on:   Color, // active (toggled) pad
    pub seq_playhead: Color, // current-step highlight
    pub seq_hit:      Color, // active pad + playhead
}

impl Theme {
    pub fn light() -> Self {
        // LCD Green — pale Game-Boy-LCD character, softened for extended reading.
        Self {
            name:         "LCD Green",
            border_type:  BorderType::Double,
            bg:           Color::Rgb(196, 217, 168), // #C4D9A8
            surface:      Color::Rgb(184, 206, 152), // #B8CE98
            surface_dark: Color::Rgb(163, 189, 130), // #A3BD82
            border:       Color::Rgb(74, 103, 65),   // #4A6741
            border_hi:    Color::Rgb(31, 61, 26),    // #1F3D1A
            fg:           Color::Rgb(31, 61, 26),    // #1F3D1A
            fg_muted:     Color::Rgb(92, 122, 78),   // #5C7A4E
            accent:       Color::Rgb(45, 95, 42),    // #2D5F2A
            accent_fg:    Color::Rgb(232, 240, 216), // #E8F0D8
            success:      Color::Rgb(45, 95, 42),    // #2D5F2A
            error:        Color::Rgb(179, 58, 58),   // #B33A3A
            warning:      Color::Rgb(166, 124, 0),   // #A67C00
            seq_pad_off:  Color::Rgb(163, 189, 130), // #A3BD82
            seq_pad_on:   Color::Rgb(45, 95, 42),    // #2D5F2A
            seq_playhead: Color::Rgb(217, 230, 192), // #D9E6C0
            seq_hit:      Color::Rgb(31, 61, 26),    // #1F3D1A
        }
    }

    pub fn dark() -> Self {
        // Phosphor CRT — classic green-on-black terminal.
        Self {
            name:         "Phosphor CRT",
            border_type:  BorderType::Double,
            bg:           Color::Rgb(10, 15, 10),    // #0A0F0A
            surface:      Color::Rgb(15, 26, 15),    // #0F1A0F
            surface_dark: Color::Rgb(6, 10, 6),      // #060A06
            border:       Color::Rgb(31, 77, 31),    // #1F4D1F
            border_hi:    Color::Rgb(51, 255, 51),   // #33FF33
            fg:           Color::Rgb(51, 255, 51),   // #33FF33
            fg_muted:     Color::Rgb(31, 143, 31),   // #1F8F1F
            accent:       Color::Rgb(102, 255, 102), // #66FF66
            accent_fg:    Color::Rgb(10, 15, 10),    // #0A0F0A
            success:      Color::Rgb(51, 255, 51),   // #33FF33
            error:        Color::Rgb(255, 85, 85),   // #FF5555
            warning:      Color::Rgb(255, 176, 0),   // #FFB000
            seq_pad_off:  Color::Rgb(18, 51, 18),    // #123312
            seq_pad_on:   Color::Rgb(51, 255, 51),   // #33FF33
            seq_playhead: Color::Rgb(31, 77, 31),    // #1F4D1F
            seq_hit:      Color::Rgb(102, 255, 102), // #66FF66
        }
    }

    // ── Convenience style constructors ────────────────────────────────────
    pub fn normal(&self)    -> Style { Style::new().fg(self.fg).bg(self.bg) }
    pub fn muted(&self)     -> Style { Style::new().fg(self.fg_muted).bg(self.bg) }
    pub fn surface(&self)   -> Style { Style::new().fg(self.fg).bg(self.surface) }
    pub fn accent(&self)    -> Style { Style::new().fg(self.accent_fg).bg(self.accent) }
    pub fn success(&self)   -> Style { Style::new().fg(self.success) }
    pub fn error(&self)     -> Style { Style::new().fg(self.error) }
    pub fn warning(&self)   -> Style { Style::new().fg(self.warning) }
    pub fn border(&self)    -> Style { Style::new().fg(self.border) }
    pub fn border_hi(&self) -> Style { Style::new().fg(self.border_hi) }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn light_theme_is_named_lcd_green() {
        assert_eq!(Theme::light().name, "LCD Green");
    }

    #[test]
    fn dark_theme_is_named_phosphor_crt() {
        assert_eq!(Theme::dark().name, "Phosphor CRT");
    }

    #[test]
    fn both_themes_use_double_line_borders() {
        assert_eq!(Theme::light().border_type, BorderType::Double);
        assert_eq!(Theme::dark().border_type, BorderType::Double);
    }
}
```

- [ ] **Step 2: Run the new tests**

Run: `cd StudioTUI && cargo test`
Expected: `test theme::tests::light_theme_is_named_lcd_green ... ok`,
`test theme::tests::dark_theme_is_named_phosphor_crt ... ok`,
`test theme::tests::both_themes_use_double_line_borders ... ok` (3 passed).

- [ ] **Step 3: Confirm the workspace still builds**

Run: `cargo build 2>&1 | tail -30`
Expected: compiles — but note `app.rs`'s `toggle_theme` still checks the OLD
literal `"Atom One Light"`, so it will build fine (string comparison, not a
type error) but the theme toggle is now silently broken until Task 2 lands.
Do not skip Task 2.

- [ ] **Step 4: Commit**

```bash
git add StudioTUI/src/theme.rs
git commit -m "$(cat <<'EOF'
StudioTUI: replace Atom One Light/Dark with retro-terminal palette

LCD Green (light) and Phosphor CRT (dark) per
docs/superpowers/specs/2026-07-10-tui-retro-theme-design.md. Adds a
border_type field (BorderType::Double for both themes) that later tasks
wire into the main panel borders. No ui/*.rs or app.rs changes yet — the
theme toggle's name comparison still points at the old "Atom One Light"
literal until the next commit.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Fix theme-toggle name comparison (`app.rs`)

**Files:**
- Modify: `StudioTUI/src/app.rs` (the `toggle_theme` method, currently ~10
  lines above the "Key routing" section — search for `fn toggle_theme`)

**Interfaces:**
- Consumes: `Theme::light().name == "LCD Green"` (from Task 1).
- Produces: nothing new — `toggle_theme` keeps its exact signature
  (`fn toggle_theme(&mut self)`), just fixes which name it compares against.

This is the exact bug class already hit once in this project this session
(the `worker::run_script` staleness) — a rename on one side without
updating the comparison on the other. Verified manually via tmux since
`toggle_theme` is a private `&mut self` method on `App`, and constructing a
real `App` in a unit test spawns filesystem scans + a `catalog.py`
subprocess — too heavy for a unit test here; tmux exercises the real thing
end-to-end instead.

- [ ] **Step 1: Find and fix the stale literal**

Current code:
```rust
    fn toggle_theme(&mut self) {
        self.theme = if self.theme.name == "Atom One Light" { Theme::dark() } else { Theme::light() };
        self.log(format!("Theme → {}", self.theme.name), LogLevel::Info);
    }
```

New code:
```rust
    fn toggle_theme(&mut self) {
        self.theme = if self.theme.name == "LCD Green" { Theme::dark() } else { Theme::light() };
        self.log(format!("Theme → {}", self.theme.name), LogLevel::Info);
    }
```

- [ ] **Step 2: Build**

Run: `cargo build 2>&1 | tail -30`
Expected: compiles clean (no new warnings/errors vs. Task 1's baseline).

- [ ] **Step 3: tmux-verify the toggle actually alternates**

```bash
cd StudioTUI
tmux kill-session -t s 2>/dev/null
tmux new -d -s s -x100 -y30 './target/debug/studio-tui'
sleep 1
tmux send-keys -t s '0' ''; sleep 0.3
tmux capture-pane -t s -p | head -2
tmux send-keys -t s '0' ''; sleep 0.3
tmux capture-pane -t s -p | head -2
tmux send-keys -t s 'q' ''
tmux kill-session -t s
```
Expected: first capture's header shows `Phosphor CRT`, second capture's
header shows `LCD Green` — i.e. it actually alternates both directions, not
stuck on one theme after the first press (that stuck-on-one-side failure
mode is exactly what the stale-literal bug would produce, since `Theme::
dark().name` never equals the light-side check, so pressing `0` from dark
mode would always re-select dark).

- [ ] **Step 4: Commit**

```bash
git add StudioTUI/src/app.rs
git commit -m "$(cat <<'EOF'
StudioTUI: fix theme-toggle name comparison after LCD Green rename

toggle_theme compared against the old "Atom One Light" literal, which no
longer matches Theme::light().name ("LCD Green" as of the prior commit) —
pressing 0 from dark mode would always re-select dark instead of
alternating. tmux-verified 0 now flips both directions.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Header wordmark, blink indicators, help-overlay border (`ui/mod.rs`)

**Files:**
- Modify: `StudioTUI/src/ui/mod.rs` (`render_header` and
  `render_help_overlay` functions)

**Interfaces:**
- Consumes: `t.border_type` (Task 1), `t.name` (Task 1/2), `app.worker_rx`,
  `app.watch_on`, `app.job_queue` (all pre-existing `App` fields, unchanged).
- Produces: nothing consumed by later tasks — `ui/mod.rs` doesn't export
  anything Tasks 4-7 depend on.

- [ ] **Step 1: Replace `render_header`**

Current code (lines 83-108):
```rust
fn render_header(app: &App, t: &crate::theme::Theme, area: Rect, buf: &mut Buffer) {
    let seq_info = if app.seq_playing {
        format!(" ▶ {}bpm", app.seq_bpm)
    } else {
        String::new()
    };
    let worker_info = if app.worker_rx.is_some() { "  ⏳ running…" } else { "" };
    let queue_info = if !app.job_queue.is_empty() {
        format!("  ⧗ {} queued", app.job_queue.len())
    } else {
        String::new()
    };
    let watch_info = if app.watch_on { "  ◉ watch" } else { "" };

    let line = Line::from(vec![
        Span::styled(" ♪ Music Studio ", Style::new().fg(t.accent_fg).bg(t.accent).add_modifier(Modifier::BOLD)),
        Span::styled(format!("  {}  ", t.name), Style::new().fg(t.fg_muted).bg(t.surface_dark)),
        Span::styled(&seq_info,    Style::new().fg(t.success).bg(t.surface_dark).add_modifier(Modifier::BOLD)),
        Span::styled(worker_info,  Style::new().fg(t.warning).bg(t.surface_dark)),
        Span::styled(queue_info,   Style::new().fg(t.warning).bg(t.surface_dark)),
        Span::styled(watch_info,   Style::new().fg(t.success).bg(t.surface_dark).add_modifier(Modifier::BOLD)),
    ]);
    Paragraph::new(line)
        .style(Style::new().bg(t.surface_dark))
        .render(area, buf);
}
```

New code:
```rust
fn render_header(app: &App, t: &crate::theme::Theme, area: Rect, buf: &mut Buffer) {
    let seq_info = if app.seq_playing {
        format!(" ▶ {}bpm", app.seq_bpm)
    } else {
        String::new()
    };
    let worker_info = if app.worker_rx.is_some() { "  ⏳ running…" } else { "" };
    let worker_style = if app.worker_rx.is_some() {
        Style::new().fg(t.warning).bg(t.surface_dark).add_modifier(Modifier::SLOW_BLINK)
    } else {
        Style::new().fg(t.warning).bg(t.surface_dark)
    };
    let queue_info = if !app.job_queue.is_empty() {
        format!("  ⧗ {} queued", app.job_queue.len())
    } else {
        String::new()
    };
    let watch_info = if app.watch_on { "  ◉ watch" } else { "" };
    let watch_style = if app.watch_on {
        Style::new().fg(t.success).bg(t.surface_dark).add_modifier(Modifier::BOLD | Modifier::SLOW_BLINK)
    } else {
        Style::new().fg(t.success).bg(t.surface_dark).add_modifier(Modifier::BOLD)
    };

    let line = Line::from(vec![
        Span::styled(" ▓▓ M U S I C   S T U D I O ▓▓ ", Style::new().fg(t.accent_fg).bg(t.accent).add_modifier(Modifier::BOLD)),
        Span::styled(format!("  {}  ", t.name), Style::new().fg(t.fg_muted).bg(t.surface_dark)),
        Span::styled(&seq_info,    Style::new().fg(t.success).bg(t.surface_dark).add_modifier(Modifier::BOLD)),
        Span::styled(worker_info,  worker_style),
        Span::styled(queue_info,   Style::new().fg(t.warning).bg(t.surface_dark)),
        Span::styled(watch_info,   watch_style),
    ]);
    Paragraph::new(line)
        .style(Style::new().bg(t.surface_dark))
        .render(area, buf);
}
```

- [ ] **Step 2: Add double-line border to the help overlay**

Current code (inside `render_help_overlay`, lines 128-132):
```rust
    let block = Block::new()
        .title(Span::styled(" HELP — ? or Esc to close ", Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
        .borders(Borders::ALL)
        .border_style(t.border_hi())
        .style(Style::new().bg(t.bg));
```

New code:
```rust
    let block = Block::new()
        .title(Span::styled(" HELP — ? or Esc to close ", Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
        .borders(Borders::ALL)
        .border_type(t.border_type)
        .border_style(t.border_hi())
        .style(Style::new().bg(t.bg));
```

- [ ] **Step 3: Build**

Run: `cd StudioTUI && cargo build 2>&1 | tail -30`
Expected: compiles clean.

- [ ] **Step 4: tmux-verify the header and help overlay**

```bash
tmux kill-session -t s 2>/dev/null
tmux new -d -s s -x140 -y30 './target/debug/studio-tui'
sleep 1
tmux capture-pane -t s -p | head -2
tmux send-keys -t s '?' ''; sleep 0.3
tmux capture-pane -t s -p | sed -n '1,4p'
tmux send-keys -t s 'Escape' ''; sleep 0.2
tmux send-keys -t s 'q' ''
tmux kill-session -t s
```
Expected: header row 1 shows the `▓▓ M U S I C   S T U D I O ▓▓` wordmark
(no double-width-glyph column drift — it's all single-cell block/space/caps
characters); help overlay's border renders with double-line box characters
(`═`/`║`/`╔` etc., not `─`/`│`/`┌`).

- [ ] **Step 5: Trigger blink and confirm it's visible**

```bash
tmux kill-session -t s 2>/dev/null
tmux new -d -s s -x140 -y30 './target/debug/studio-tui'
sleep 1
tmux send-keys -t s 'j' ''; tmux send-keys -t s 'Enter' ''; sleep 0.3
tmux capture-pane -t s -p | head -2
sleep 1.5
tmux capture-pane -t s -p | head -2
tmux send-keys -t s 'q' ''
tmux kill-session -t s
```
(This runs "Analyze BPM+Key" via the job queue, same as the live pass-3
verification.) Expected: while the job is running, both captures show
`⏳ running…` in the header (blink attribute doesn't show as plain text in
`capture-pane -p`, since that flattens styling — confirm blink visually by
running the app directly in a real terminal if you want to see the flicker;
the automated check here only confirms the indicator text and job lifecycle
are still correct after the styling change).

- [ ] **Step 6: Commit**

```bash
git add StudioTUI/src/ui/mod.rs
git commit -m "$(cat <<'EOF'
StudioTUI: retro header wordmark, blink on pending indicators, double borders

Header's plain "Music Studio" text becomes a block-flanked spaced-caps
wordmark; the running-job and watch-mode header indicators blink
(Modifier::SLOW_BLINK) while active — a narrow "something's pending"
semantic, not applied to anything that redraws every frame. Help overlay
picks up the new double-line border type.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Pipeline panel borders (`ui/pipeline.rs`)

**Files:**
- Modify: `StudioTUI/src/ui/pipeline.rs` (`render_params`, `render_actions`,
  `ConsoleLog::render` — the PARAMETERS, ACTIONS, and CONSOLE panel blocks)

**Interfaces:**
- Consumes: `t.border_type` (Task 1).
- Produces: nothing consumed elsewhere.

Three separate `Block::new()...borders(Borders::ALL)` call sites get
`.border_type(t.border_type)` added. The param-cell dividers
(`render_param_cell`, `Borders::LEFT`) and the actions-column divider
(inside `render_actions`, also `Borders::LEFT`) are internal dividers, not
main panels — per the spec, those stay on the default thin border and are
NOT touched by this task.

- [ ] **Step 1: PARAMETERS panel — add border_type**

Current code (inside `render_params`):
```rust
    let block = Block::new()
        .title(Span::styled(" PARAMETERS ", Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
        .borders(Borders::ALL)
        .border_style(t.border())
        .style(Style::new().bg(t.surface));
```

New code:
```rust
    let block = Block::new()
        .title(Span::styled(" PARAMETERS ", Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
        .borders(Borders::ALL)
        .border_type(t.border_type)
        .border_style(t.border())
        .style(Style::new().bg(t.surface));
```

- [ ] **Step 2: ACTIONS panel — add border_type**

Current code (inside `render_actions`):
```rust
    let block = Block::new()
        .title(Line::from(title_spans))
        .borders(Borders::ALL)
        .border_style(t.border())
        .style(Style::new().bg(t.surface));
```

New code:
```rust
    let block = Block::new()
        .title(Line::from(title_spans))
        .borders(Borders::ALL)
        .border_type(t.border_type)
        .border_style(t.border())
        .style(Style::new().bg(t.surface));
```

- [ ] **Step 3: CONSOLE panel — add border_type**

Current code (inside `ConsoleLog::render`):
```rust
        let block = Block::new()
            .title(Span::styled(title_str, Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
            .borders(Borders::ALL)
            .border_style(if self.app.worker_rx.is_some() { t.border_hi() } else { t.border() })
            .style(Style::new().bg(t.surface));
```

New code:
```rust
        let block = Block::new()
            .title(Span::styled(title_str, Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
            .borders(Borders::ALL)
            .border_type(t.border_type)
            .border_style(if self.app.worker_rx.is_some() { t.border_hi() } else { t.border() })
            .style(Style::new().bg(t.surface));
```

- [ ] **Step 4: Build**

Run: `cd StudioTUI && cargo build 2>&1 | tail -30`
Expected: compiles clean.

- [ ] **Step 5: tmux-verify Pipeline tab**

```bash
tmux kill-session -t s 2>/dev/null
tmux new -d -s s -x140 -y30 './target/debug/studio-tui'
sleep 1
tmux capture-pane -t s -p | sed -n '3,20p'
tmux send-keys -t s 'q' ''
tmux kill-session -t s
```
Expected: PARAMETERS, ACTIONS, and CONSOLE panel borders render with
double-line box characters; the STEM MODE/DENSITY/CHOP/TEMPO cell dividers
inside PARAMETERS and the two-column divider inside ACTIONS remain
thin/plain (`│`, not `║`).

- [ ] **Step 6: Commit**

```bash
git add StudioTUI/src/ui/pipeline.rs
git commit -m "$(cat <<'EOF'
StudioTUI: double-line borders on Pipeline's main panels

PARAMETERS/ACTIONS/CONSOLE get t.border_type (Double); internal dividers
(param-cell separators, the ACTIONS two-column divider) stay thin so the
dense param grid doesn't get visually heavy.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Sequencer grid panel border (`ui/sequencer.rs`)

**Files:**
- Modify: `StudioTUI/src/ui/sequencer.rs` (`render_seq_grid`)

**Interfaces:**
- Consumes: `t.border_type` (Task 1).
- Produces: nothing consumed elsewhere.

Only the outer STEP SEQUENCER grid panel changes. The BPM/BARS/KIT/NAME
control-field boxes (`render_ctrl_field`) and the Play/Stop button box
(inline in `render_seq_controls`) are controls, not main panels — left
untouched per the spec.

- [ ] **Step 1: STEP SEQUENCER panel — add border_type**

Current code (inside `render_seq_grid`):
```rust
    let block = Block::new()
        .title(Span::styled(
            " ◉ STEP SEQUENCER  16-step · 4/4 ",
            Style::new().fg(t.accent).add_modifier(Modifier::BOLD),
        ))
        .borders(Borders::ALL)
        .border_style(t.border())
        .style(Style::new().bg(t.bg));
```

New code:
```rust
    let block = Block::new()
        .title(Span::styled(
            " ◉ STEP SEQUENCER  16-step · 4/4 ",
            Style::new().fg(t.accent).add_modifier(Modifier::BOLD),
        ))
        .borders(Borders::ALL)
        .border_type(t.border_type)
        .border_style(t.border())
        .style(Style::new().bg(t.bg));
```

- [ ] **Step 2: Build**

Run: `cd StudioTUI && cargo build 2>&1 | tail -30`
Expected: compiles clean.

- [ ] **Step 3: tmux-verify Sequencer tab**

```bash
tmux kill-session -t s 2>/dev/null
tmux new -d -s s -x140 -y30 './target/debug/studio-tui'
sleep 1
tmux send-keys -t s '2' ''; sleep 0.3
tmux capture-pane -t s -p | sed -n '3,14p'
tmux send-keys -t s 'q' ''
tmux kill-session -t s
```
Expected: the STEP SEQUENCER grid's outer border is double-line; the BPM/
BARS/KIT/NAME/Play boxes below it and the beat-group `│` dividers inside the
grid remain thin/plain.

- [ ] **Step 4: Commit**

```bash
git add StudioTUI/src/ui/sequencer.rs
git commit -m "$(cat <<'EOF'
StudioTUI: double-line border on the Sequencer grid panel

STEP SEQUENCER's outer block gets t.border_type; the BPM/BARS/KIT/NAME/Play
control boxes and the grid's internal beat-group dividers stay thin.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Logic STATUS panel border + status-dot blink (`ui/logic.rs`)

**Files:**
- Modify: `StudioTUI/src/ui/logic.rs` (`render_status`)

**Interfaces:**
- Consumes: `t.border_type` (Task 1), `app.logic_status_pending`
  (pre-existing `App` field, unchanged).
- Produces: nothing consumed elsewhere.

Only the STATUS panel changes. The TRANSPORT/TRACKS/PROJECT button boxes
(`render_button_row`) are controls, not main panels — left untouched.

- [ ] **Step 1: STATUS panel — add border_type, and blink the status dot while pending**

Current code (`render_status`, full function):
```rust
fn render_status(app: &App, t: &Theme, area: Rect, buf: &mut Buffer) {
    let (status_str, status_style) = if app.logic_ok {
        ("● online",  t.success().add_modifier(Modifier::BOLD))
    } else {
        ("○ offline", t.error().add_modifier(Modifier::BOLD))
    };

    let line = Line::from(vec![
        Span::styled("Logic Pro  ", Style::new().fg(t.fg).add_modifier(Modifier::BOLD)),
        Span::styled(status_str, status_style),
        Span::styled("   project: ", Style::new().fg(t.fg_muted)),
        Span::styled(&app.logic_project, Style::new().fg(t.fg)),
        Span::styled("   tempo: ",  Style::new().fg(t.fg_muted)),
        Span::styled(&app.logic_tempo, Style::new().fg(t.fg)),
        Span::styled("   key: ",    Style::new().fg(t.fg_muted)),
        Span::styled(&app.logic_key, Style::new().fg(t.fg)),
        Span::styled("   bar: ",    Style::new().fg(t.fg_muted)),
        Span::styled(&app.logic_bar, Style::new().fg(t.fg)),
    ]);

    let block = Block::new()
        .title(Span::styled(" STATUS ", Style::new().fg(t.accent)))
        .borders(Borders::ALL)
        .border_style(if app.logic_ok { t.success() } else { t.border() })
        .style(Style::new().bg(t.surface));
    let inner = block.inner(area);
    block.render(area, buf);
    Paragraph::new(vec![line]).render(inner, buf);
}
```

New code:
```rust
fn render_status(app: &App, t: &Theme, area: Rect, buf: &mut Buffer) {
    let (status_str, mut status_style) = if app.logic_ok {
        ("● online",  t.success().add_modifier(Modifier::BOLD))
    } else {
        ("○ offline", t.error().add_modifier(Modifier::BOLD))
    };
    if app.logic_status_pending {
        status_style = status_style.add_modifier(Modifier::SLOW_BLINK);
    }

    let line = Line::from(vec![
        Span::styled("Logic Pro  ", Style::new().fg(t.fg).add_modifier(Modifier::BOLD)),
        Span::styled(status_str, status_style),
        Span::styled("   project: ", Style::new().fg(t.fg_muted)),
        Span::styled(&app.logic_project, Style::new().fg(t.fg)),
        Span::styled("   tempo: ",  Style::new().fg(t.fg_muted)),
        Span::styled(&app.logic_tempo, Style::new().fg(t.fg)),
        Span::styled("   key: ",    Style::new().fg(t.fg_muted)),
        Span::styled(&app.logic_key, Style::new().fg(t.fg)),
        Span::styled("   bar: ",    Style::new().fg(t.fg_muted)),
        Span::styled(&app.logic_bar, Style::new().fg(t.fg)),
    ]);

    let block = Block::new()
        .title(Span::styled(" STATUS ", Style::new().fg(t.accent)))
        .borders(Borders::ALL)
        .border_type(t.border_type)
        .border_style(if app.logic_ok { t.success() } else { t.border() })
        .style(Style::new().bg(t.surface));
    let inner = block.inner(area);
    block.render(area, buf);
    Paragraph::new(vec![line]).render(inner, buf);
}
```

- [ ] **Step 2: Build**

Run: `cd StudioTUI && cargo build 2>&1 | tail -30`
Expected: compiles clean.

- [ ] **Step 3: tmux-verify Logic tab, including the pending blink trigger**

```bash
tmux kill-session -t s 2>/dev/null
tmux new -d -s s -x140 -y30 './target/debug/studio-tui'
sleep 1
tmux send-keys -t s '3' ''; sleep 0.3
tmux capture-pane -t s -p | sed -n '3,6p'
tmux send-keys -t s 's' ''; sleep 0.1
tmux capture-pane -t s -p | sed -n '3,6p'
sleep 1
tmux send-keys -t s 'q' ''
tmux kill-session -t s
```
Expected: STATUS panel's border is double-line; pressing `s` (status check,
`logic_status_pending = true` until the logic-pro-mcp subprocess responds or
fails fast) shows `○ offline` — Logic Pro likely isn't running in this
environment, which is fine; the check here is that the panel still renders
correctly and doesn't crash/hang with the new blink styling, not that Logic
actually connects.

- [ ] **Step 4: Commit**

```bash
git add StudioTUI/src/ui/logic.rs
git commit -m "$(cat <<'EOF'
StudioTUI: double-line STATUS border, blink status dot while pending

STATUS panel gets t.border_type; the online/offline dot blinks
(Modifier::SLOW_BLINK) while a status check is in flight
(logic_status_pending). TRANSPORT/TRACKS/PROJECT button boxes are
controls, not main panels, and stay on the thin border.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Library panel borders (`ui/library.rs`)

**Files:**
- Modify: `StudioTUI/src/ui/library.rs` (`render_categories`, `render_files`)

**Interfaces:**
- Consumes: `t.border_type` (Task 1).
- Produces: nothing consumed elsewhere.

- [ ] **Step 1: CATEGORIES panel — add border_type**

Current code (inside `render_categories`):
```rust
    let block = Block::new()
        .title(Span::styled(" CATEGORIES ", Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
        .borders(Borders::ALL)
        .border_style(t.border())
        .style(Style::new().bg(t.surface));
```

New code:
```rust
    let block = Block::new()
        .title(Span::styled(" CATEGORIES ", Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
        .borders(Borders::ALL)
        .border_type(t.border_type)
        .border_style(t.border())
        .style(Style::new().bg(t.surface));
```

- [ ] **Step 2: File list panel — add border_type**

Current code (inside `render_files`, the `let mut block = Block::new()...`):
```rust
    let mut block = Block::new()
        .title(Span::styled(
            format!(" {cat_label} · {count} file(s) "),
            Style::new().fg(t.accent).add_modifier(Modifier::BOLD),
        ))
        .borders(Borders::ALL)
        .border_style(t.border_hi())
        .style(Style::new().bg(t.bg));
```

New code:
```rust
    let mut block = Block::new()
        .title(Span::styled(
            format!(" {cat_label} · {count} file(s) "),
            Style::new().fg(t.accent).add_modifier(Modifier::BOLD),
        ))
        .borders(Borders::ALL)
        .border_type(t.border_type)
        .border_style(t.border_hi())
        .style(Style::new().bg(t.bg));
```

- [ ] **Step 3: Build**

Run: `cd StudioTUI && cargo build 2>&1 | tail -30`
Expected: compiles clean.

- [ ] **Step 4: tmux-verify Library tab**

```bash
tmux kill-session -t s 2>/dev/null
tmux new -d -s s -x140 -y30 './target/debug/studio-tui'
sleep 1
tmux send-keys -t s '4' ''; sleep 0.3
tmux capture-pane -t s -p | sed -n '3,15p'
tmux send-keys -t s 'q' ''
tmux kill-session -t s
```
Expected: both CATEGORIES and the file-list panel render double-line
borders.

- [ ] **Step 5: Commit**

```bash
git add StudioTUI/src/ui/library.rs
git commit -m "$(cat <<'EOF'
StudioTUI: double-line borders on Library's CATEGORIES and file-list panels

Both are outer container panels per the spec's border scope; no internal
dividers exist in this tab to leave thin.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Full-workspace verification (both themes, all tabs)

**Files:** none — verification only, no code changes expected. If this task
surfaces a real bug, fix it in the relevant file from Tasks 1-7 and amend
that understanding into a small follow-up commit (do not silently patch and
skip re-verifying).

**Interfaces:** N/A.

This repeats, in one pass, the exact verification the approved spec's
"Testing / verification" section calls for: both themes, all 4 tabs, the
help overlay, and all three blink triggers.

- [ ] **Step 1: Build one final time**

Run: `cd StudioTUI && cargo build 2>&1 | tail -30`
Expected: clean build, same warning count as the pre-existing baseline (3
warnings — `seq_pad_off` unread, and `normal`/`muted`/`surface`/`accent`/
`warning` style-ctor methods unused — per `STATUS.md`; this task must not
introduce new ones).

- [ ] **Step 2: tmux-capture all 4 tabs in LCD Green (light, default)**

```bash
tmux kill-session -t s 2>/dev/null
tmux new -d -s s -x140 -y46 './target/debug/studio-tui'
sleep 1
for tab in 1 2 3 4; do
  tmux send-keys -t s "$tab" ''; sleep 0.3
  echo "=== tab $tab (LCD Green) ==="
  tmux capture-pane -t s -p
done
```
Expected: every panel border listed in Tasks 4-7 is double-line, every
control box stays thin, the header wordmark and theme name (`LCD Green`)
render correctly, no column drift or garbled cells anywhere.

- [ ] **Step 3: Toggle to Phosphor CRT, repeat**

```bash
tmux send-keys -t s '0' ''; sleep 0.3
for tab in 1 2 3 4; do
  tmux send-keys -t s "$tab" ''; sleep 0.3
  echo "=== tab $tab (Phosphor CRT) ==="
  tmux capture-pane -t s -p
done
```
Expected: header now reads `Phosphor CRT`; same border/layout correctness
as Step 2, just repainted.

- [ ] **Step 4: Help overlay in both themes**

```bash
tmux send-keys -t s '?' ''; sleep 0.3
tmux capture-pane -t s -p | sed -n '1,20p'
tmux send-keys -t s 'Escape' ''; sleep 0.2
tmux send-keys -t s '0' ''; sleep 0.3
tmux send-keys -t s '?' ''; sleep 0.3
tmux capture-pane -t s -p | sed -n '1,20p'
tmux send-keys -t s 'Escape' ''; sleep 0.2
```
Expected: overlay renders with a double-line border and both keymap columns
in both themes.

- [ ] **Step 5: Trigger all three blink conditions in one pass**

```bash
tmux send-keys -t s '1' ''; sleep 0.2
tmux send-keys -t s 'j' ''; tmux send-keys -t s 'Enter' ''; sleep 0.3
tmux capture-pane -t s -p | head -2
tmux send-keys -t s 'W' ''; sleep 0.3
tmux capture-pane -t s -p | head -2
tmux send-keys -t s '3' ''; sleep 0.2
tmux send-keys -t s 's' ''; sleep 0.1
tmux capture-pane -t s -p | sed -n '3,4p'
sleep 2
tmux send-keys -t s '1' ''; sleep 0.2
tmux send-keys -t s 'W' ''; sleep 0.2
tmux send-keys -t s 'q' ''
tmux kill-session -t s
```
Expected: `⏳ running…` appears in the header during the Analyze job,
`◉ watch` appears after `W`, and the Logic STATUS dot renders without error
right after `s` — none of these hang or crash the app, and turning watch
mode back off before quitting leaves no dangling state.

- [ ] **Step 6: Final status check — nothing left uncommitted**

Run: `git status --short StudioTUI/`
Expected: empty output (everything from Tasks 1-7 was already committed;
this task made no code changes unless Step 1-5 surfaced a bug).
