use std::collections::{HashMap, HashSet, VecDeque};
use std::path::{Path, PathBuf};
use std::sync::mpsc::{Receiver, Sender};
use std::time::Instant;

use crossterm::event::{KeyCode, KeyModifiers};
use ratatui::widgets::ListState;

use crate::fs::{lib_dirs, scan_audio, source_tracks, stem_folders};
use crate::theme::Theme;
use crate::worker::{self, WorkerMsg};

// ── Tabs ─────────────────────────────────────────────────────────────────────
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum ActiveTab { Pipeline, Sequencer, Logic, Library }

pub const TABS: &[(&str, ActiveTab)] = &[
    ("1 Pipeline",  ActiveTab::Pipeline),
    ("2 Sequencer", ActiveTab::Sequencer),
    ("3 Logic Pro", ActiveTab::Logic),
    ("4 Library",   ActiveTab::Library),
];

// ── Sequencer ────────────────────────────────────────────────────────────────
pub const SEQ_INSTS: &[&str] = &["Kick","Snare","Hat","Openhat","Clap","808"];
// GM drum notes, same mapping as Scripts/beat_export.py's DEFAULT_NOTE.
const SEQ_NOTES: &[u8] = &[36, 38, 42, 46, 39, 35];
pub const SEQ_BARS: &[u32] = &[1, 2, 4, 8];

// ── Log level ─────────────────────────────────────────────────────────────────
#[derive(Clone, Copy)]
pub enum LogLevel { Info, Ok, Err, Plain }

#[derive(Clone)]
pub struct LogLine {
    pub text: String,
    pub level: LogLevel,
}

// ── Job queue ─────────────────────────────────────────────────────────────────
#[derive(Clone)]
pub struct Job {
    pub label:   String,
    pub cmdline: String,
}

impl Job {
    fn new(label: impl Into<String>, cmdline: String) -> Self {
        Self { label: label.into(), cmdline }
    }
}

// ── Library categories ────────────────────────────────────────────────────────
pub const LIB_CATS: &[(&str, &str)] = &[
    ("stems","Stems"), ("oneshots","One-Shots"), ("vocals","Vocals"), ("chops","Chops"),
    ("loops","Loops"), ("kits","Kits"), ("midi","MIDI"), ("resynth","Resynth"),
    ("mangled","Mangled"),
];

// ── Pipeline actions ──────────────────────────────────────────────────────────
pub const PIPELINE_ACTIONS: &[(&str, &str)] = &[
    ("Download",         "download.sh"),
    ("Analyze BPM+Key",  "analyze.sh"),
    ("Separate Stems",   "stems.sh"),
    ("Full Pipeline",    ""),              // chain
    ("Chop Drums",       "chop-drums.sh"),
    ("Sort Kit",         "sort-kit.sh"),
    ("Chop Vocals",      "chop.sh"),
    ("Chop Stems",       "chop-stems.sh"),
    ("Deconstruct",      "deconstruct.sh"),
    ("Bass → MIDI",      "bass-to-midi.sh"),
    ("Re-voice Melody",  "revoice.sh"),
    ("Build Logic Proj", "build-logic-project.sh"),
];

/// core-function param values, in the order the UI cycles them (docs/DESIGN-SYSTEM.md §3b).
const STEM_MODES:   &[&str] = &["6stem", "4stem", "instrumental"];
const DENSITIES:    &[&str] = &["loose", "tight"];
const CHOP_SECONDS: &[u32]  = &[8, 4, 16];

// ── Input focus ───────────────────────────────────────────────────────────────
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Focus {
    PipelineActions,
    PipelineUrl,
    PipelineTempo,
    SeqGrid,
    SeqBpm,
    SeqName,
    LibraryList,
    LibraryFilter,
    LogicTransport,
}

// ── Help overlay keymaps (single source of truth — docs/DESIGN-SYSTEM.md §2) ──
pub fn global_keymap() -> &'static [(&'static str, &'static str)] {
    &[
        ("1-4", "switch tabs"),
        ("q",   "quit"),
        ("?",   "help overlay"),
        ("0",   "toggle theme"),
        ("c",   "clear console"),
        ("r",   "refresh library"),
        ("W",   "toggle watch mode"),
    ]
}

pub fn keymap_for(tab: ActiveTab) -> &'static [(&'static str, &'static str)] {
    match tab {
        ActiveTab::Pipeline => &[
            ("j/k",         "select action"),
            ("Enter/Space", "run action (queues job)"),
            ("u",           "edit download URL"),
            ("t",           "edit tempo"),
            ("Left/Right",  "cycle source track"),
            ("[ / ]",       "cycle stem folder"),
            ("s",           "cycle stem mode"),
            ("d",           "cycle density"),
            ("g",           "cycle chop seconds"),
            ("a",           "batch-deconstruct all sources"),
            ("Esc",         "cancel queued jobs"),
        ],
        ActiveTab::Sequencer => &[
            ("hjkl/arrows", "move cursor"),
            ("Space/Enter", "toggle step"),
            ("p",           "play/stop"),
            ("+/-",         "nudge BPM"),
            ("n",           "edit name"),
            ("b",           "edit BPM"),
            ("B",           "cycle bars"),
            ("K",           "cycle kit"),
            ("x",           "clear pattern"),
            ("S",           "save pattern"),
            ("L",           "load pattern"),
            ("m",           "export MIDI"),
            ("w",           "export WAV"),
        ],
        ActiveTab::Logic => &[
            ("s",             "status"),
            ("c",             "connect / disconnect"),
            ("Space/x/[/,/.", "play/stop/start/rwd/fwd"),
            ("R",             "record"),
            ("t/u/o",         "list/mute/solo tracks"),
            ("w/n/b/e",       "save/new/bounce/export project"),
        ],
        ActiveTab::Library => &[
            ("j/k",         "move"),
            ("Enter/Space", "preview"),
            ("m",           "mangle"),
            ("o",           "reveal in Finder"),
            ("/",           "filter"),
            ("h/l",         "category"),
        ],
    }
}

