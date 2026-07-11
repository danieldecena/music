use ratatui::style::{Color, Style};

/// Centralised palette. All widget rendering borrows `&Theme` — never
/// hardcodes colours. `name` feeds the header so the label always matches.
pub struct Theme {
    pub name:         &'static str,
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
        // Atom One Light
        Self {
            name:         "Atom One Light",
            bg:           Color::Rgb(250, 250, 250), // #FAFAFA
            surface:      Color::Rgb(239, 239, 239), // #EFEFEF
            surface_dark: Color::Rgb(222, 222, 222), // #DEDEDE
            border:       Color::Rgb(193, 193, 193), // #C1C1C1
            border_hi:    Color::Rgb(64, 120, 242),  // atom blue
            fg:           Color::Rgb(56, 58, 66),    // #383A42
            fg_muted:     Color::Rgb(160, 161, 167), // #A0A1A7
            accent:       Color::Rgb(64, 120, 242),  // #4078F2 atom blue
            accent_fg:    Color::Rgb(250, 250, 250),
            success:      Color::Rgb(80, 161, 79),   // #50A14F atom green
            error:        Color::Rgb(228, 86, 73),   // #E45649 atom red
            warning:      Color::Rgb(193, 132, 1),   // #C18401 atom yellow
            seq_pad_off:  Color::Rgb(215, 215, 215),
            seq_pad_on:   Color::Rgb(64, 120, 242),  // atom blue
            seq_playhead: Color::Rgb(200, 230, 200), // soft green wash
            seq_hit:      Color::Rgb(80, 161, 79),   // atom green
        }
    }

    pub fn dark() -> Self {
        // Atom One Dark
        Self {
            name:         "Atom One Dark",
            bg:           Color::Rgb(40, 44, 52),    // #282C34
            surface:      Color::Rgb(49, 54, 63),    // #31363F
            surface_dark: Color::Rgb(33, 37, 43),    // #21252B
            border:       Color::Rgb(76, 82, 99),    // #4C5263
            border_hi:    Color::Rgb(97, 175, 239),  // atom blue (dark)
            fg:           Color::Rgb(171, 178, 191), // #ABB2BF
            fg_muted:     Color::Rgb(92, 99, 112),   // #5C6370
            accent:       Color::Rgb(97, 175, 239),  // #61AFEF
            accent_fg:    Color::Rgb(40, 44, 52),
            success:      Color::Rgb(152, 195, 121), // #98C379
            error:        Color::Rgb(224, 108, 117), // #E06C75
            warning:      Color::Rgb(229, 192, 123), // #E5C07B
            seq_pad_off:  Color::Rgb(58, 64, 74),
            seq_pad_on:   Color::Rgb(97, 175, 239),
            seq_playhead: Color::Rgb(62, 78, 62),    // soft green wash (dark)
            seq_hit:      Color::Rgb(152, 195, 121),
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
