pub mod pipeline;
pub mod sequencer;
pub mod library;
pub mod logic;

use ratatui::{
    buffer::Buffer,
    layout::{Constraint, Layout, Rect},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Clear, Paragraph, Tabs, Widget},
    Frame,
};

use crate::app::{App, ActiveTab, TABS};

/// Root draw function — called once per frame. Dispatches to tab widgets.
/// Follows ratatui skill §1: no &mut Frame passed into sub-renders.
pub fn draw(frame: &mut Frame, app: &mut App) {
    let area = frame.area();
    frame.render_widget(RootView { app }, area);
}

struct RootView<'a> {
    app: &'a App,
}

impl<'a> Widget for RootView<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        let t = &self.app.theme;
        let app = self.app;

        // Layout: header(1) | tab_bar(2) | body(fill) | console(8)
        let [hdr_area, tab_bar_area, body_area, console_area] = Layout::vertical([
            Constraint::Length(1),
            Constraint::Length(2),
            Constraint::Fill(1),
            Constraint::Length(8),
        ]).areas(area);

        // ── Header ────────────────────────────────────────────────────────
        render_header(app, t, hdr_area, buf);

        // ── Tab bar ───────────────────────────────────────────────────────
        let tab_titles: Vec<Span> = TABS.iter().map(|(label, tab)| {
            let active = app.tab == *tab;
            Span::styled(*label, if active {
                Style::new().fg(t.accent_fg).bg(t.accent).add_modifier(Modifier::BOLD)
            } else {
                Style::new().fg(t.fg_muted).bg(t.surface)
            })
        }).collect();

        let selected = TABS.iter().position(|(_, t)| *t == app.tab).unwrap_or(0);
        Tabs::new(tab_titles)
            .select(selected)
            .divider("  ")
            .style(Style::new().bg(t.surface))
            .render(tab_bar_area, buf);

        // ── Active tab body ───────────────────────────────────────────────
        Block::new()
            .style(Style::new().bg(t.bg))
            .render(body_area, buf);

        match app.tab {
            ActiveTab::Pipeline  => pipeline::PipelineTab  { app }.render(body_area, buf),
            ActiveTab::Sequencer => sequencer::SequencerTab { app }.render(body_area, buf),
            ActiveTab::Logic     => logic::LogicTab         { app }.render(body_area, buf),
            ActiveTab::Library   => library::LibraryTab     { app }.render(body_area, buf),
        }

        // ── Console ───────────────────────────────────────────────────────
        pipeline::ConsoleLog { app }.render(console_area, buf);

        // ── Help overlay ─────────────────────────────────────────────────
        if app.help_open {
            render_help_overlay(app, t, area, buf);
        }
    }
}

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

/// Centered popup rect, `pct_x`/`pct_y` percent of `area`.
fn centered_rect(pct_x: u16, pct_y: u16, area: Rect) -> Rect {
    let v = Layout::vertical([
        Constraint::Percentage((100 - pct_y) / 2),
        Constraint::Percentage(pct_y),
        Constraint::Percentage((100 - pct_y) / 2),
    ]).split(area);
    Layout::horizontal([
        Constraint::Percentage((100 - pct_x) / 2),
        Constraint::Percentage(pct_x),
        Constraint::Percentage((100 - pct_x) / 2),
    ]).split(v[1])[1]
}

fn render_help_overlay(app: &App, t: &crate::theme::Theme, area: Rect, buf: &mut Buffer) {
    let popup = centered_rect(70, 70, area);
    Clear.render(popup, buf);

    let block = Block::new()
        .title(Span::styled(" HELP — ? or Esc to close ", Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
        .borders(Borders::ALL)
        .border_style(t.border_hi())
        .style(Style::new().bg(t.bg));
    let inner = block.inner(popup);
    block.render(popup, buf);

    let [left, right] = Layout::horizontal([Constraint::Fill(1), Constraint::Fill(1)]).areas(inner);

    let mut global_lines = vec![Line::from(Span::styled(
        "GLOBAL", Style::new().fg(t.accent).add_modifier(Modifier::BOLD),
    ))];
    for (k, d) in crate::app::global_keymap() {
        global_lines.push(Line::from(vec![
            Span::styled(format!("{k:<14}"), Style::new().fg(t.accent)),
            Span::styled(*d, Style::new().fg(t.fg)),
        ]));
    }
    Paragraph::new(global_lines).style(Style::new().bg(t.bg)).render(left, buf);

    let mut tab_lines = vec![Line::from(Span::styled(
        "THIS TAB", Style::new().fg(t.accent).add_modifier(Modifier::BOLD),
    ))];
    for (k, d) in crate::app::keymap_for(app.tab) {
        tab_lines.push(Line::from(vec![
            Span::styled(format!("{k:<14}"), Style::new().fg(t.accent)),
            Span::styled(*d, Style::new().fg(t.fg)),
        ]));
    }
    Paragraph::new(tab_lines).style(Style::new().bg(t.bg)).render(right, buf);
}