// ── App state (Model) ─────────────────────────────────────────────────────────
pub struct App {
    pub running:   bool,
    pub tab:       ActiveTab,
    pub theme:     Theme,
    pub root:      PathBuf,
    pub focus:     Focus,
    pub help_open: bool,

    // Pipeline
    pub pipeline_sel:  usize,
    pub source_tracks: Vec<String>,
    pub stem_folders:  Vec<String>,
    pub source_idx:    usize,
    pub stems_idx:     usize,
    pub download_url:  String,
    pub stem_mode_idx: usize,   // 0=6-stem 1=4-stem 2=instrumental
    pub density_idx:   usize,   // 0=loose 1=tight
    pub chop_s_idx:    usize,   // 0=8 1=4 2=16
    pub tempo_str:     String,
    pub job_queue:     VecDeque<Job>,

    // Console
    pub log_lines: Vec<LogLine>,
    pub worker_rx: Option<Receiver<WorkerMsg>>,
    pub logic_status_pending: bool,

    // Sequencer
    pub seq_matrix:   [[bool; 16]; 6],
    pub seq_step:     usize,
    pub seq_cursor:   (usize, usize), // (row, col)
    pub seq_playing:  bool,
    pub seq_bpm:      u32,
    pub seq_bpm_str:  String,
    pub seq_name:     String,
    pub seq_bars_idx: usize,
    pub seq_kit_idx:  usize,   // 0 = "any"; 1.. indexes kit_folders
    pub kit_folders:  Vec<String>,
    pub seq_rx:       Option<Receiver<()>>,
    pub seq_stop_tx:  Option<Sender<()>>,

    // Library
    pub lib_cat_idx:   usize,
    pub lib_files_all: Vec<String>,
    pub lib_files:     Vec<String>,
    pub lib_state:     ListState,
    pub lib_filter:    String,
    pub catalog:       HashMap<String, (String, String)>,

    // Logic
    pub logic_ok:     bool,
    pub logic_project: String,
    pub logic_tempo:   String,
    pub logic_key:     String,
    pub logic_bar:     String,

    // Watch mode
    pub watch_on:        bool,
    known_sources:        HashSet<String>,
    last_watch_scan:      Instant,
}

impl App {
    pub fn new() -> Self {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent()
                       .unwrap_or(&PathBuf::from(".")).to_path_buf();

        let source_tracks = source_tracks(&root);
        let stem_folders  = stem_folders(&root);
        let kit_folders   = crate::fs::kit_folders(&root);
        let catalog       = load_catalog(&root);

        let lib_files_all = {
            let dirs = lib_dirs(&root, "stems");
            scan_audio(&root, &dirs)
        };
        let lib_files = if lib_files_all.is_empty() {
            vec!["— no stems found —".into()]
        } else { lib_files_all.clone() };

        Self {
            running:       true,
            tab:           ActiveTab::Pipeline,
            theme:         Theme::light(),
            root,
            focus:         Focus::PipelineActions,
            help_open:     false,

            pipeline_sel:  0,
            source_tracks,
            stem_folders,
            source_idx:    0,
            stems_idx:     0,
            download_url:  String::new(),
            stem_mode_idx: 0,
            density_idx:   0,
            chop_s_idx:    0,
            tempo_str:     "120".into(),
            job_queue:     VecDeque::new(),

            log_lines: vec![LogLine {
                text:  "Ready — press 1-4 to switch tabs, ? for help.".into(),
                level: LogLevel::Info,
            }],
            worker_rx: None,
            logic_status_pending: false,

            seq_matrix:   [[false; 16]; 6],
            seq_step:     0,
            seq_cursor:   (0, 0),
            seq_playing:  false,
            seq_bpm:      120,
            seq_bpm_str:  "120".into(),
            seq_name:     "beat".into(),
            seq_bars_idx: 1, // 2 bars
            seq_kit_idx:  0, // "any"
            kit_folders,
            seq_rx:       None,
            seq_stop_tx:  None,

            lib_cat_idx: 0,
            lib_files_all,
            lib_files,
            lib_state:   ListState::default().with_selected(Some(0)),
            lib_filter:  String::new(),
            catalog,

            logic_ok:      false,
            logic_project: "—".into(),
            logic_tempo:   "—".into(),
            logic_key:     "—".into(),
            logic_bar:     "—".into(),

            watch_on:         false,
            known_sources:    HashSet::new(),
            last_watch_scan:  Instant::now(),
        }
    }

    // ── Log helpers ───────────────────────────────────────────────────────────
    pub fn log(&mut self, text: impl Into<String>, level: LogLevel) {
        use std::time::{SystemTime, UNIX_EPOCH};
        let secs = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
        let h = (secs / 3600) % 24;
        let m = (secs / 60) % 60;
        let s = secs % 60;
        let prefix = match level {
            LogLevel::Info  => "[·] ",
            LogLevel::Ok    => "[ok] ",
            LogLevel::Err   => "[!] ",
            LogLevel::Plain => "",
        };
        let line = format!("{h:02}:{m:02}:{s:02} {prefix}{}", text.into());
        self.log_lines.push(LogLine { text: line, level });
        // Keep last 200 lines
        if self.log_lines.len() > 200 {
            self.log_lines.remove(0);
        }
    }

