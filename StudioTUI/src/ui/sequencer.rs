use ratatui::{
    buffer::Buffer,
    layout::{Constraint, Layout, Rect},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph, Widget},
};

use crate::app::{App, Focus, SEQ_INSTS};
use crate::theme::Theme;
use crate::ui::pipeline::render_hint;

// ── Sequencer tab widget ──────────────────────────────────────────────────────

pub struct SequencerTab<'a> {
    pub app: &'a App,
}

impl<'a> Widget for SequencerTab<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        let t = &self.app.theme;
        let app = self.app;

        // Layout: grid block | controls | legend | hint
        let grid_h = SEQ_INSTS.len() as u16 + 4; // header row + 6 inst rows + 2 border
        let [grid_area, controls_area, legend_area, hint_area] = Layout::vertical([
            Constraint::Length(grid_h),
            Constraint::Length(3),
            Constraint::Length(1),
            Constraint::Length(1),
        ]).areas(area);

        render_seq_grid(app, t, grid_area, buf);
        render_seq_controls(app, t, controls_area, buf);
        render_legend(t, legend_area, buf);
        render_hint(t, hint_area, buf,
            "hjkl/arrows move · Space toggle · p play/stop · +/- BPM · n name · b BPM · B bars · K kit · x clear · S save · L load · m MIDI · w WAV · 1-4 tabs · q quit");
    }
}

// Column geometry, shared by header + rows.
const LABEL_W: u16 = 9;
const SEP_W:   u16 = 1;
const STEP_W:  u16 = 4; // 3 chars + 1 gap

/// Background wash for a step column: alternate shading per beat group so the
/// 4/4 grid (steps 1-4 / 5-8 / 9-12 / 13-16) reads at a glance.
fn beat_group_bg(t: &Theme, col: usize) -> ratatui::style::Color {
    if (col / 4) % 2 == 0 { t.bg } else { t.surface }
}

fn render_seq_grid(app: &App, t: &Theme, area: Rect, buf: &mut Buffer) {
    let block = Block::new()
        .title(Span::styled(
            " ◉ STEP SEQUENCER  16-step · 4/4 ",
            Style::new().fg(t.accent).add_modifier(Modifier::BOLD),
        ))
        .borders(Borders::ALL)
        .border_style(t.border())
        .style(Style::new().bg(t.bg));
    let inner = block.inner(area);
    block.render(area, buf);

    // ── Step number header row ────────────────────────────────────────────────
    let hdr_y = inner.y;
    {
        // Label column placeholder ("STEP" caption sitting over the labels).
        let lbl_area = Rect { x: inner.x, y: hdr_y, width: LABEL_W + SEP_W, height: 1 };
        Paragraph::new("  STEP  │")
            .style(Style::new().fg(t.fg_muted).bg(t.surface_dark).add_modifier(Modifier::BOLD))
            .render(lbl_area, buf);

        for col in 0..16usize {
            let px = inner.x + LABEL_W + SEP_W + col as u16 * STEP_W;

            // Beat-group separator every 4 steps (start of a new downbeat).
            if col > 0 && col % 4 == 0 {
                let sep_area = Rect { x: px - 1, y: hdr_y, width: 1, height: 1 };
                Paragraph::new("│")
                    .style(Style::new().fg(t.border_hi).bg(t.bg))
                    .render(sep_area, buf);
            }

            let is_playhead = app.seq_playing && app.seq_step == col;
            let is_downbeat = col % 4 == 0;
            let num_style = if is_playhead {
                Style::new().fg(t.accent_fg).bg(t.success).add_modifier(Modifier::BOLD)
            } else if is_downbeat {
                Style::new().fg(t.accent).bg(beat_group_bg(t, col)).add_modifier(Modifier::BOLD)
            } else {
                Style::new().fg(t.fg_muted).bg(beat_group_bg(t, col))
            };
            let num_area = Rect { x: px, y: hdr_y, width: STEP_W - 1, height: 1 };
            Paragraph::new(format!("{:2} ", col + 1)).style(num_style).render(num_area, buf);
        }
    }

    // ── Instrument rows ───────────────────────────────────────────────────────
    for (row_idx, inst) in SEQ_INSTS.iter().enumerate() {
        let ry = inner.y + 1 + row_idx as u16;

        let is_cursor_row = row_idx == app.seq_cursor.0;
        let (marker, label_style) = if is_cursor_row {
            ("▸", Style::new().fg(t.accent).bg(t.surface_dark).add_modifier(Modifier::BOLD))
        } else {
            (" ", Style::new().fg(t.fg).bg(t.surface))
        };

        // Instrument name label ("▸ Kick   ").
        let label_area = Rect { x: inner.x, y: ry, width: LABEL_W, height: 1 };
        Paragraph::new(format!("{marker}{inst:>7} ")).style(label_style).render(label_area, buf);

        // Label/grid divider.
        let sep_area = Rect { x: inner.x + LABEL_W, y: ry, width: SEP_W, height: 1 };
        Paragraph::new("│").style(Style::new().fg(t.border).bg(t.bg)).render(sep_area, buf);

        // Step pads.
        for col in 0..16usize {
            let px = inner.x + LABEL_W + SEP_W + col as u16 * STEP_W;

            // Beat-group separator.
            if col > 0 && col % 4 == 0 {
                let sep_a = Rect { x: px - 1, y: ry, width: 1, height: 1 };
                Paragraph::new("│")
                    .style(Style::new().fg(t.border_hi).bg(t.bg))
                    .render(sep_a, buf);
            }

            let is_on      = app.seq_matrix[row_idx][col];
            let is_playing = app.seq_playing && app.seq_step == col;
            let is_cursor  = app.seq_cursor == (row_idx, col);

            // Off pads inherit the beat-group wash so downbeats stay readable.
            let off_bg = beat_group_bg(t, col);
            let (text, bg, fg) = match (is_on, is_playing) {
                (true,  true)  => ("▓▓ ", t.seq_hit,      t.accent_fg),
                (true,  false) => ("██ ", t.seq_pad_on,   t.accent_fg),
                (false, true)  => ("░░ ", t.seq_playhead,  t.fg),
                (false, false) => ("·· ", off_bg,          t.fg_muted),
            };

            // Cursor cell wins with a bold accent fill so it's unmistakable.
            let style = if is_cursor {
                Style::new().fg(t.accent_fg).bg(t.accent).add_modifier(Modifier::BOLD | Modifier::REVERSED)
            } else {
                Style::new().fg(fg).bg(bg)
            };

            let pad_area = Rect { x: px, y: ry, width: STEP_W - 1, height: 1 };
            Paragraph::new(text).style(style).render(pad_area, buf);
        }
    }
}

