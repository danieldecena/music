use std::path::PathBuf;
use std::sync::mpsc::Receiver;
use std::time::Instant;

use crate::steps::{self, FieldKind, Step};
use crate::theme::Theme;
use crate::worker::{self, WorkerMsg};

pub const SPINNER: [&str; 10] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

/// A running (or finished) music-core.sh call and its streamed output.
pub struct RunState {
    pub name: String,
    pub command: String,
    pub rx: Receiver<WorkerMsg>,
    pub lines: Vec<String>,
    pub running: bool,
    pub success: Option<bool>,
    pub started: Instant,
    pub elapsed_secs: u64,
    pub spinner: usize,
}

/// Collecting the inputs a step needs before it can run. One field at a time.
pub struct InputState {
    pub step: usize,           // index into App::steps
    pub field: usize,          // current field
    pub values: Vec<String>,   // committed values so far
    pub buffer: String,        // text-field edit buffer
    pub is_text: bool,         // text field vs. pick list
    pub options: Vec<String>,  // values to commit (paths / choice strings)
    pub labels: Vec<String>,   // display labels for the pick list
    pub pick: usize,
    pub note: Option<String>,  // e.g. an empty-picker hint
}

struct Setup {
    is_text: bool,
    buffer: String,
    options: Vec<String>,
    labels: Vec<String>,
    note: Option<String>,
}

pub struct App {
    pub root: PathBuf,
    pub steps: Vec<Step>,
    pub filtered: Vec<usize>,
    pub sel: usize,
    pub filtering: bool,
    pub query: String,
    pub theme: Theme,
    pub run: Option<RunState>,
    pub input: Option<InputState>,
}

impl App {
    pub fn open(root: PathBuf) -> App {
        let mut app = App {
            root,
            steps: steps::catalog(),
            filtered: vec![],
            sel: 0,
            filtering: false,
            query: String::new(),
            theme: Theme::dark(),
            run: None,
            input: None,
        };
        app.rebuild_filter();
        app
    }

    /// Visible order: favorites first, then by category, narrowed by the query.
    pub fn rebuild_filter(&mut self) {
        let q = self.query.to_lowercase();
        let matches = |s: &Step| {
            q.is_empty()
                || s.name.to_lowercase().contains(&q)
                || s.desc.to_lowercase().contains(&q)
                || s.category.to_lowercase().contains(&q)
        };
        let mut favs: Vec<usize> = self
            .steps
            .iter()
            .enumerate()
            .filter(|(_, s)| s.favorite && matches(s))
            .map(|(i, _)| i)
            .collect();
        favs.sort_by(|&a, &b| self.steps[a].name.cmp(self.steps[b].name));

        let mut rest: Vec<usize> = self
            .steps
            .iter()
            .enumerate()
            .filter(|(_, s)| !s.favorite && matches(s))
            .map(|(i, _)| i)
            .collect();
        rest.sort_by(|&a, &b| {
            self.steps[a]
                .category
                .cmp(self.steps[b].category)
                .then_with(|| self.steps[a].name.cmp(self.steps[b].name))
        });

        self.filtered = favs;
        self.filtered.extend(rest);
        if self.sel >= self.filtered.len() {
            self.sel = self.filtered.len().saturating_sub(1);
        }
    }

    pub fn selected(&self) -> Option<&Step> {
        self.filtered.get(self.sel).map(|&i| &self.steps[i])
    }

    pub fn move_sel(&mut self, delta: isize) {
        let len = self.filtered.len();
        if len == 0 {
            return;
        }
        self.sel = (self.sel as isize + delta).rem_euclid(len as isize) as usize;
    }

    pub fn toggle_favorite(&mut self) {
        if let Some(&i) = self.filtered.get(self.sel) {
            self.steps[i].favorite = !self.steps[i].favorite;
            self.rebuild_filter();
        }
    }

    pub fn toggle_theme(&mut self) {
        self.theme = self.theme.toggle();
    }

    // ---- filter mode ----
    pub fn filter_push(&mut self, c: char) {
        self.query.push(c);
        self.sel = 0;
        self.rebuild_filter();
    }
    pub fn filter_backspace(&mut self) {
        self.query.pop();
        self.sel = 0;
        self.rebuild_filter();
    }
    pub fn filter_clear(&mut self) {
        self.query.clear();
        self.filtering = false;
        self.sel = 0;
        self.rebuild_filter();
    }

    // ---- input collection ----

    /// Begin collecting inputs for the selected step (or run it immediately if
    /// it needs none). No-op while a run is in flight.
    pub fn start_selected(&mut self) {
        if self.run.as_ref().map(|r| r.running).unwrap_or(false) {
            return;
        }
        let Some(&step) = self.filtered.get(self.sel) else {
            return;
        };
        if self.steps[step].fields.is_empty() {
            self.run_step(step, &[]);
            return;
        }
        self.input = Some(InputState {
            step,
            field: 0,
            values: vec![],
            buffer: String::new(),
            is_text: false,
            options: vec![],
            labels: vec![],
            pick: 0,
            note: None,
        });
        self.begin_field();
    }