    // ── Poll worker messages (call every frame) ───────────────────────────────
    pub fn poll_worker(&mut self) {
        // Collect messages first to avoid simultaneous borrow of self
        let msgs: Vec<WorkerMsg> = match &self.worker_rx {
            Some(rx) => std::iter::from_fn(|| rx.try_recv().ok()).collect(),
            None => return,
        };
        let mut done = false;
        for msg in msgs {
            match msg {
                WorkerMsg::Line(l) => {
                    if self.logic_status_pending {
                        self.parse_logic_status_line(&l);
                    }
                    self.log(l, LogLevel::Plain);
                }
                WorkerMsg::Done { success } => {
                    if success { self.log("✓ Done", LogLevel::Ok); }
                    else       { self.log("✗ Failed", LogLevel::Err); }
                    self.logic_status_pending = false;
                    done = true;
                }
            }
        }
        if done {
            self.worker_rx = None;
            self.start_next_job();
        }
    }

    fn parse_logic_status_line(&mut self, l: &str) {
        if let Some(v) = l.strip_prefix("running: ") {
            self.logic_ok = v.trim() == "yes";
            if !self.logic_ok {
                self.logic_project = "—".into();
                self.logic_tempo   = "—".into();
                self.logic_key     = "—".into();
                self.logic_bar     = "—".into();
            }
        } else if let Some(v) = l.strip_prefix("project: ") {
            self.logic_project = v.trim().to_string();
        } else if let Some(v) = l.strip_prefix("tempo: ") {
            self.logic_tempo = v.trim().to_string();
        } else if let Some(v) = l.strip_prefix("key: ") {
            self.logic_key = v.trim().to_string();
        } else if let Some(v) = l.strip_prefix("bar: ") {
            self.logic_bar = v.trim().to_string();
        }
    }

    // ── Poll sequencer tick ───────────────────────────────────────────────────
    pub fn poll_seq(&mut self) {
        let Some(rx) = &self.seq_rx else { return };
        if rx.try_recv().is_ok() {
            let step = self.seq_step;
            // Fire any active pads
            let any = self.seq_matrix.iter().any(|row| row[step]);
            if any { worker::beep(); }
            self.seq_step = (step + 1) % 16;
        }
    }

    // ── Poll watch mode (call every frame; internally rate-limited to 2s) ─────
    pub fn poll_watch(&mut self) {
        if !self.watch_on { return; }
        if self.last_watch_scan.elapsed() < std::time::Duration::from_secs(2) { return; }
        self.last_watch_scan = Instant::now();

        let current = source_tracks(&self.root);
        let new: Vec<String> = current.iter()
            .filter(|s| !s.starts_with('—') && !self.known_sources.contains(*s))
            .cloned().collect();
        for s in &current {
            if !s.starts_with('—') { self.known_sources.insert(s.clone()); }
        }
        self.source_tracks = current;

        if !new.is_empty() {
            let lib  = self.lib_cmd_prefix();
            let dens = DENSITIES[self.density_idx];
            for track in &new {
                self.log(format!("Watch: new file detected — {track}"), LogLevel::Ok);
                self.job_queue.push_back(Job::new(
                    "Deconstruct",
                    format!("{lib} deconstruct {} {} 2>&1", worker::sh_quote(track), worker::sh_quote(dens)),
                ));
            }
            self.start_next_job();
        }
    }

    fn toggle_watch(&mut self) {
        self.watch_on = !self.watch_on;
        if self.watch_on {
            self.known_sources = self.source_tracks.iter().cloned().collect();
            self.last_watch_scan = Instant::now();
            self.log("Watch mode on — rescanning sources every ~2s.", LogLevel::Info);
        } else {
            self.log("Watch mode off.", LogLevel::Info);
        }
    }

    fn toggle_theme(&mut self) {
        self.theme = if self.theme.name == "Atom One Light" { Theme::dark() } else { Theme::light() };
        self.log(format!("Theme → {}", self.theme.name), LogLevel::Info);
    }

    // ── Key routing: input focus → tab handler → global fallback ─────────────
    fn is_text_focus(&self) -> bool {
        matches!(
            self.focus,
            Focus::PipelineUrl | Focus::PipelineTempo | Focus::SeqBpm | Focus::SeqName | Focus::LibraryFilter
        )
    }

    pub fn handle_key(&mut self, code: KeyCode, mods: KeyModifiers) {
        use KeyCode::*;

        if self.is_text_focus() {
            match self.tab {
                ActiveTab::Pipeline  => { self.handle_pipeline(code, mods); }
                ActiveTab::Sequencer => { self.handle_sequencer(code, mods); }
                ActiveTab::Logic     => { self.handle_logic(code); }
                ActiveTab::Library   => { self.handle_library(code); }
            }
            return;
        }

        if self.help_open {
            if matches!(code, Char('?') | Esc) { self.help_open = false; }
            return;
        }

        let consumed = match self.tab {
            ActiveTab::Pipeline  => self.handle_pipeline(code, mods),
            ActiveTab::Sequencer => self.handle_sequencer(code, mods),
            ActiveTab::Logic     => self.handle_logic(code),
            ActiveTab::Library   => self.handle_library(code),
        };
        if consumed { return; }

        // Global fallback (unshadowed by tab-local keys — e.g. Logic's own `c`).
        match code {
            Char('q') | Char('Q') => { self.stop_seq(); self.running = false; }
            Char('1') => { self.tab = ActiveTab::Pipeline;  self.focus = Focus::PipelineActions; }
            Char('2') => { self.tab = ActiveTab::Sequencer; self.focus = Focus::SeqGrid; }
            Char('3') => { self.tab = ActiveTab::Logic;     self.focus = Focus::LogicTransport; }
            Char('4') => { self.tab = ActiveTab::Library;   self.focus = Focus::LibraryList; }
            Char('c') => { self.log_lines.clear(); }
            Char('r') => { self.refresh_lib(); }
            Char('?') => { self.help_open = true; }
            Char('0') => { self.toggle_theme(); }
            Char('W') => { self.toggle_watch(); }
            _ => {}
        }
    }

