use ratatui::{
    buffer::Buffer,
    layout::{Constraint, Layout, Rect},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph, Widget, Wrap},
};

use crate::app::{App, LogLevel, PIPELINE_ACTIONS};
use crate::theme::Theme;

// ── Pipeline tab widget ───────────────────────────────────────────────────────

pub struct PipelineTab<'a> {
    pub app: &'a App,
}

impl<'a> Widget for PipelineTab<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        let t = &self.app.theme;

        // Paint a clean background so leftover space never looks like a dead box.
        Block::new().style(Style::new().bg(t.bg)).render(area, buf);

        // Size the ACTIONS panel to its content (rows per column + borders)
        // instead of stretching it into empty vertical space.
        let rows = (PIPELINE_ACTIONS.len() + 1) / 2;
        let actions_h = (rows as u16) + 2;

        let [params_area, actions_area, _gap, hint_area] = Layout::vertical([
            Constraint::Length(8),
            Constraint::Length(actions_h),
            Constraint::Fill(1),
            Constraint::Length(1),
        ]).areas(area);

        render_params(self.app, t, params_area, buf);
        render_actions(self.app, t, actions_area, buf);
        render_hint(t, hint_area, buf,
            "j/k select · Enter run · u URL · t tempo · [/] stem · s mode · d density · g chop · ←/→ src · a batch · Esc cancel · r refresh · c clear · 1-4 tabs · ? help · q quit");
    }
}

/// Truncate keeping the informative tail (end of a path), prefixing with `…`.
fn truncate_tail(s: &str, max: usize) -> String {
    let n = s.chars().count();
    if n <= max { return s.to_string(); }
    if max <= 1 { return "…".to_string(); }
    let tail: String = s.chars().skip(n - (max - 1)).collect();
    format!("…{tail}")
}

