use ratatui::style::Color;

// The Ratatui Design palette. The terminal is the canvas: flat navy surfaces,
// cream/yellow accents, no gradients. Selection is reversed video — a yellow
// fill with navy text — the design system's golden-rule idiom. Dark is the
// brand identity (navy #14152b / cream #f4e0c4 / yellow #e8c14b); light is a
// warm-paper inversion that keeps contrast on a bright field.
#[derive(Clone, Copy)]
pub struct Theme {
    pub light: bool,
    pub bg: Color,        // app background (terminal backdrop)
    pub fg: Color,        // default text
    pub muted: Color,     // secondary text
    pub selection: Color, // reversed-video selection fill
    pub sel_fg: Color,    // text on the selection fill
    pub title: Color,     // block titles
    pub key: Color,       // keybind chip fill / filter caret
    pub key_fg: Color,    // text on a keybind chip
    pub category: Color,  // category headers
    pub favorite: Color,  // ★ pinned marker
    pub cmd: Color,       // the command string
    pub running: Color,   // spinner + running label
    pub ok: Color,        // exit 0
    pub fail: Color,      // non-zero exit
    pub focus: Color,     // focused block border
    pub border: Color,    // unfocused block border
}

impl Theme {
    pub fn dark() -> Self {
        Theme {
            light: false,
            bg: Color::Rgb(0x14, 0x15, 0x2b),        // brand navy
            fg: Color::Rgb(0xe6, 0xe6, 0xee),        // text-primary
            muted: Color::Rgb(0x76, 0x76, 0x76),     // ansi darkgray
            selection: Color::Rgb(0xe8, 0xc1, 0x4b), // brand yellow
            sel_fg: Color::Rgb(0x0d, 0x0e, 0x1c),    // deepest navy
            title: Color::Rgb(0xe8, 0xc1, 0x4b),
            key: Color::Rgb(0xe8, 0xc1, 0x4b),
            key_fg: Color::Rgb(0x0d, 0x0e, 0x1c),
            category: Color::Rgb(0x2f, 0xb3, 0xb3),  // ansi cyan
            favorite: Color::Rgb(0xe8, 0xc1, 0x4b),
            cmd: Color::Rgb(0xb3, 0x4d, 0xb3),       // ansi magenta
            running: Color::Rgb(0x2f, 0xb3, 0xb3),
            ok: Color::Rgb(0x33, 0xaa, 0x33),        // ansi green
            fail: Color::Rgb(0xcc, 0x33, 0x33),      // ansi red
            focus: Color::Rgb(0xe8, 0xc1, 0x4b),
            border: Color::Rgb(0x3a, 0x3d, 0x63),
        }
    }

    pub fn light() -> Self {
        Theme {
            light: true,
            bg: Color::Rgb(0xf4, 0xe0, 0xc4),        // brand cream
            fg: Color::Rgb(0x14, 0x15, 0x2b),        // navy ink
            muted: Color::Rgb(0x8a, 0x7d, 0x68),
            selection: Color::Rgb(0x14, 0x15, 0x2b), // navy fill (reversed for a bright field)
            sel_fg: Color::Rgb(0xf4, 0xe0, 0xc4),
            title: Color::Rgb(0x9a, 0x6a, 0x00),     // dark amber
            key: Color::Rgb(0x14, 0x15, 0x2b),
            key_fg: Color::Rgb(0xf4, 0xe0, 0xc4),
            category: Color::Rgb(0x1f, 0x6f, 0x6f),  // teal
            favorite: Color::Rgb(0x9a, 0x6a, 0x00),
            cmd: Color::Rgb(0x9a, 0x2f, 0x8a),       // magenta
            running: Color::Rgb(0x1f, 0x6f, 0x6f),
            ok: Color::Rgb(0x2d, 0x7a, 0x2d),
            fail: Color::Rgb(0xb3, 0x3a, 0x3a),
            focus: Color::Rgb(0x9a, 0x6a, 0x00),
            border: Color::Rgb(0xcb, 0xb8, 0x96),
        }
    }

    pub fn toggle(self) -> Self {
        if self.light {
            Theme::dark()
        } else {
            Theme::light()
        }
    }
}