    // ── Job queue ──────────────────────────────────────────────────────────────
    fn lib_cmd_prefix(&self) -> String {
        let lib = self.root.join("lib/music-core.sh");
        format!("source {};", worker::sh_quote(&lib.to_string_lossy()))
    }

    fn start_next_job(&mut self) {
        if self.worker_rx.is_some() { return; }
        if let Some(job) = self.job_queue.pop_front() {
            self.log(format!("▶ {}", job.label), LogLevel::Info);
            let (tx, rx) = std::sync::mpsc::channel();
            self.worker_rx = Some(rx);
            worker::run_zsh(job.cmdline.clone(), self.root.clone(), tx);
        }
    }

    fn clear_queue(&mut self) {
        let n = self.job_queue.len();
        self.job_queue.clear();
        if n > 0 { self.log(format!("Cleared {n} queued job(s)."), LogLevel::Info); }
    }

    // ── Pipeline ─────────────────────────────────────────────────────────────
    fn handle_pipeline(&mut self, code: KeyCode, _mods: KeyModifiers) -> bool {
        use KeyCode::*;
        match self.focus {
            Focus::PipelineUrl => {
                match code {
                    Esc => self.focus = Focus::PipelineActions,
                    Char(c) => self.download_url.push(c),
                    Backspace => { self.download_url.pop(); }
                    Enter => self.focus = Focus::PipelineActions,
                    _ => {}
                }
                true
            }
            Focus::PipelineTempo => {
                match code {
                    Esc => self.focus = Focus::PipelineActions,
                    Char(c) if c.is_ascii_digit() => self.tempo_str.push(c),
                    Backspace => { self.tempo_str.pop(); }
                    Enter => self.focus = Focus::PipelineActions,
                    _ => {}
                }
                true
            }
            Focus::PipelineActions => match code {
                Char('j') | Down  => { self.pipeline_sel = (self.pipeline_sel + 1).min(PIPELINE_ACTIONS.len() - 1); true }
                Char('k') | Up    => { self.pipeline_sel = self.pipeline_sel.saturating_sub(1); true }
                Char('u')         => { self.focus = Focus::PipelineUrl; true }
                Char('t')         => { self.focus = Focus::PipelineTempo; true }
                Char('[')         => { self.cycle_stems(false); true }
                Char(']')         => { self.cycle_stems(true); true }
                Char('s')         => { self.stem_mode_idx = (self.stem_mode_idx + 1) % STEM_MODES.len(); true }
                Char('d')         => { self.density_idx = (self.density_idx + 1) % DENSITIES.len(); true }
                Char('g')         => { self.chop_s_idx = (self.chop_s_idx + 1) % CHOP_SECONDS.len(); true }
                Left              => { self.cycle_source(false); true }
                Right             => { self.cycle_source(true); true }
                Char('a')         => { self.batch_deconstruct_all(); true }
                Enter | Char(' ') => { self.run_pipeline(self.pipeline_sel); true }
                Esc               => { self.clear_queue(); true }
                _ => false,
            },
            _ => false,
        }
    }

    fn cycle_source(&mut self, fwd: bool) {
        let n = self.source_tracks.len();
        if n == 0 { return; }
        let step = if fwd { 1usize } else { usize::MAX };
        self.source_idx = self.source_idx.wrapping_add(step) % n;
    }

    fn cycle_stems(&mut self, fwd: bool) {
        let n = self.stem_folders.len();
        if n == 0 { return; }
        let step = if fwd { 1usize } else { usize::MAX };
        self.stems_idx = self.stems_idx.wrapping_add(step) % n;
    }

    /// Currently-selected source track, or None if the workspace has none yet.
    fn current_source(&self) -> Option<String> {
        self.source_tracks.get(self.source_idx).cloned().filter(|s| !s.starts_with('—'))
    }

    /// Currently-selected Stems track folder, or None if none exist yet.
    fn current_stem_folder(&self) -> Option<String> {
        self.stem_folders.get(self.stems_idx).cloned().filter(|s| !s.starts_with('—'))
    }

