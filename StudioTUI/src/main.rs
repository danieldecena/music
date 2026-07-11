mod app;
mod fs;
mod theme;
mod ui;
mod worker;

use color_eyre::Result;
use crossterm::event::{self, Event, KeyEventKind};

fn main() -> Result<()> {
    color_eyre::install()?;

    // Panic hook: restore terminal before printing the panic message (skill §6)
    let original_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        ratatui::restore();
        original_hook(info);
    }));

    let mut terminal = ratatui::init();
    let mut app = app::App::new();

    while app.running {
        terminal.draw(|frame| ui::draw(frame, &mut app))?;

        // Drain background channel messages (non-blocking, skill §10)
        app.poll_worker();
        app.poll_seq();
        app.poll_watch();

        // Non-blocking event poll — 50 ms tick for smooth playhead (skill §7)
        if event::poll(std::time::Duration::from_millis(16))? {
            if let Event::Key(key) = event::read()? {
                if key.kind == KeyEventKind::Press {
                    app.handle_key(key.code, key.modifiers);
                }
            }
        }
    }

    ratatui::restore();
    Ok(())
}
