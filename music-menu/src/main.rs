use std::io;
use std::path::PathBuf;
use std::time::Duration;

use ratatui::crossterm::event::{self, Event, KeyCode, KeyEventKind};
use ratatui::DefaultTerminal;

mod app;
mod steps;
mod theme;
mod ui;
mod worker;

use app::App;

fn main() -> io::Result<()> {
    // The music workspace to operate on: first CLI arg, else the cwd. music-core.sh
    // resolves its own MUSIC_DIR from its file location, so the cwd must be a repo
    // checkout that contains lib/music-core.sh.
    // Canonicalize so discovered paths and the run cwd are both absolute: a
    // relative arg like `..` would otherwise be baked into every source path
    // AND used as the run cwd, so `../Apple Music/x` resolves from the wrong dir.
    let root = std::env::args()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
    let root = root.canonicalize().unwrap_or(root);

    let mut terminal = ratatui::init();
    let mut app = App::open(root);
    let result = run(&mut terminal, &mut app);
    ratatui::restore();
    result
}

fn run(terminal: &mut DefaultTerminal, app: &mut App) -> io::Result<()> {
    loop {
        terminal.draw(|frame| ui::draw(frame, app))?;

        // Poll with a timeout so live output + the spinner keep updating even
        // when no keys are pressed.
        if event::poll(Duration::from_millis(100))? {
            if let Event::Key(key) = event::read()? {
                if key.kind != KeyEventKind::Press {
                    continue;
                }
                // 1) Collecting inputs for a step.
                if app.input.is_some() {
                    let is_text = app.input.as_ref().map(|i| i.is_text).unwrap_or(false);
                    match key.code {
                        KeyCode::Esc => app.input_cancel(),
                        KeyCode::Enter => app.input_commit(),
                        KeyCode::Down => app.input_move(1),
                        KeyCode::Up => app.input_move(-1),
                        _ if is_text => match key.code {
                            KeyCode::Backspace => app.input_backspace(),
                            KeyCode::Char(c) => app.input_char(c),
                            _ => {}
                        },
                        // pick-list navigation
                        KeyCode::Char('j') | KeyCode::Right | KeyCode::Tab => app.input_move(1),
                        KeyCode::Char('k') | KeyCode::Left => app.input_move(-1),
                        _ => {}
                    }
                    continue;
                }
                // 2) Editing the search filter.
                if app.filtering {
                    match key.code {
                        KeyCode::Esc => app.filter_clear(),
                        // Open the highlighted step directly — one Enter from a
                        // filtered list to running it, no separate commit step.
                        KeyCode::Enter => {
                            app.filtering = false;
                            app.start_selected();
                        }
                        KeyCode::Backspace => app.filter_backspace(),
                        KeyCode::Up => app.move_sel(-1),
                        KeyCode::Down => app.move_sel(1),
                        KeyCode::Char(c) => app.filter_push(c),
                        _ => {}
                    }
                    continue;
                }
                // 3) The menu.
                match key.code {
                    KeyCode::Char('q') => break,
                    // Esc backs out of an active filter first; only quits the app
                    // when there's no filter left to clear.
                    KeyCode::Esc if !app.query.is_empty() => app.filter_clear(),
                    KeyCode::Esc => break,
                    KeyCode::Down | KeyCode::Char('j') => app.move_sel(1),
                    KeyCode::Up | KeyCode::Char('k') => app.move_sel(-1),
                    KeyCode::Enter => app.start_selected(),
                    KeyCode::Char('/') => app.filtering = true,
                    KeyCode::Char('f') => app.toggle_favorite(),
                    KeyCode::Char('t') => app.toggle_theme(),
                    _ => {}
                }
            }
        }
        app.poll_run();
    }
    Ok(())
}