fn render_params(app: &App, t: &Theme, area: Rect, buf: &mut Buffer) {
    let block = Block::new()
        .title(Span::styled(" PARAMETERS ", Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
        .borders(Borders::ALL)
        .border_style(t.border())
        .style(Style::new().bg(t.surface));
    let inner = block.inner(area);
    block.render(area, buf);

    let [row_source, row_stem, row_url, row_params] = Layout::vertical([
        Constraint::Length(1),
        Constraint::Length(1),
        Constraint::Length(1),
        Constraint::Length(3),
    ]).areas(inner);

    const LBL_W: u16 = 14;

    // SOURCE TRACK
    {
        let [lbl, val] = Layout::horizontal([Constraint::Length(LBL_W), Constraint::Fill(1)]).areas(row_source);
        Paragraph::new("SOURCE TRACK").style(Style::new().fg(t.fg_muted)).render(lbl, buf);
        let source = app.source_tracks.get(app.source_idx).map(String::as_str).unwrap_or("—");
        Paragraph::new(truncate_tail(source, val.width as usize))
            .style(Style::new().fg(t.fg).add_modifier(Modifier::BOLD))
            .render(val, buf);
    }

    // STEM FOLDER
    {
        let [lbl, val] = Layout::horizontal([Constraint::Length(LBL_W), Constraint::Fill(1)]).areas(row_stem);
        Paragraph::new("STEM FOLDER").style(Style::new().fg(t.fg_muted)).render(lbl, buf);
        let stem = app.stem_folders.get(app.stems_idx).map(String::as_str).unwrap_or("—");
        Paragraph::new(truncate_tail(stem, val.width as usize))
            .style(Style::new().fg(t.fg).add_modifier(Modifier::BOLD))
            .render(val, buf);
    }

    // DOWNLOAD URL
    {
        let url_focused = matches!(app.focus, crate::app::Focus::PipelineUrl);
        let [lbl, val] = Layout::horizontal([Constraint::Length(LBL_W), Constraint::Fill(1)]).areas(row_url);
        Paragraph::new("DOWNLOAD URL").style(Style::new().fg(t.fg_muted)).render(lbl, buf);
        let url_text = if app.download_url.is_empty() { "press u to edit…" } else { &app.download_url };
        let url_style = if url_focused {
            Style::new().fg(t.accent).add_modifier(Modifier::UNDERLINED | Modifier::BOLD)
        } else {
            Style::new().fg(if app.download_url.is_empty() { t.fg_muted } else { t.fg })
        };
        Paragraph::new(truncate_tail(url_text, val.width as usize)).style(url_style).render(val, buf);
    }

    // Mini param grid — four chips separated by dividers.
    let [p1, p2, p3, p4] = Layout::horizontal([
        Constraint::Fill(1), Constraint::Fill(1),
        Constraint::Fill(1), Constraint::Fill(1),
    ]).areas(row_params);

    let stem_modes = ["6-stem", "4-stem", "instrumental"];
    let densities  = ["loose", "tight"];
    let chop_ss    = ["8s", "4s", "16s"];

    let tempo_focused = matches!(app.focus, crate::app::Focus::PipelineTempo);

    render_param_cell(t, p1, buf, "STEM MODE", stem_modes[app.stem_mode_idx], false, false);
    render_param_cell(t, p2, buf, "DENSITY",   densities[app.density_idx],    true,  false);
    render_param_cell(t, p3, buf, "CHOP",      chop_ss[app.chop_s_idx],       true,  false);
    render_param_cell(t, p4, buf, "TEMPO",     &app.tempo_str,                true,  tempo_focused);
}

fn render_param_cell(t: &Theme, area: Rect, buf: &mut Buffer, label: &str, value: &str, divider: bool, focused: bool) {
    let value_style = if focused {
        Style::new().fg(t.accent).add_modifier(Modifier::UNDERLINED | Modifier::BOLD)
    } else {
        Style::new().fg(t.accent).add_modifier(Modifier::BOLD)
    };
    let lines = vec![
        Line::from(Span::styled(format!(" {label}"), Style::new().fg(t.fg_muted))),
        Line::from(Span::styled(format!(" {value}"), value_style)),
    ];
    let block = Block::new()
        .borders(if divider { Borders::LEFT } else { Borders::NONE })
        .border_style(t.border())
        .style(Style::new().bg(t.surface));
    let inner = block.inner(area);
    block.render(area, buf);
    Paragraph::new(lines).render(inner, buf);
}

fn action_glyph(label: &str) -> &'static str {
    match label {
        l if l.contains("Download")  => "⭳",
        l if l.contains("Analyze")   => "⚙",
        l if l.contains("Separate")  => "▤",
        l if l.contains("Full")      => "⟳",
        l if l.contains("Chop Drum") => "◈",
        l if l.contains("Sort")      => "▦",
        l if l.contains("Chop Voc")  => "◉",
        l if l.contains("Chop Stem") => "▥",
        l if l.contains("Decon")     => "✦",
        l if l.contains("Bass")      => "♪",
        l if l.contains("Re-voice")  => "♫",
        l if l.contains("Build")     => "⌂",
        _                            => "•",
    }
}

fn render_actions(app: &App, t: &Theme, area: Rect, buf: &mut Buffer) {
    // One panel, one title. Two columns share the frame, split by a divider.
    let mut title_spans = vec![Span::styled(" ACTIONS ", Style::new().fg(t.accent).add_modifier(Modifier::BOLD))];
    if !app.job_queue.is_empty() {
        title_spans.push(Span::styled(
            format!("· ⧗ {} queued ", app.job_queue.len()),
            Style::new().fg(t.warning),
        ));
    }
    let block = Block::new()
        .title(Line::from(title_spans))
        .borders(Borders::ALL)
        .border_style(t.border())
        .style(Style::new().bg(t.surface));
    let inner = block.inner(area);
    block.render(area, buf);

    let [left_area, right_area] = Layout::horizontal([
        Constraint::Fill(1),
        Constraint::Fill(1),
    ]).areas(inner);

    // Vertical divider between the two columns.
    let divider = Block::new()
        .borders(Borders::LEFT)
        .border_style(t.border())
        .style(Style::new().bg(t.surface));
    let right_inner = divider.inner(right_area);
    divider.render(right_area, buf);

    let mid = (PIPELINE_ACTIONS.len() + 1) / 2;
    render_action_col(app, t, left_area,  buf, 0..mid);
    render_action_col(app, t, right_inner, buf, mid..PIPELINE_ACTIONS.len());
}

fn render_action_col(
    app: &App, t: &Theme, area: Rect, buf: &mut Buffer,
    range: std::ops::Range<usize>,
) {
    let items: Vec<ListItem> = range.map(|i| {
        let (label, script) = PIPELINE_ACTIONS[i];
        let no_script = script.is_empty();
        let is_sel = i == app.pipeline_sel;
        let glyph = action_glyph(label);

        let style = if is_sel {
            Style::new().fg(t.accent_fg).bg(t.accent).add_modifier(Modifier::BOLD)
        } else if no_script {
            Style::new().fg(t.fg_muted)
        } else {
            Style::new().fg(t.fg)
        };

        let marker = if is_sel { "▸" } else { " " };
        let suffix = if no_script { " ·" } else { "" };
        ListItem::new(format!("{marker} {glyph}  {label}{suffix}")).style(style)
    }).collect();

    List::new(items).render(area, buf);
}

// ── Console log widget ────────────────────────────────────────────────────────

pub struct ConsoleLog<'a> {
    pub app: &'a App,
}

impl<'a> Widget for ConsoleLog<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        let t = &self.app.theme;
        let h = area.height.saturating_sub(2) as usize;
        let lines: Vec<Line> = self.app.log_lines.iter()
            .rev().take(h).rev()
            .map(|l| {
                let style = match l.level {
                    LogLevel::Ok    => Style::new().fg(t.success),
                    LogLevel::Err   => Style::new().fg(t.error),
                    LogLevel::Info  => Style::new().fg(t.fg_muted),
                    LogLevel::Plain => Style::new().fg(t.fg),
                };
                Line::from(Span::styled(&l.text, style))
            })
            .collect();

        // Worker busy indicator in title
        let title_str = if self.app.worker_rx.is_some() {
            " CONSOLE  ⏳ running… "
        } else {
            " CONSOLE "
        };

        let block = Block::new()
            .title(Span::styled(title_str, Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
            .borders(Borders::ALL)
            .border_style(if self.app.worker_rx.is_some() { t.border_hi() } else { t.border() })
            .style(Style::new().bg(t.surface));

        Paragraph::new(lines).block(block).wrap(Wrap { trim: false }).render(area, buf);
    }
}

// ── Shared helpers ────────────────────────────────────────────────────────────

pub fn render_hint(t: &Theme, area: Rect, buf: &mut Buffer, hint: &str) {
    Paragraph::new(Line::from(vec![
        Span::styled(" ", Style::new().bg(t.surface_dark)),
        Span::styled(hint, Style::new().fg(t.fg_muted).bg(t.surface_dark)),
    ]))
    .style(Style::new().bg(t.surface_dark))
    .render(area, buf);
}
