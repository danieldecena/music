use std::path::Path;

use ratatui::{
    layout::{Alignment, Constraint, Layout, Rect},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, List, ListItem, ListState, Paragraph, Wrap},
    Frame,
};

use crate::{
    app::App,
    steps::{self, Step},
    theme::Theme,
};

pub fn draw(f: &mut Frame, app: &App) {
    let t = app.theme;
    f.render_widget(
        Block::default().style(Style::default().bg(t.bg).fg(t.fg)),
        f.area(),
    );

    let root = Layout::vertical([
        Constraint::Length(1), // header
        Constraint::Min(0),    // body
        Constraint::Length(1), // footer
    ])
    .split(f.area());

    draw_header(f, root[0], app);

    let cols = Layout::horizontal([Constraint::Length(34), Constraint::Min(0)]).split(root[1]);
    draw_list(f, cols[0], app);
    if app.input.is_some() {
        draw_input(f, cols[1], app);
    } else {
        draw_detail(f, cols[1], app);
    }

    draw_footer(f, root[2], app);
}

fn draw_header(f: &mut Frame, area: Rect, app: &App) {
    let t = app.theme;
    let cols = Layout::horizontal([Constraint::Min(0), Constraint::Length(10)]).split(area);

    let mut spans = vec![Span::styled(
        " music ",
        Style::default().fg(t.key_fg).bg(t.key).add_modifier(Modifier::BOLD),
    )];
    spans.push(Span::styled(" flip menu ", Style::default().fg(t.muted)));
    if app.filtering || !app.query.is_empty() {
        spans.push(Span::styled("/", Style::default().fg(t.key)));
        spans.push(Span::styled(app.query.clone(), Style::default().fg(t.fg)));
        if app.filtering {
            spans.push(Span::styled(" ", Style::default().bg(t.selection)));
        }
    }
    f.render_widget(Paragraph::new(Line::from(spans)), cols[0]);

    let mode = if t.light { "☀ light" } else { "☾ dark" };
    f.render_widget(
        Paragraph::new(Line::from(Span::styled(mode, Style::default().fg(t.muted))))
            .alignment(Alignment::Right),
        cols[1],
    );
}

fn draw_list(f: &mut Frame, area: Rect, app: &App) {
    let t = app.theme;
    let block = titled(&format!("Steps ({})", app.filtered.len()), app.input.is_none(), t);

    if app.filtered.is_empty() {
        f.render_widget(
            Paragraph::new(Line::styled("  no matching steps", Style::default().fg(t.muted)))
                .block(block),
            area,
        );
        return;
    }

    let mut items: Vec<ListItem> = Vec::new();
    let mut sel_row = 0usize;
    let mut prev_group: Option<String> = None;

    for (pos, &idx) in app.filtered.iter().enumerate() {
        let s = &app.steps[idx];
        let group = if s.favorite {
            "★ Favorites".to_string()
        } else {
            s.category.to_string()
        };
        if prev_group.as_deref() != Some(group.as_str()) {
            items.push(ListItem::new(Line::styled(
                group.clone(),
                Style::default().fg(t.category).add_modifier(Modifier::BOLD),
            )));
            prev_group = Some(group);
        }
        if pos == app.sel {
            sel_row = items.len();
        }
        let star = if s.favorite {
            Span::styled("★ ", Style::default().fg(t.favorite))
        } else {
            Span::styled("  ", Style::default())
        };
        items.push(ListItem::new(Line::from(vec![
            star,
            Span::styled(s.name.to_string(), Style::default().fg(t.fg)),
        ])));
    }

    let list = List::new(items)
        .block(block)
        .highlight_symbol("> ")
        .highlight_style(
            Style::default()
                .bg(t.selection)
                .fg(t.sel_fg)
                .add_modifier(Modifier::BOLD),
        );
    let mut state = ListState::default();
    state.select(Some(sel_row));
    f.render_stateful_widget(list, area, &mut state);
}