    /// Builds the job(s) a pipeline action should enqueue, per
    /// docs/DESIGN-SYSTEM.md §3b's function table. Empty = missing required input.
    fn build_jobs(&self, idx: usize) -> Vec<Job> {
        let lib   = self.lib_cmd_prefix();
        let mode  = STEM_MODES[self.stem_mode_idx];
        let dens  = DENSITIES[self.density_idx];
        let chop_s = CHOP_SECONDS[self.chop_s_idx];

        match idx {
            0 => { // Download
                if self.download_url.is_empty() { return vec![]; }
                let out = self.root.join("Apple Music").to_string_lossy().into_owned();
                vec![Job::new("Download", format!(
                    "{lib} download_url {} {} 2>&1",
                    worker::sh_quote(&self.download_url), worker::sh_quote(&out),
                ))]
            }
            1 => { // Analyze BPM+Key
                let Some(s) = self.current_source() else { return vec![] };
                vec![Job::new("Analyze BPM+Key", format!("{lib} analyze_track {} 2>&1", worker::sh_quote(&s)))]
            }
            2 => { // Separate Stems
                let Some(s) = self.current_source() else { return vec![] };
                vec![Job::new("Separate Stems", format!(
                    "{lib} separate_stems {} {} Stems 2>&1",
                    worker::sh_quote(&s), worker::sh_quote(mode),
                ))]
            }
            3 => { // Full Pipeline: analyze -> separate -> chop_vocals
                let Some(s) = self.current_source() else { return vec![] };
                let track = Path::new(&s).file_stem().map(|f| f.to_string_lossy().into_owned()).unwrap_or_default();
                let model_dir = if mode == "6stem" { "htdemucs_6s" } else { "htdemucs" };
                let vocals = format!("Stems/{model_dir}/{track}/vocals.wav");
                vec![
                    Job::new("Analyze BPM+Key", format!("{lib} analyze_track {} 2>&1", worker::sh_quote(&s))),
                    Job::new("Separate Stems", format!(
                        "{lib} separate_stems {} {} Stems 2>&1", worker::sh_quote(&s), worker::sh_quote(mode),
                    )),
                    Job::new("Chop Vocals", format!(
                        "{lib} chop_vocals {} Samples/Vocals {} 2>&1", worker::sh_quote(&vocals), worker::sh_quote(dens),
                    )),
                ]
            }
            4 => { // Chop Drums
                let Some(sf) = self.current_stem_folder() else { return vec![] };
                vec![Job::new("Chop Drums", format!(
                    "{lib} chop_drums {} Samples/One-Shots {} 2>&1", worker::sh_quote(&sf), worker::sh_quote(dens),
                ))]
            }
            5 => { // Sort Kit
                let Some(sf) = self.current_stem_folder() else { return vec![] };
                let track = Path::new(&sf).file_name().map(|f| f.to_string_lossy().into_owned()).unwrap_or_default();
                let dir = format!("Samples/One-Shots/{track}");
                vec![Job::new("Sort Kit", format!("{lib} sort_kit {} 2>&1", worker::sh_quote(&dir)))]
            }
            6 => { // Chop Vocals
                let Some(sf) = self.current_stem_folder() else { return vec![] };
                let vocals = format!("{sf}/vocals.wav");
                vec![Job::new("Chop Vocals", format!(
                    "{lib} chop_vocals {} Samples/Vocals {} 2>&1", worker::sh_quote(&vocals), worker::sh_quote(dens),
                ))]
            }
            7 => { // Chop Stems
                let Some(sf) = self.current_stem_folder() else { return vec![] };
                vec![Job::new("Chop Stems", format!(
                    "{lib} chop_stems {} Samples/Chops {chop_s} 2>&1", worker::sh_quote(&sf),
                ))]
            }
            8 => { // Deconstruct
                let Some(s) = self.current_source() else { return vec![] };
                vec![Job::new("Deconstruct", format!(
                    "{lib} deconstruct {} {} 2>&1", worker::sh_quote(&s), worker::sh_quote(dens),
                ))]
            }
            9 | 10 | 11 => { // Bass→MIDI / Re-voice / Build Logic — arg-accepting wrapper scripts
                let Some(sf) = self.current_stem_folder() else { return vec![] };
                let (label, script) = PIPELINE_ACTIONS[idx];
                let script_path = self.root.join(script);
                vec![Job::new(label, format!(
                    "{} {} 2>&1", worker::sh_quote(&script_path.to_string_lossy()), worker::sh_quote(&sf),
                ))]
            }
            _ => vec![],
        }
    }

    fn run_pipeline(&mut self, idx: usize) {
        let (label, _) = PIPELINE_ACTIONS[idx];
        let jobs = self.build_jobs(idx);
        if jobs.is_empty() {
            self.log(format!("{label} — missing input (no source/stem folder yet)."), LogLevel::Err);
            return;
        }
        let n = jobs.len();
        for j in jobs { self.job_queue.push_back(j); }
        self.log(format!("Queued {n} job(s) for {label}."), LogLevel::Info);
        self.start_next_job();
    }

    fn batch_deconstruct_all(&mut self) {
        let lib  = self.lib_cmd_prefix();
        let dens = DENSITIES[self.density_idx];
        let mut n = 0;
        for s in self.source_tracks.clone() {
            if s.starts_with('—') { continue; }
            self.job_queue.push_back(Job::new("Deconstruct", format!(
                "{lib} deconstruct {} {} 2>&1", worker::sh_quote(&s), worker::sh_quote(dens),
            )));
            n += 1;
        }
        if n == 0 {
            self.log("No source tracks to batch-deconstruct.", LogLevel::Err);
        } else {
            self.log(format!("Batch-queued {n} deconstruct job(s)."), LogLevel::Info);
            self.start_next_job();
        }
    }

    // ── Sequencer ─────────────────────────────────────────────────────────────
    fn handle_sequencer(&mut self, code: KeyCode, _mods: KeyModifiers) -> bool {
        use KeyCode::*;

        match self.focus {
            Focus::SeqName => {
                match code {
                    Esc | Enter => self.focus = Focus::SeqGrid,
                    Char(c) => self.seq_name.push(c),
                    Backspace => { self.seq_name.pop(); }
                    _ => {}
                }
                return true;
            }
            Focus::SeqBpm => {
                match code {
                    Esc => self.focus = Focus::SeqGrid,
                    Enter => {
                        if let Ok(v) = self.seq_bpm_str.parse::<u32>() {
                            self.seq_bpm = v.clamp(40, 300);
                        }
                        self.seq_bpm_str = self.seq_bpm.to_string();
                        self.restart_seq_if_playing();
                        self.focus = Focus::SeqGrid;
                    }
                    Char(c) if c.is_ascii_digit() => self.seq_bpm_str.push(c),
                    Backspace => { self.seq_bpm_str.pop(); }
                    _ => {}
                }
                return true;
            }
            _ => {}
        }

        let (row, col) = self.seq_cursor;
        match code {
            Char('p') | Char(' ') if col == 16 => { self.toggle_seq(); true }
            Char(' ') | Enter => {
                self.seq_matrix[row][col] ^= true;
                if self.seq_matrix[row][col] { worker::beep(); }
                true
            }
            Up    | Char('k') => { self.seq_cursor.0 = row.saturating_sub(1); true }
            Down  | Char('j') => { self.seq_cursor.0 = (row + 1).min(SEQ_INSTS.len() - 1); true }
            Left  | Char('h') => { self.seq_cursor.1 = col.saturating_sub(1); true }
            Right | Char('l') => { self.seq_cursor.1 = (col + 1).min(15); true }
            Char('p') => { self.toggle_seq(); true }
            Char('+') => {
                self.seq_bpm = (self.seq_bpm + 5).min(300);
                self.seq_bpm_str = self.seq_bpm.to_string();
                self.restart_seq_if_playing();
                true
            }
            Char('-') => {
                self.seq_bpm = self.seq_bpm.saturating_sub(5).max(40);
                self.seq_bpm_str = self.seq_bpm.to_string();
                self.restart_seq_if_playing();
                true
            }
            Char('m') => { self.export_seq("midi"); true }
            Char('w') => { self.export_seq("wav"); true }
            Char('n') => { self.focus = Focus::SeqName; true }
            Char('b') => { self.focus = Focus::SeqBpm; true }
            Char('B') => { self.seq_bars_idx = (self.seq_bars_idx + 1) % SEQ_BARS.len(); true }
            Char('K') => { self.seq_kit_idx = (self.seq_kit_idx + 1) % (self.kit_folders.len() + 1); true }
            Char('x') => { self.seq_matrix = [[false; 16]; 6]; self.log("Pattern cleared.", LogLevel::Info); true }
            Char('S') => { self.save_pattern(); true }
            Char('L') => { self.load_pattern(); true }
            _ => false,
        }
    }

