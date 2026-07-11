use ratatui::{
    buffer::Buffer,
    layout::{Constraint, Layout, Rect},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph, Widget},
};

use crate::app::App;
use crate::theme::Theme;
use crate::ui::pipeline::render_hint;

// ── Logic Pro tab widget ──────────────────────────────────────────────────────

pub struct LogicTab<'a> {
    pub app: &'a App,
}

/// Visual tier for a labelled action button.
#[derive(Clone, Copy)]
enum Btn {
    Primary,   // transport go-actions (accent)
    Danger,    // record (error)
    Secondary, // tracks / project actions (surface)
}

impl<'a> Widget for LogicTab<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        let t = &self.app.theme;
        let app = self.app;

        let [
            status_area,
            transport_title,
            transport_area,
            tracks_title,
            tracks_area,
            project_title,
            project_area,
            info_area,
            hint_area,
        ] = Layout::vertical([
            Constraint::Length(3), // status bar
            Constraint::Length(1), // "TRANSPORT"
            Constraint::Length(3), // transport buttons
            Constraint::Length(1), // "TRACKS"
            Constraint::Length(3), // tracks buttons
            Constraint::Length(1), // "PROJECT"
            Constraint::Length(3), // project buttons
            Constraint::Fill(1),   // info blurb
            Constraint::Length(1), // hint bar
        ])
        .areas(area);

        render_status(app, t, status_area, buf);

        render_section_title(t, transport_title, buf, "TRANSPORT");
        render_button_row(app.logic_ok, t, transport_area, buf, &[
            ("[Space] ▶ Play",  Btn::Primary),
            ("[x] ⏹ Stop",      Btn::Primary),
            ("[[] ⏮ Start",     Btn::Primary),
            ("[,] ⏪ Rwd",       Btn::Primary),
            ("[.] ⏩ Fwd",       Btn::Primary),
            ("[R] ⏺ Rec",       Btn::Danger),
        ]);

        render_section_title(t, tracks_title, buf, "TRACKS");
        render_button_row(app.logic_ok, t, tracks_area, buf, &[
            ("[t] ☰ List",  Btn::Secondary),
            ("[u] ✕ Mute",  Btn::Secondary),
            ("[o] ◉ Solo",  Btn::Secondary),
        ]);

        render_section_title(t, project_title, buf, "PROJECT");
        render_button_row(app.logic_ok, t, project_area, buf, &[
            ("[w] ▤ Save",   Btn::Secondary),
            ("[n] ▦ New",    Btn::Secondary),
            ("[b] ⟳ Bounce", Btn::Secondary),
            ("[e] ⭳ Export", Btn::Secondary),
        ]);

        render_info(t, info_area, buf);
        render_hint(t, hint_area, buf,
            "s status  c connect  ·  Space/x/[/,/. transport  R rec  ·  t/u/o tracks  ·  w/n/b/e project  ·  q quit");
    }
}

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

/// Small bold accent label that heads each button group.
fn render_section_title(t: &Theme, area: Rect, buf: &mut Buffer, title: &str) {
    Paragraph::new(Line::from(Span::styled(
        title,
        Style::new().fg(t.accent).add_modifier(Modifier::BOLD),
    )))
    .render(area, buf);
}

/// Renders a horizontal row of labelled key-hinted buttons. Every button is
/// greyed (fg_muted on surface_dark) while Logic is offline so it's obvious the
/// actions are inert until connected; colour returns once `online`.
fn render_button_row(online: bool, t: &Theme, area: Rect, buf: &mut Buffer, btns: &[(&str, Btn)]) {
    let constraints: Vec<_> = btns.iter().map(|_| Constraint::Fill(1)).collect();
    let cells = Layout::horizontal(constraints).split(area);

    for (i, (label, kind)) in btns.iter().enumerate() {
        let style = if !online {
            Style::new().fg(t.fg_muted).bg(t.surface_dark)
        } else {
            match kind {
                Btn::Primary   => Style::new().fg(t.accent_fg).bg(t.accent),
                Btn::Danger    => Style::new().fg(t.accent_fg).bg(t.error),
                Btn::Secondary => Style::new().fg(t.fg).bg(t.surface),
            }
        };
        let block = Block::new()
            .borders(Borders::ALL)
            .border_style(t.border())
            .style(style);
        let inner = block.inner(cells[i]);
        block.render(cells[i], buf);
        Paragraph::new(*label).style(style).render(inner, buf);
    }
}

fn render_info(t: &Theme, area: Rect, buf: &mut Buffer) {
    let lines = vec![
        Line::from(Span::styled(
            "Needs Logic Pro open + Accessibility/Automation granted.",
            Style::new().fg(t.fg_muted),
        )),
        Line::from(Span::styled(
            "Press s for status, c to connect.",
            Style::new().fg(t.fg_muted),
        )),
        Line::from(Span::styled(
            "UI-scripting is best-effort — some actions may not stick.",
            Style::new().fg(t.fg_muted),
        )),
    ];
    Paragraph::new(lines).style(Style::new().bg(t.bg)).render(area, buf);
}
