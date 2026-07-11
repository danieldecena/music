use ratatui::{
    buffer::Buffer,
    layout::{Constraint, Layout, Rect},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Widget},
};

use crate::app::{App, Focus, LIB_CATS};
use crate::theme::Theme;
use crate::ui::pipeline::render_hint;

// ── Library tab widget ────────────────────────────────────────────────────────

pub struct LibraryTab<'a> {
    pub app: &'a App,
}

impl<'a> Widget for LibraryTab<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        let t = &self.app.theme;
        let app = self.app;

        let [main_area, hint_area] = Layout::vertical([
            Constraint::Fill(1),
            Constraint::Length(1),
        ]).areas(area);

        let [cats_area, files_area] = Layout::horizontal([
            Constraint::Length(18),
            Constraint::Fill(1),
        ]).areas(main_area);

        render_categories(app, t, cats_area, buf);
        render_files(app, t, files_area, buf);
        render_hint(t, hint_area, buf,
            "j/k move · Enter play · m mangle · o reveal · / filter · h/l category · r refresh · 1-4 tabs · q quit");
    }
}

fn render_categories(app: &App, t: &Theme, area: Rect, buf: &mut Buffer) {
    let items: Vec<ListItem> = LIB_CATS.iter().enumerate().map(|(i, (_, label))| {
        let active = i == app.lib_cat_idx;
        // 1-9 keys map onto categories, so surface the number.
        let num = i + 1;
        if active {
            let style = Style::new().fg(t.accent_fg).bg(t.accent).add_modifier(Modifier::BOLD);
            ListItem::new(Line::from(Span::styled(format!(" ▸ {num} {label}"), style)))
        } else {
            let num_style = Style::new().fg(t.fg_muted).bg(t.surface);
            let label_style = Style::new().fg(t.fg).bg(t.surface);
            ListItem::new(Line::from(vec![
                Span::styled(format!("   {num} "), num_style),
                Span::styled(label.to_string(), label_style),
            ]))
        }
    }).collect();

    let block = Block::new()
        .title(Span::styled(" CATEGORIES ", Style::new().fg(t.accent).add_modifier(Modifier::BOLD)))
        .borders(Borders::ALL)
        .border_type(t.border_type)
        .border_style(t.border())
        .style(Style::new().bg(t.surface));

    List::new(items).block(block).render(area, buf);
}

fn render_files(app: &App, t: &Theme, area: Rect, buf: &mut Buffer) {
    let filter_focused = app.focus == Focus::LibraryFilter;
    let show_filter = filter_focused || !app.lib_filter.is_empty();

    let [filter_area, list_area] = Layout::vertical([
        Constraint::Length(if show_filter { 1 } else { 0 }),
        Constraint::Fill(1),
    ]).areas(area);

    if show_filter {
        let style = if filter_focused {
            Style::new().fg(t.accent).add_modifier(Modifier::UNDERLINED)
        } else {
            Style::new().fg(t.fg_muted)
        };
        Line::from(Span::styled(format!("/ {}", app.lib_filter), style))
            .render(filter_area, buf);
    }

    let selected = app.lib_state.selected().unwrap_or(0);
    let cat_label = LIB_CATS[app.lib_cat_idx].1;

    // Drop a redundant leading path prefix common to every entry so the
    // informative tail (folder + filename) stays visible.
    let prefix = common_prefix(&app.lib_files);

    // Inner text budget: width minus 2 borders minus the 2-char row marker.
    let text_w = (list_area.width as usize).saturating_sub(4).max(8);

    let items: Vec<ListItem> = app.lib_files.iter().enumerate().map(|(i, f)| {
        let placeholder = f.starts_with('—');
        let selected_row = i == selected && !placeholder;
        let meta = if placeholder { None } else { app.meta_for(f) };
        let badge = meta.map(|(bpm, key)| format!(" ⟨{bpm}·{key}⟩ "));
        let badge_w = badge.as_ref().map(|b| b.chars().count()).unwrap_or(0);

        let shown = if placeholder {
            f.clone()
        } else {
            let stripped = f.strip_prefix(&prefix).unwrap_or(f);
            truncate_start(stripped, text_w.saturating_sub(badge_w))
        };

        if selected_row {
            let style = Style::new().fg(t.accent_fg).bg(t.accent).add_modifier(Modifier::BOLD);
            let mut spans = vec![Span::styled(format!("▸ {shown}"), style)];
            if let Some(b) = badge {
                spans.push(Span::styled(b, style));
            }
            ListItem::new(Line::from(spans))
        } else if placeholder {
            ListItem::new(Line::from(Span::styled(
                format!("  {shown}"),
                Style::new().fg(t.fg_muted).bg(t.bg).add_modifier(Modifier::ITALIC),
            )))
        } else {
            let mut spans = vec![Span::styled(
                format!("  {shown}"),
                Style::new().fg(t.fg).bg(t.bg),
            )];
            if let Some(b) = badge {
                spans.push(Span::styled(b, Style::new().fg(t.fg_muted).bg(t.bg)));
            }
            ListItem::new(Line::from(spans))
        }
    }).collect();

    let count = app.lib_files.iter().filter(|f| !f.starts_with('—')).count();

    let mut block = Block::new()
        .title(Span::styled(
            format!(" {cat_label} · {count} file(s) "),
            Style::new().fg(t.accent).add_modifier(Modifier::BOLD),
        ))
        .borders(Borders::ALL)
        .border_type(t.border_type)
        .border_style(t.border_hi())
        .style(Style::new().bg(t.bg));

    // Show the common prefix that was hidden (so paths stay unambiguous) plus
    // the action affordance for the selected file along the bottom edge.
    if !prefix.is_empty() {
        block = block.title(Span::styled(
            format!(" {prefix} "),
            Style::new().fg(t.fg_muted),
        ));
    }
    let selected_real = app.lib_files.get(selected).map(|f| !f.starts_with('—')).unwrap_or(false);
    if selected_real {
        block = block.title_bottom(Line::from(Span::styled(
            " Enter play · m mangle ",
            Style::new().fg(t.accent),
        )));
    }

    List::new(items).block(block).render(list_area, buf);
}

/// Longest directory prefix (aligned to `/` segments) shared by every real
/// entry. Filenames are never counted, so the result always ends at a folder
/// boundary. Empty when there is nothing safe to strip.
fn common_prefix(files: &[String]) -> String {
    let real: Vec<&String> = files.iter().filter(|f| !f.starts_with('—')).collect();
    if real.len() < 2 {
        return String::new();
    }
    let first: Vec<&str> = real[0].split('/').collect();
    // Cap at the directory portion of the first entry (exclude its filename).
    let mut end = first.len().saturating_sub(1);
    for f in &real[1..] {
        let segs: Vec<&str> = f.split('/').collect();
        let cap = segs.len().saturating_sub(1);
        let mut i = 0;
        while i < end && i < cap && segs[i] == first[i] {
            i += 1;
        }
        end = i;
        if end == 0 {
            return String::new();
        }
    }
    if end == 0 {
        return String::new();
    }
    let mut p = first[..end].join("/");
    p.push('/');
    p
}

/// Keep the tail of a path (the most identifying part) when it overflows,
/// prefixing an ellipsis so it is clear the head was trimmed.
fn truncate_start(s: &str, max: usize) -> String {
    let len = s.chars().count();
    if len <= max {
        return s.to_string();
    }
    let keep = max.saturating_sub(1);
    let tail: String = s.chars().skip(len - keep).collect();
    format!("…{tail}")
}