    /// Kit scoping the WAV sample lookup: None = search all of Samples/One-Shots.
    pub fn current_kit(&self) -> Option<&str> {
        if self.seq_kit_idx == 0 { None } else { self.kit_folders.get(self.seq_kit_idx - 1).map(String::as_str) }
    }

    pub fn kit_label(&self) -> &str {
        self.current_kit().unwrap_or("any")
    }

    pub fn bars_label(&self) -> String {
        SEQ_BARS[self.seq_bars_idx].to_string()
    }

    /// Renders the current seq_matrix pattern via Scripts/beat_export.py.
    /// mode = "midi" | "wav".
    fn export_seq(&mut self, mode: &str) {
        let rows: Vec<(usize, String)> = (0..SEQ_INSTS.len())
            .filter(|&r| self.seq_matrix[r].iter().any(|&on| on))
            .map(|r| {
                let pattern: String = self.seq_matrix[r]
                    .iter().map(|&on| if on { '1' } else { '0' }).collect();
                (r, pattern)
            })
            .collect();
        if rows.is_empty() {
            self.log("Nothing to export — no active steps.", LogLevel::Err);
            return;
        }

        let (out_rel, ext) = if mode == "midi" {
            (format!("Samples/MIDI/{}.mid", self.seq_name), "MIDI")
        } else {
            (format!("Samples/Loops/{}.wav", self.seq_name), "WAV")
        };
        let out_path = self.root.join(&out_rel);

        let mut args = vec![
            mode.to_string(),
            out_path.to_string_lossy().into_owned(),
            "--bpm".into(), self.seq_bpm.to_string(),
            "--steps".into(), "16".into(),
            "--reps".into(), SEQ_BARS[self.seq_bars_idx].to_string(),
        ];
        let kit = self.current_kit().map(str::to_string);
        for (r, pattern) in rows {
            let name = SEQ_INSTS[r].to_lowercase();
            let mut row = format!("{}:{}:{}", name, SEQ_NOTES[r], pattern);
            if mode == "wav" {
                if let Some(sample) = crate::fs::find_sample_for(&self.root, &name, kit.as_deref()) {
                    row.push(':');
                    row.push_str(&sample.to_string_lossy());
                }
            }
            args.push("--row".into());
            args.push(row);
        }

        self.log(format!("▶ Export {ext} → {out_rel}"), LogLevel::Info);
        let python = self.root.join(".venv/bin/python");
        let script = self.root.join("Scripts/beat_export.py");
        let (tx, rx) = std::sync::mpsc::channel();
        self.worker_rx = Some(rx);
        worker::run_python(python, script, args, self.root.clone(), tx);
    }

    fn toggle_seq(&mut self) {
        if self.seq_playing { self.stop_seq(); }
        else               { self.start_seq(); }
    }

    fn start_seq(&mut self) {
        self.seq_step    = 0;
        self.seq_playing = true;
        let (stop_tx, tick_rx) = worker::seq_ticker(self.seq_bpm);
        self.seq_rx      = Some(tick_rx);
        self.seq_stop_tx = Some(stop_tx);
        self.log("Sequencer started.", LogLevel::Info);
    }

    fn stop_seq(&mut self) {
        self.seq_playing = false;
        if let Some(tx) = self.seq_stop_tx.take() {
            let _ = tx.send(());
        }
        self.seq_rx = None;
        if self.seq_playing { self.log("Sequencer stopped.", LogLevel::Info); }
        self.seq_playing = false;
    }

    fn restart_seq_if_playing(&mut self) {
        if self.seq_playing {
            let step = self.seq_step;
            self.stop_seq();
            self.start_seq();
            self.seq_step = step;
        }
    }

    fn save_pattern(&mut self) {
        if self.seq_name.trim().is_empty() {
            self.log("Set a name (n) before saving.", LogLevel::Err);
            return;
        }
        let dir = self.root.join("Samples/Patterns");
        if std::fs::create_dir_all(&dir).is_err() {
            self.log("Failed to create Samples/Patterns.", LogLevel::Err);
            return;
        }
        let path = dir.join(format!("{}.pattern", self.seq_name));
        let mut out = format!(
            "bpm={}\nbars={}\nkit={}\nname={}\n",
            self.seq_bpm, SEQ_BARS[self.seq_bars_idx], self.kit_label(), self.seq_name,
        );
        for row in &self.seq_matrix {
            let line: String = row.iter().map(|&on| if on { '1' } else { '0' }).collect();
            out.push_str(&line);
            out.push('\n');
        }
        match std::fs::write(&path, out) {
            Ok(_) => self.log(format!("Saved pattern → Samples/Patterns/{}.pattern", self.seq_name), LogLevel::Ok),
            Err(e) => self.log(format!("Save failed: {e}"), LogLevel::Err),
        }
    }

