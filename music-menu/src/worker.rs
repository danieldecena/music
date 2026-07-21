// worker.rs — run a music-core.sh function in a background thread and stream its
// merged stdout+stderr back to the UI over a channel. stdin is nulled so any
// interactive `read` in the shell fails fast instead of hanging the render loop
// (the interactive `*.sh` wrappers would otherwise deadlock the TUI).
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::mpsc::{channel, Receiver, Sender};
use std::thread;

pub enum WorkerMsg {
    Line(String),
    Done { success: bool },
}

/// Single-quote a string for zsh (embedded `'` becomes `'\''`).
pub fn sh_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "'\\''"))
}

/// Spawn `zsh -c <cmdline>` in `cwd`, streaming output. Returns the receiver the
/// UI drains each tick.
pub fn run_zsh(cmdline: String, cwd: PathBuf) -> Receiver<WorkerMsg> {
    let (tx, rx) = channel();
    thread::spawn(move || {
        let mut cmd = std::process::Command::new("zsh");
        cmd.arg("-c")
            .arg(&cmdline)
            .current_dir(&cwd)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        match cmd.spawn() {
            Ok(child) => stream_child(child, tx),
            Err(e) => {
                let _ = tx.send(WorkerMsg::Line(format!("zsh spawn failed: {e}")));
                let _ = tx.send(WorkerMsg::Done { success: false });
            }
        }
    });
    rx
}

fn stream_child(mut child: std::process::Child, tx: Sender<WorkerMsg>) {
    use std::io::BufRead;
    // A reader thread for stderr so it interleaves with stdout.
    let err_handle = child.stderr.take().map(|stderr| {
        let tx = tx.clone();
        thread::spawn(move || {
            for line in std::io::BufReader::new(stderr).lines().map_while(Result::ok) {
                if tx.send(WorkerMsg::Line(line)).is_err() {
                    break;
                }
            }
        })
    });
    if let Some(stdout) = child.stdout.take() {
        for line in std::io::BufReader::new(stdout).lines().map_while(Result::ok) {
            if tx.send(WorkerMsg::Line(line)).is_err() {
                break;
            }
        }
    }
    if let Some(h) = err_handle {
        let _ = h.join();
    }
    let success = child.wait().map(|s| s.success()).unwrap_or(false);
    let _ = tx.send(WorkerMsg::Done { success });
}