    pub fn input_cancel(&mut self) {
        self.input = None;
    }

    pub fn input_move(&mut self, delta: isize) {
        if let Some(i) = self.input.as_mut() {
            let len = i.options.len();
            if i.is_text || len == 0 {
                return;
            }
            i.pick = (i.pick as isize + delta).rem_euclid(len as isize) as usize;
        }
    }

    pub fn input_char(&mut self, c: char) {
        if let Some(i) = self.input.as_mut() {
            if i.is_text {
                i.buffer.push(c);
            }
        }
    }

    pub fn input_backspace(&mut self) {
        if let Some(i) = self.input.as_mut() {
            if i.is_text {
                i.buffer.pop();
            }
        }
    }

    /// Commit the current field. Advances to the next field, or runs the step
    /// once the last field is in.
    pub fn input_commit(&mut self) {
        let done = {
            let i = self.input.as_mut().unwrap();
            let val = if i.is_text {
                let b = i.buffer.trim().to_string();
                if b.is_empty() {
                    return;
                }
                b
            } else {
                if i.options.is_empty() {
                    return;
                }
                i.options[i.pick].clone()
            };
            i.values.push(val);
            i.field += 1;
            i.field >= self.steps[i.step].fields.len()
        };
        if done {
            let (step, values) = {
                let i = self.input.as_ref().unwrap();
                (i.step, i.values.clone())
            };
            self.run_step(step, &values);
            self.input = None;
        } else {
            self.begin_field();
        }
    }

    /// Populate the input state for the field it currently points at.
    fn begin_field(&mut self) {
        let (step, field) = {
            let i = self.input.as_ref().unwrap();
            (i.step, i.field)
        };
        let s = self.field_setup(step, field);
        let i = self.input.as_mut().unwrap();
        i.is_text = s.is_text;
        i.buffer = s.buffer;
        i.options = s.options;
        i.labels = s.labels;
        i.pick = 0;
        i.note = s.note;
    }

    fn field_setup(&self, step: usize, field: usize) -> Setup {
        match &self.steps[step].fields[field].kind {
            FieldKind::Url => Setup {
                is_text: true,
                buffer: String::new(),
                options: vec![],
                labels: vec![],
                note: None,
            },
            FieldKind::Text(def) => Setup {
                is_text: true,
                buffer: def.to_string(),
                options: vec![],
                labels: vec![],
                note: None,
            },
            FieldKind::Choice(opts) => Setup {
                is_text: false,
                buffer: String::new(),
                options: opts.iter().map(|s| s.to_string()).collect(),
                labels: opts.iter().map(|s| s.to_string()).collect(),
                note: None,
            },
            FieldKind::Source => {
                mk_picker(steps::find_sources(&self.root), "no audio found — run Download first")
            }
            FieldKind::Stems => mk_picker(
                steps::find_stem_dirs(&self.root),
                "no stems yet — run Separate or Deconstruct first",
            ),
            FieldKind::OneShots => mk_picker(
                steps::find_oneshots(&self.root),
                "no one-shots yet — run Split drums first",
            ),
        }
    }

    // ---- running ----

    fn run_step(&mut self, step: usize, values: &[String]) {
        let s = &self.steps[step];
        let command = (s.build)(values);
        let name = s.name.to_string();
        let cmdline = format!("source lib/music-core.sh; {command} 2>&1");
        let rx = worker::run_zsh(cmdline, self.root.clone());
        self.run = Some(RunState {
            name,
            command,
            rx,
            lines: Vec::new(),
            running: true,
            success: None,
            started: Instant::now(),
            elapsed_secs: 0,
            spinner: 0,
        });
    }

    /// Each tick: pull new output lines and advance the spinner.
    pub fn poll_run(&mut self) {
        let Some(rs) = self.run.as_mut() else {
            return;
        };
        if !rs.running {
            return;
        }
        rs.spinner = (rs.spinner + 1) % SPINNER.len();
        while let Ok(msg) = rs.rx.try_recv() {
            match msg {
                WorkerMsg::Line(l) => {
                    rs.lines.push(l);
                    if rs.lines.len() > 1000 {
                        rs.lines.remove(0);
                    }
                }
                WorkerMsg::Done { success } => {
                    rs.running = false;
                    rs.success = Some(success);
                    rs.elapsed_secs = rs.started.elapsed().as_secs();
                }
            }
        }
    }

    pub fn spinner_frame(&self) -> &'static str {
        SPINNER[self.run.as_ref().map(|r| r.spinner).unwrap_or(0)]
    }
}

fn mk_picker(paths: Vec<PathBuf>, empty_hint: &str) -> Setup {
    let labels: Vec<String> = paths.iter().map(|p| steps::short_label(p)).collect();
    let options: Vec<String> = paths.iter().map(|p| p.to_string_lossy().to_string()).collect();
    let note = if options.is_empty() {
        Some(empty_hint.to_string())
    } else {
        None
    };
    Setup {
        is_text: false,
        buffer: String::new(),
        options,
        labels,
        note,
    }
}