fn draw_detail(f: &mut Frame, area: Rect, app: &App) {
    let t = app.theme;
    let rows = Layout::vertical([Constraint::Length(6), Constraint::Min(0)]).split(area);

    // ---- details card ----
    let mut info: Vec<Line> = Vec::new();
    if let Some(s) = app.selected() {
        info.push(Line::from(vec![
            Span::styled("step  ", Style::default().fg(t.muted)),
            Span::styled(s.name.to_string(), Style::default().add_modifier(Modifier::BOLD)),
            Span::styled(
                if s.favorite { "   ★ pinned" } else { "" }.to_string(),
                Style::default().fg(t.favorite),
            ),
        ]));
        info.push(Line::from(vec![
            Span::styled("needs ", Style::default().fg(t.muted)),
            Span::styled(field_summary(s), Style::default().fg(t.cmd)),
        ]));
        info.push(Line::from(vec![
            Span::styled("desc  ", Style::default().fg(t.muted)),
            Span::styled(s.desc.to_string(), Style::default().fg(t.fg)),
        ]));
        info.push(status_line(app, t));
    } else {
        info.push(Line::styled("select a step", Style::default().fg(t.muted)));
    }
    f.render_widget(
        Paragraph::new(info).wrap(Wrap { trim: true }).block(titled("Details", false, t)),
        rows[0],
    );

    // ---- live output ----
    let out_title = match &app.run {
        Some(r) if r.running => format!("Output  {} running", app.spinner_frame()),
        _ => "Output".to_string(),
    };
    let block = titled(&out_title, app.run.as_ref().map(|r| r.running).unwrap_or(false), t);
    let inner_h = rows[1].height.saturating_sub(2) as usize;

    let lines: Vec<Line> = match &app.run {
        Some(r) => {
            let mut ls: Vec<Line> = vec![Line::from(vec![
                Span::styled("$ ", Style::default().fg(t.muted)),
                Span::styled(r.command.clone(), Style::default().fg(t.cmd)),
            ])];
            let avail = inner_h.saturating_sub(1).max(1);
            let start = r.lines.len().saturating_sub(avail);
            for l in &r.lines[start..] {
                ls.push(Line::styled(l.clone(), Style::default().fg(t.fg)));
            }
            if r.lines.is_empty() {
                ls.push(Line::styled("(no output yet)", Style::default().fg(t.muted)));
            }
            ls
        }
        None => vec![Line::styled(
            "press ↵ to set up and run the selected step",
            Style::default().fg(t.muted),
        )],
    };
    f.render_widget(Paragraph::new(lines).block(block), rows[1]);
}

fn draw_input(f: &mut Frame, area: Rect, app: &App) {
    let t = app.theme;
    let i = app.input.as_ref().unwrap();
    let s = &app.steps[i.step];
    let total = s.fields.len();

    let block = titled(&format!("Input — {}", s.name), true, t);
    let inner = block.inner(area);
    f.render_widget(block, area);

    // Header: description, committed values, current prompt.
    let mut head: Vec<Line> = vec![Line::styled(s.desc.to_string(), Style::default().fg(t.muted))];
    for (fi, v) in i.values.iter().enumerate() {
        head.push(Line::from(vec![
            Span::styled(format!("{:>13}  ", s.fields[fi].label), Style::default().fg(t.muted)),
            Span::styled(display_val(v), Style::default().fg(t.cmd)),
        ]));
    }
    let cur = &s.fields[i.field];
    head.push(Line::from(vec![
        Span::styled(
            format!("{:>13}  ", cur.label),
            Style::default().fg(t.title).add_modifier(Modifier::BOLD),
        ),
        Span::styled(format!("({}/{})", i.field + 1, total), Style::default().fg(t.muted)),
    ]));

    let head_h = head.len() as u16;
    let regions = Layout::vertical([Constraint::Length(head_h), Constraint::Min(0)]).split(inner);
    f.render_widget(Paragraph::new(head), regions[0]);

    // Body: text buffer, or a pick list, or an empty-picker note.
    if i.is_text {
        let line = Line::from(vec![
            Span::styled("> ", Style::default().fg(t.title)),
            Span::styled(i.buffer.clone(), Style::default().fg(t.fg)),
            Span::styled(" ", Style::default().bg(t.fg)), // block cursor
        ]);
        f.render_widget(Paragraph::new(line).wrap(Wrap { trim: false }), regions[1]);
    } else if let Some(note) = &i.note {
        f.render_widget(
            Paragraph::new(vec![
                Line::styled(note.clone(), Style::default().fg(t.muted)),
                Line::styled("Esc to cancel", Style::default().fg(t.muted)),
            ])
            .wrap(Wrap { trim: true }),
            regions[1],
        );
    } else {
        let items: Vec<ListItem> = i
            .labels
            .iter()
            .map(|l| ListItem::new(Line::styled(l.clone(), Style::default().fg(t.fg))))
            .collect();
        let list = List::new(items).highlight_symbol("> ").highlight_style(
            Style::default()
                .bg(t.selection)
                .fg(t.sel_fg)
                .add_modifier(Modifier::BOLD),
        );
        let mut state = ListState::default();
        state.select(Some(i.pick));
        f.render_stateful_widget(list, regions[1], &mut state);
    }
}

