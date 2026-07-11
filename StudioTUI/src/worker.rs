use std::path::PathBuf;
use std::process::Stdio;
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;

/// Messages sent from background workers to the main loop.
#[derive(Debug)]
pub enum WorkerMsg {
    Line(String),
    Done { success: bool },
}

/// Single-quote a string for zsh (embedded `'` becomes `'\''`).
pub fn sh_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "'\\''"))
}

/// Stream a spawned child's stdout+stderr back as `Line`s, then `Done`.
fn stream_child(mut child: std::process::Child, tx: Sender<WorkerMsg>) {
    use std::io::BufRead;
    let err_handle = child.stderr.take().map(|stderr| {
        let tx = tx.clone();
        thread::spawn(move || {
            for line in std::io::BufReader::new(stderr).lines().map_while(Result::ok) {
                if tx.send(WorkerMsg::Line(line)).is_err() { break; }
            }
        })
    });
    if let Some(stdout) = child.stdout.take() {
        for line in std::io::BufReader::new(stdout).lines().map_while(Result::ok) {
            if tx.send(WorkerMsg::Line(line)).is_err() { break; }
        }
    }
    if let Some(h) = err_handle { let _ = h.join(); }
    let success = child.wait().map(|s| s.success()).unwrap_or(false);
    let _ = tx.send(WorkerMsg::Done { success });
}

/// Run an arbitrary zsh command line (e.g. `source lib/music-core.sh; fn args…`).
/// stdin is nulled so interactive `read`s fail fast instead of hanging the TUI.
pub fn run_zsh(cmdline: String, cwd: PathBuf, tx: Sender<WorkerMsg>) {
    thread::spawn(move || {
        let mut cmd = std::process::Command::new("zsh");
        cmd.arg("-c").arg(&cmdline).current_dir(&cwd)
           .stdin(Stdio::null())
           .stdout(Stdio::piped())
           .stderr(Stdio::piped());
        match cmd.spawn() {
            Ok(child) => stream_child(child, tx),
            Err(e) => {
                let _ = tx.send(WorkerMsg::Line(format!("✗ zsh spawn failed: {e}")));
                let _ = tx.send(WorkerMsg::Done { success: false });
            }
        }
    });
}

/// Runs a venv python script with an arbitrary argv, streaming output back.
pub fn run_python(
    python: PathBuf,
    script: PathBuf,
    args: Vec<String>,
    cwd: PathBuf,
    tx: Sender<WorkerMsg>,
) {
    thread::spawn(move || {
        let mut cmd = std::process::Command::new(&python);
        cmd.arg(&script).args(&args).current_dir(&cwd)
           .stdin(Stdio::null())
           .stdout(Stdio::piped())
           .stderr(Stdio::piped());
        match cmd.spawn() {
            Ok(child) => stream_child(child, tx),
            Err(_) => {
                let _ = tx.send(WorkerMsg::Line(format!("✗ python not found: {}", python.display())));
                let _ = tx.send(WorkerMsg::Done { success: false });
            }
        }
    });
}

/// Reveal a file in Finder (macOS `open -R`). Fire-and-forget.
pub fn reveal_in_finder(path: PathBuf) {
    thread::spawn(move || {
        let _ = std::process::Command::new("open").arg("-R").arg(&path)
            .stdout(Stdio::null()).stderr(Stdio::null()).status();
    });
}

pub fn preview_file(path: PathBuf) {
    thread::spawn(move || {
        let ext = path.extension().and_then(|e| e.to_str()).unwrap_or("").to_lowercase();
        if path.exists() && !matches!(ext.as_str(), "mid" | "midi") {
            let _ = std::process::Command::new("afplay").arg(&path)
                .stdout(Stdio::null()).stderr(Stdio::null()).status();
        } else {
            beep();
        }
    });
}

pub fn beep() {
    // afplay with a built-in system sound is ~10x faster than osascript beep.
    // stdout/stderr are nulled: afplay inherits the TUI's real terminal fds
    // (ratatui's alternate screen doesn't isolate them), so any error text it
    // prints — e.g. no CoreAudio route available — writes directly onto the
    // screen and corrupts rendering until a full repaint.
    thread::spawn(|| {
        let _ = std::process::Command::new("afplay")
            .arg("/System/Library/Sounds/Tock.aiff")
            .stdout(Stdio::null()).stderr(Stdio::null())
            .status();
    });
}

/// Creates a sequencer tick channel.
/// Returns (sender for the tick thread, receiver for the main loop).
pub fn seq_ticker(bpm: u32) -> (Sender<()>, Receiver<()>) {
    let (tick_tx, tick_rx) = mpsc::channel::<()>();
    let (stop_tx, stop_rx) = mpsc::channel::<()>();
    thread::spawn(move || {
        loop {
            let interval = std::time::Duration::from_secs_f64(60.0 / bpm.max(1) as f64 / 4.0);
            thread::sleep(interval);
            if tick_tx.send(()).is_err() { break; }
            if stop_rx.try_recv().is_ok() { break; }
        }
    });
    (stop_tx, tick_rx)
}
