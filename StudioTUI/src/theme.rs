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