fn status_line(app: &App, t: Theme) -> Line<'static> {
    match &app.run {
        Some(r) if r.running => Line::from(vec![
            Span::styled("run   ", Style::default().fg(t.muted)),
            Span::styled(
                format!("{} running {}", app.spinner_frame(), r.name),
                Style::default().fg(t.running),
            ),
        ]),
        Some(r) => {
            let (label, color) = match r.success {
                Some(true) => ("✓ done".to_string(), t.ok),
                Some(false) => ("✗ failed".to_string(), t.fail),
                None => ("• ended".to_string(), t.muted),
            };
            Line::from(vec![
                Span::styled("run   ", Style::default().fg(t.muted)),
                Span::styled(label, Style::default().fg(color).add_modifier(Modifier::BOLD)),
                Span::styled(format!("  {} ({}s)", r.name, r.elapsed_secs), Style::default().fg(t.muted)),
            ])
        }
        None => Line::from(vec![
            Span::styled("run   ", Style::default().fg(t.muted)),
            Span::styled("not run yet", Style::default().fg(t.muted)),
        ]),
    }
}

fn draw_footer(f: &mut Frame, area: Rect, app: &App) {
    let t = app.theme;
    let cmds: Vec<(&str, &str)> = if app.input.is_some() {
        let text = app.input.as_ref().map(|i| i.is_text).unwrap_or(false);
        if text {
            vec![("type", "edit"), ("↵", "next"), ("Esc", "cancel")]
        } else {
            vec![("↑↓", "pick"), ("↵", "next"), ("Esc", "cancel")]
        }
    } else if app.filtering {
        vec![("type", "filter"), ("↵", "done"), ("Esc", "clear")]
    } else {
        vec![
            ("↑↓", "move"),
            ("↵", "run"),
            ("/", "search"),
            ("f", "pin"),
            ("t", "theme"),
            ("q", "quit"),
        ]
    };
    let key = Style::default().fg(t.key_fg).bg(t.key).add_modifier(Modifier::BOLD);
    let muted = Style::default().fg(t.muted);
    let mut spans = Vec::new();
    for (k, a) in cmds {
        spans.push(Span::styled(format!(" {k} "), key));
        spans.push(Span::styled(format!(" {a}   "), muted));
    }
    f.render_widget(Paragraph::new(Line::from(spans)), area);
}

/// A bordered block with a bold, padded title in the theme colors.
fn titled(title: &str, focused: bool, t: Theme) -> Block<'static> {
    let border = if focused { t.focus } else { t.border };
    Block::default()
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(Style::default().fg(border))
        .style(Style::default().bg(t.bg))
        .title(Span::styled(
            format!(" {title} "),
            Style::default().fg(t.title).add_modifier(Modifier::BOLD),
        ))
}

/// The inputs a step needs, one line, e.g. "source track · drum density".
fn field_summary(s: &Step) -> String {
    if s.fields.is_empty() {
        return "nothing".to_string();
    }
    s.fields
        .iter()
        .map(|f| f.label)
        .collect::<Vec<_>>()
        .join(" · ")
}

/// Committed values are stored as full paths; show a short two-component form.
fn display_val(v: &str) -> String {
    if v.contains('/') {
        steps::short_label(Path::new(v))
    } else {
        v.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::{display_val, field_summary};
    use crate::steps::{catalog, Step};

    #[test]
    fn display_val_shortens_paths_but_passes_plain_text() {
        assert_eq!(display_val("Stems/htdemucs/Song"), "htdemucs/Song");
        assert_eq!(display_val("tight"), "tight"); // a choice value, no slash
        assert_eq!(display_val("8"), "8"); // seconds text
    }

    #[test]
    fn field_summary_joins_labels_with_a_middot() {
        let deconstruct = catalog().into_iter().find(|s| s.name == "Deconstruct").unwrap();
        assert_eq!(field_summary(&deconstruct), "source track · drum density");
    }

    #[test]
    fn field_summary_of_a_fieldless_step_is_nothing() {
        let s = Step {
            name: "x",
            category: "x",
            desc: "x",
            fields: vec![],
            build: |_| String::new(),
            favorite: false,
        };
        assert_eq!(field_summary(&s), "nothing");
    }
}