fn render_seq_controls(app: &App, t: &Theme, area: Rect, buf: &mut Buffer) {
    let [play_area, bpm_area, bars_area, kit_area, name_area] = Layout::horizontal([
        Constraint::Length(12),
        Constraint::Length(10),
        Constraint::Length(8),
        Constraint::Length(14),
        Constraint::Fill(1),
    ]).areas(area);

    // Play/Stop button — colour signals current transport state.
    let (play_label, play_bg) = if app.seq_playing {
        ("⏹ Stop", t.error)
    } else {
        ("▶ Play", t.success)
    };
    let play_style = Style::new().fg(t.accent_fg).bg(play_bg).add_modifier(Modifier::BOLD);
    let pb = Block::new()
        .borders(Borders::ALL)
        .border_style(Style::new().fg(play_bg))
        .style(play_style);
    let pi = pb.inner(play_area);
    pb.render(play_area, buf);
    Paragraph::new(play_label).style(play_style).render(pi, buf);

    let bars_label = app.bars_label();
    render_ctrl_field(t, bpm_area,  buf, "BPM",  &app.seq_bpm_str, true,  app.focus == Focus::SeqBpm);
    render_ctrl_field(t, bars_area, buf, "BARS", &bars_label,      false, false);
    render_ctrl_field(t, kit_area,  buf, "KIT",  app.kit_label(),  false, false);
    render_ctrl_field(t, name_area, buf, "NAME", &app.seq_name,    false, app.focus == Focus::SeqName);
}

/// A tidy labeled field: caption in the top border, value inside.
/// `emphasize` tints the value with the accent colour (used for BPM).
/// `focused` overrides the value style with the design system's focused-text-input
/// treatment (UNDERLINED | BOLD in accent) and lifts the border to `border_hi`.
fn render_ctrl_field(t: &Theme, area: Rect, buf: &mut Buffer, label: &str, value: &str, emphasize: bool, focused: bool) {
    let block = Block::new()
        .title(Span::styled(
            format!(" {label} "),
            Style::new().fg(t.fg_muted).add_modifier(Modifier::BOLD),
        ))
        .borders(Borders::ALL)
        .border_style(if focused { t.border_hi() } else { t.border() })
        .style(Style::new().bg(t.surface));
    let inner = block.inner(area);
    block.render(area, buf);
    let value_style = if focused {
        Style::new().fg(t.accent).bg(t.surface).add_modifier(Modifier::BOLD | Modifier::UNDERLINED)
    } else {
        let value_fg = if emphasize { t.accent } else { t.fg };
        Style::new().fg(value_fg).bg(t.surface).add_modifier(Modifier::BOLD)
    };
    Paragraph::new(format!(" {value}")).style(value_style).render(inner, buf);
}

fn render_legend(t: &Theme, area: Rect, buf: &mut Buffer) {
    let parts = Line::from(vec![
        Span::styled("██", Style::new().fg(t.seq_pad_on)),
        Span::styled(" on  ", Style::new().fg(t.fg_muted)),
        Span::styled("▓▓", Style::new().fg(t.seq_hit)),
        Span::styled(" hit  ", Style::new().fg(t.fg_muted)),
        Span::styled("░░", Style::new().fg(t.success)),
        Span::styled(" playhead  ", Style::new().fg(t.fg_muted)),
        Span::styled("··", Style::new().fg(t.fg_muted)),
        Span::styled(" off", Style::new().fg(t.fg_muted)),
        Span::styled("   │   ", Style::new().fg(t.border)),
        Span::styled(
            "GM  kick 36 · snare 38 · hat 42 · openhat 46 · clap 39 · 808 35",
            Style::new().fg(t.fg_muted),
        ),
        Span::styled("   │   ", Style::new().fg(t.border)),
        Span::styled(
            "S/L → Samples/Patterns/<name>.pattern",
            Style::new().fg(t.fg_muted),
        ),
    ]);
    Paragraph::new(vec![parts]).style(Style::new().bg(t.bg)).render(area, buf);
}
