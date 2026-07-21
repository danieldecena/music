// steps.rs — the flip-path catalog (what the menu offers) plus the library
// discovery that fills the picker fields. Each Step declares the inputs it needs
// and a `build` fn that turns the collected values into a music-core.sh call.
use std::fs;
use std::path::{Path, PathBuf};

use crate::worker::sh_quote as q;

/// One input a step collects before it can run.
pub enum FieldKind {
    Url,                     // text: paste a track URL
    Source,                  // pick an audio file from the download folders
    Stems,                   // pick a Stems/<model>/<track> folder
    OneShots,                // pick a Samples/One-Shots/<track> folder
    Choice(Vec<&'static str>), // cycle a fixed option set (density / quality)
    Text(&'static str),      // free text with a default (seconds)
}

pub struct Field {
    pub label: &'static str,
    pub kind: FieldKind,
}

pub struct Step {
    pub name: &'static str,
    pub category: &'static str,
    pub desc: &'static str,
    pub fields: Vec<Field>,
    pub build: fn(&[String]) -> String,
    pub favorite: bool,
}

fn f(label: &'static str, kind: FieldKind) -> Field {
    Field { label, kind }
}

// ---- build fns: collected values -> a music-core.sh function call ----
fn b_download(v: &[String]) -> String {
    format!("download_url {} {}", q(&v[0]), q("Apple Music"))
}
fn b_deconstruct(v: &[String]) -> String {
    format!("deconstruct {} {}", q(&v[0]), q(&v[1]))
}
fn b_separate(v: &[String]) -> String {
    format!("separate_stems {} {} {}", q(&v[0]), q(&v[1]), q("Stems"))
}
fn b_analyze(v: &[String]) -> String {
    format!("analyze_track {}", q(&v[0]))
}
fn b_chop_vocals(v: &[String]) -> String {
    format!(
        "chop_vocals {} {} {}",
        q(&format!("{}/vocals.wav", v[0])),
        q("Samples/Vocals"),
        q(&v[1])
    )
}
fn b_chop_drums(v: &[String]) -> String {
    format!(
        "chop_drums {} {} {}",
        q(&format!("{}/drums.wav", v[0])),
        q("Samples/One-Shots"),
        q(&v[1])
    )
}
fn b_sort_kit(v: &[String]) -> String {
    format!("sort_kit {}", q(&v[0]))
}
fn b_chop_stems(v: &[String]) -> String {
    format!("chop_stems {} {} {}", q(&v[0]), q("Samples/Chops"), q(&v[1]))
}

/// The whole flip path, in menu order.
pub fn catalog() -> Vec<Step> {
    vec![
        Step {
            name: "Download",
            category: "Get audio",
            desc: "Fetch a track from Apple Music / SoundCloud / a URL.",
            fields: vec![f("url", FieldKind::Url)],
            build: b_download,
            favorite: false,
        },
        Step {
            name: "Deconstruct",
            category: "Flip path",
            desc: "One-shot flip prep: tempo/key, 4 stems, one-shots, kit, chops.",
            fields: vec![
                f("source track", FieldKind::Source),
                f("drum density", FieldKind::Choice(vec!["loose", "tight"])),
            ],
            build: b_deconstruct,
            favorite: true,
        },
        Step {
            name: "Separate stems",
            category: "Flip path",
            desc: "Split a track into stems with demucs.",
            fields: vec![
                f("source track", FieldKind::Source),
                f("quality", FieldKind::Choice(vec!["fast", "hq", "6stem", "acapella"])),
            ],
            build: b_separate,
            favorite: false,
        },
        Step {
            name: "Tempo & key",
            category: "Flip path",
            desc: "Estimate BPM and key.",
            fields: vec![f("source track", FieldKind::Source)],
            build: b_analyze,
            favorite: false,
        },
        Step {
            name: "Chop vocals",
            category: "Samples",
            desc: "Slice the vocal stem into phrase clips (silence detect).",
            fields: vec![
                f("stem folder", FieldKind::Stems),
                f("sensitivity", FieldKind::Choice(vec!["loose", "tight"])),
            ],
            build: b_chop_vocals,
            favorite: false,
        },
        Step {
            name: "Split drums",
            category: "Samples",
            desc: "Slice the drum stem into one-shot hits (onset detect).",
            fields: vec![
                f("stem folder", FieldKind::Stems),
                f("density", FieldKind::Choice(vec!["loose", "tight"])),
            ],
            build: b_chop_drums,
            favorite: false,
        },
        Step {
            name: "Sort kit",
            category: "Samples",
            desc: "Classify drum one-shots into kick / snare / hat.",
            fields: vec![f("one-shots folder", FieldKind::OneShots)],
            build: b_sort_kit,
            favorite: false,
        },
        Step {
            name: "Chop stems",
            category: "Samples",
            desc: "Fixed-length snippets of every stem for auditioning.",
            fields: vec![
                f("stem folder", FieldKind::Stems),
                f("seconds", FieldKind::Text("8")),
            ],
            build: b_chop_stems,
            favorite: false,
        },
    ]
}

// ---- library discovery for the pickers ----

const AUDIO_EXTS: [&str; 4] = ["m4a", "mp3", "wav", "flac"];

/// Audio files under the download folders, for the Source picker.
pub fn find_sources(root: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for sub in ["Apple Music", "SoundCloud", "Downloads"] {
        collect_audio(&root.join(sub), 0, &mut out);
    }
    out.sort();
    out
}

fn collect_audio(dir: &Path, depth: usize, out: &mut Vec<PathBuf>) {
    if depth > 4 || out.len() >= 500 {
        return;
    }
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect_audio(&path, depth + 1, out);
        } else if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
            if AUDIO_EXTS.contains(&ext.to_lowercase().as_str()) {
                out.push(path);
            }
        }
    }
}

/// Existing Stems/<model>/<track> folders, for the Stems picker.
pub fn find_stem_dirs(root: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for model in ["htdemucs", "htdemucs_6s"] {
        subdirs(&root.join("Stems").join(model), &mut out);
    }
    out.sort();
    out
}

/// Existing Samples/One-Shots/<track> folders, for the Sort-kit picker.
pub fn find_oneshots(root: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    subdirs(&root.join("Samples").join("One-Shots"), &mut out);
    out.sort();
    out
}

fn subdirs(base: &Path, out: &mut Vec<PathBuf>) {
    if let Ok(entries) = fs::read_dir(base) {
        for entry in entries.flatten() {
            if entry.path().is_dir() {
                out.push(entry.path());
            }
        }
    }
}

/// A short two-component label for a discovered path (`<parent>/<name>`).
pub fn short_label(path: &Path) -> String {
    let name = path.file_name().map(|s| s.to_string_lossy().to_string());
    let parent = path
        .parent()
        .and_then(|p| p.file_name())
        .map(|s| s.to_string_lossy().to_string());
    match (parent, name) {
        (Some(p), Some(n)) => format!("{p}/{n}"),
        (_, Some(n)) => n,
        _ => path.to_string_lossy().to_string(),
    }
}