    fn load_pattern(&mut self) {
        if self.seq_name.trim().is_empty() {
            self.log("Set a name (n) before loading.", LogLevel::Err);
            return;
        }
        let path = self.root.join("Samples/Patterns").join(format!("{}.pattern", self.seq_name));
        let Ok(text) = std::fs::read_to_string(&path) else {
            self.log(format!("No pattern named '{}'.", self.seq_name), LogLevel::Err);
            return;
        };
        let mut rows: Vec<[bool; 16]> = Vec::new();
        for line in text.lines() {
            if let Some(v) = line.strip_prefix("bpm=") {
                if let Ok(b) = v.parse::<u32>() {
                    self.seq_bpm = b.clamp(40, 300);
                    self.seq_bpm_str = self.seq_bpm.to_string();
                }
            } else if let Some(v) = line.strip_prefix("bars=") {
                if let Ok(b) = v.parse::<u32>() {
                    if let Some(i) = SEQ_BARS.iter().position(|&x| x == b) { self.seq_bars_idx = i; }
                }
            } else if let Some(v) = line.strip_prefix("kit=") {
                if v == "any" {
                    self.seq_kit_idx = 0;
                } else if let Some(i) = self.kit_folders.iter().position(|k| k == v) {
                    self.seq_kit_idx = i + 1;
                }
            } else if line.starts_with("name=") {
                // seq_name is already the load key; nothing to do.
            } else if line.len() == 16 && line.chars().all(|c| c == '0' || c == '1') {
                let mut row = [false; 16];
                for (i, c) in line.chars().enumerate() { row[i] = c == '1'; }
                rows.push(row);
            }
        }
        for (i, row) in rows.into_iter().take(6).enumerate() {
            self.seq_matrix[i] = row;
        }
        self.restart_seq_if_playing();
        self.log(format!("Loaded pattern '{}'.", self.seq_name), LogLevel::Ok);
    }

    // ── Logic ─────────────────────────────────────────────────────────────────
    fn handle_logic(&mut self, code: KeyCode) -> bool {
        use KeyCode::*;
        match code {
            Char('s') => { self.run_logic_cli("status", true); true }
            Char('c') => {
                if self.logic_ok {
                    self.logic_ok = false;
                    self.logic_project = "—".into();
                    self.logic_tempo   = "—".into();
                    self.logic_key     = "—".into();
                    self.logic_bar     = "—".into();
                    self.log("Logic Pro disconnected.", LogLevel::Info);
                } else {
                    self.run_logic_cli("status", true);
                }
                true
            }
            // transport
            Char('p') | Char(' ') => { self.run_logic_cli("play", false); true }
            Char('x') => { self.run_logic_cli("stop", false); true }
            Char('[') => { self.run_logic_cli("gotostart", false); true }
            Char(',') => { self.run_logic_cli("rewind", false); true }
            Char('.') => { self.run_logic_cli("ff", false); true }
            Char('R') => { self.run_logic_cli("record", false); true }
            // tracks
            Char('t') => { self.run_logic_cli("listtracks", false); true }
            Char('u') => { self.run_logic_cli("mute", false); true }
            Char('o') => { self.run_logic_cli("solo", false); true }
            // project
            Char('w') => { self.run_logic_cli("save", false); true }
            Char('n') => { self.run_logic_cli("newproject", false); true }
            Char('b') => { self.run_logic_cli("bounce", false); true }
            Char('e') => { self.run_logic_cli("export", false); true }
            _ => false,
        }
    }

    /// Shells out to logic-pro-mcp's CLI (its own venv) for a real Logic Pro
    /// action. `status_pending` marks the call so poll_worker parses its
    /// output into logic_project/tempo/key/bar instead of just logging it.
    fn run_logic_cli(&mut self, cmd: &str, status_pending: bool) {
        let mcp = self.root.join("logic-pro-mcp");
        let python = mcp.join(".venv/bin/python");
        let script = mcp.join("logic_cli.py");
        if !python.exists() {
            self.log("logic-pro-mcp venv not found — set it up first.", LogLevel::Err);
            return;
        }
        self.log(format!("▶ Logic → {cmd}"), LogLevel::Info);
        self.logic_status_pending = status_pending;
        let (tx, rx) = std::sync::mpsc::channel();
        self.worker_rx = Some(rx);
        worker::run_python(python, script, vec![cmd.to_string()], self.root.clone(), tx);
    }

    // ── Library ───────────────────────────────────────────────────────────────
    fn handle_library(&mut self, code: KeyCode) -> bool {
        use KeyCode::*;

        if self.focus == Focus::LibraryFilter {
            match code {
                Esc | Enter => self.focus = Focus::LibraryList,
                Char(c) => { self.lib_filter.push(c); self.apply_lib_filter(); }
                Backspace => { self.lib_filter.pop(); self.apply_lib_filter(); }
                _ => {}
            }
            return true;
        }

        match code {
            Char('j') | Down  => {
                let max = self.lib_files.len().saturating_sub(1);
                let cur = self.lib_state.selected().unwrap_or(0);
                self.lib_state.select(Some((cur + 1).min(max)));
                true
            }
            Char('k') | Up => {
                let cur = self.lib_state.selected().unwrap_or(0);
                self.lib_state.select(Some(cur.saturating_sub(1)));
                true
            }
            Enter | Char(' ') => {
                if let Some(idx) = self.lib_state.selected() {
                    if let Some(rel) = self.lib_files.get(idx) {
                        if !rel.starts_with('—') {
                            let path = self.root.join(rel);
                            self.log(format!("▶ afplay {rel}"), LogLevel::Info);
                            worker::preview_file(path);
                        }
                    }
                }
                true
            }
            Char('o') => {
                if let Some(idx) = self.lib_state.selected() {
                    if let Some(rel) = self.lib_files.get(idx).cloned() {
                        if rel.starts_with('—') {
                            self.log("Nothing selected to reveal.", LogLevel::Err);
                        } else {
                            self.log(format!("▶ reveal {rel}"), LogLevel::Info);
                            worker::reveal_in_finder(self.root.join(&rel));
                        }
                    }
                }
                true
            }
            Char('/') => { self.focus = Focus::LibraryFilter; true }
            Char('m') => {
                if let Some(idx) = self.lib_state.selected() {
                    if let Some(rel) = self.lib_files.get(idx).cloned() {
                        if rel.starts_with('—') {
                            self.log("Nothing selected to mangle.", LogLevel::Err);
                        } else {
                            self.log(format!("▶ Mangle {rel}"), LogLevel::Info);
                            let script = self.root.join("mangle.sh");
                            let cmdline = format!(
                                "{} {} 2>&1",
                                worker::sh_quote(&script.to_string_lossy()), worker::sh_quote(&rel),
                            );
                            self.job_queue.push_back(Job::new("Mangle", cmdline));
                            self.start_next_job();
                            self.log("→ variants land in Samples/Mangled — open the Mangled tab and press r.", LogLevel::Info);
                        }
                    }
                }
                true
            }
            Left  | Char('h') => { let i = self.lib_cat_idx.saturating_sub(1); self.set_lib_cat(i); true }
            Right | Char('l') => { let n = LIB_CATS.len() - 1; let i = (self.lib_cat_idx + 1).min(n); self.set_lib_cat(i); true }
            _ => false,
        }
    }

    fn set_lib_cat(&mut self, idx: usize) {
        self.lib_cat_idx = idx.min(LIB_CATS.len() - 1);
        self.lib_filter.clear();
        self.refresh_lib();
    }

    fn apply_lib_filter(&mut self) {
        if self.lib_files_all.is_empty() {
            let cat = LIB_CATS[self.lib_cat_idx].1;
            self.lib_files = vec![format!("— no {cat} found —")];
        } else {
            let needle = self.lib_filter.to_lowercase();
            let filtered: Vec<String> = if needle.is_empty() {
                self.lib_files_all.clone()
            } else {
                self.lib_files_all.iter().filter(|f| f.to_lowercase().contains(&needle)).cloned().collect()
            };
            self.lib_files = if filtered.is_empty() { vec!["— no matches —".into()] } else { filtered };
        }
        self.lib_state.select(Some(0));
    }

    pub fn refresh_lib(&mut self) {
        let cat = LIB_CATS[self.lib_cat_idx].0;
        let dirs = lib_dirs(&self.root, cat);
        self.lib_files_all = scan_audio(&self.root, &dirs);
        self.apply_lib_filter();
        let n = self.lib_files_all.len();
        self.log(format!("Library: {n} file(s) in {cat}"), LogLevel::Info);
    }

    /// BPM/key badge for a Stems row, keyed off the catalog map loaded at
    /// startup (`Scripts/catalog.py ready --json`). `rel_path` is a Stems-tab
    /// entry like `Stems/htdemucs/<track>/vocals.wav`.
    pub fn meta_for(&self, rel_path: &str) -> Option<(&str, &str)> {
        let track = Path::new(rel_path).parent()?.file_name()?.to_str()?;
        self.catalog.get(track).map(|(b, k)| (b.as_str(), k.as_str()))
    }
}

// ── Catalog loading (F6) ───────────────────────────────────────────────────────

fn load_catalog(root: &Path) -> HashMap<String, (String, String)> {
    let python = root.join(".venv/bin/python");
    let script = root.join("Scripts/catalog.py");
    if !python.exists() || !script.exists() { return HashMap::new(); }
    let out = std::process::Command::new(&python)
        .arg(&script).arg("ready").arg("--limit").arg("1000").arg("--json")
        .current_dir(root)
        .output();
    let Ok(out) = out else { return HashMap::new(); };
    if !out.status.success() { return HashMap::new(); }
    parse_catalog_json(&String::from_utf8_lossy(&out.stdout))
}

/// Minimal hand-rolled parse of `catalog.py ready --json`'s flat (non-nested)
/// object array — avoids a serde dependency (PLAN.md keeps deps at 3).
fn parse_catalog_json(text: &str) -> HashMap<String, (String, String)> {
    let mut map = HashMap::new();
    let mut i = 0usize;
    while let Some(start) = text[i..].find('{') {
        let abs_start = i + start;
        let Some(end_rel) = text[abs_start..].find('}') else { break };
        let obj = &text[abs_start..abs_start + end_rel + 1];
        i = abs_start + end_rel + 1;

        let track = extract_str_field(obj, "track");
        let bpm   = extract_num_field(obj, "bpm");
        let key   = extract_str_field(obj, "key");
        if let (Some(t), Some(b), Some(k)) = (track, bpm, key) {
            map.insert(t, (b, k));
        }
    }
    map
}

fn extract_str_field(obj: &str, field: &str) -> Option<String> {
    let needle = format!("\"{field}\":\"");
    let start = obj.find(&needle)? + needle.len();
    let rest = &obj[start..];
    let end = rest.find('"')?;
    Some(rest[..end].to_string())
}

fn extract_num_field(obj: &str, field: &str) -> Option<String> {
    let needle = format!("\"{field}\":");
    let start = obj.find(&needle)? + needle.len();
    let rest = &obj[start..];
    let end = rest.find(|c: char| c == ',' || c == '}').unwrap_or(rest.len());
    let val = rest[..end].trim();
    if val == "null" { None } else { Some(val.to_string()) }
}
