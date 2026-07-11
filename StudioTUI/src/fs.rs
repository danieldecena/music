use std::path::{Path, PathBuf};

pub const AUDIO_EXTS: &[&str] = &["wav","aif","aiff","mp3","m4a","flac","mid","midi"];
pub const AUDIO_EXTS_NO_MIDI: &[&str] = &["wav","aif","aiff","mp3","m4a","flac"];

fn is_ext(p: &Path, exts: &[&str]) -> bool {
    p.extension()
        .and_then(|e| e.to_str())
        .map(|e| exts.contains(&e.to_lowercase().as_str()))
        .unwrap_or(false)
}

fn skip_dir(name: &str) -> bool {
    matches!(name, ".venv"|"Samples"|"Stems"|".git"|"__pycache__"|"soundfonts"|"node_modules"|"target"|".DS_Store")
}

/// Recursively collect audio files under dirs, returning relative paths.
pub fn scan_audio(root: &Path, dirs: &[PathBuf]) -> Vec<String> {
    let mut out = Vec::new();
    for dir in dirs {
        if !dir.exists() { continue; }
        collect_audio(root, dir, &mut out);
    }
    out.sort();
    out
}

fn collect_audio(root: &Path, dir: &Path, out: &mut Vec<String>) {
    let Ok(entries) = std::fs::read_dir(dir) else { return };
    let mut entries: Vec<_> = entries.flatten().collect();
    entries.sort_by_key(|e| e.file_name());
    for e in entries {
        let p = e.path();
        if p.is_dir() {
            collect_audio(root, &p, out);
        } else if is_ext(&p, AUDIO_EXTS) {
            if let Ok(rel) = p.strip_prefix(root) {
                out.push(rel.to_string_lossy().into_owned());
            }
        }
    }
}

pub fn source_tracks(root: &Path) -> Vec<String> {
    // Downloaded tracks live under Apple Music/<artist>/<album>/…, SoundCloud/,
    // and Downloads/ — scan those recursively (not just the repo root).
    let mut out = Vec::new();
    for dir in ["Apple Music", "SoundCloud", "Downloads"] {
        let d = root.join(dir);
        if d.exists() {
            collect_source_audio(root, &d, &mut out);
        }
    }
    out.sort();
    if out.is_empty() { out.push("— no source files —".into()); }
    out
}

fn collect_source_audio(root: &Path, dir: &Path, out: &mut Vec<String>) {
    let Ok(entries) = std::fs::read_dir(dir) else { return };
    for e in entries.flatten() {
        let p = e.path();
        if p.is_dir() {
            collect_source_audio(root, &p, out);
        } else if is_ext(&p, AUDIO_EXTS_NO_MIDI) {
            if let Ok(rel) = p.strip_prefix(root) {
                out.push(rel.to_string_lossy().into_owned());
            }
        }
    }
}

pub fn stem_folders(root: &Path) -> Vec<String> {
    let stems_root = root.join("Stems");
    let mut out = Vec::new();
    let Ok(models) = std::fs::read_dir(&stems_root) else {
        return vec!["— no stems yet —".into()];
    };
    let mut models: Vec<_> = models.flatten().collect();
    models.sort_by_key(|e| e.file_name());
    for model in models {
        let Ok(tracks) = std::fs::read_dir(model.path()) else { continue };
        let mut tracks: Vec<_> = tracks.flatten().collect();
        tracks.sort_by_key(|e| e.file_name());
        for track in tracks {
            let tp = track.path();
            if tp.is_dir() {
                let has_wav = std::fs::read_dir(&tp)
                    .map(|rd| rd.flatten().any(|e| is_ext(&e.path(), &["wav"])))
                    .unwrap_or(false);
                if has_wav {
                    if let Ok(rel) = tp.strip_prefix(root) {
                        out.push(rel.to_string_lossy().into_owned());
                    }
                }
            }
        }
    }
    if out.is_empty() { out.push("— no stems yet —".into()); }
    out
}

/// Track folders under Samples/One-Shots — each is a "kit" for the sequencer
/// (sort_kit populates kick/snare/hat inside them).
pub fn kit_folders(root: &Path) -> Vec<String> {
    let dir = root.join("Samples").join("One-Shots");
    let mut out = Vec::new();
    if let Ok(entries) = std::fs::read_dir(&dir) {
        let mut entries: Vec<_> = entries.flatten().collect();
        entries.sort_by_key(|e| e.file_name());
        for e in entries {
            if e.path().is_dir() {
                out.push(e.file_name().to_string_lossy().into_owned());
            }
        }
    }
    out
}

/// Best-effort: find a one-shot sample under Samples/One-Shots whose path
/// (directory or filename, e.g. `sort_kit`'s kick/snare/hat subfolders)
/// contains `name` (case-insensitive). `kit` (a One-Shots subfolder name)
/// scopes the search to that track's kit; None searches everything. Rows
/// with no matching category (e.g. Openhat/Clap/808 — sort_kit only
/// classifies kick/snare/hat) legitimately return None.
pub fn find_sample_for(root: &Path, name: &str, kit: Option<&str>) -> Option<PathBuf> {
    let base = root.join("Samples").join("One-Shots");
    let dir = match kit {
        Some(k) => base.join(k),
        None => base,
    };
    let needle = name.to_lowercase();
    fn walk(dir: &Path, needle: &str, out: &mut Option<PathBuf>) {
        if out.is_some() { return; }
        let Ok(entries) = std::fs::read_dir(dir) else { return };
        for e in entries.flatten() {
            if out.is_some() { return; }
            let p = e.path();
            if p.is_dir() {
                walk(&p, needle, out);
            } else if is_ext(&p, &["wav"]) {
                if p.to_string_lossy().to_lowercase().contains(needle) {
                    *out = Some(p);
                }
            }
        }
    }
    let mut out = None;
    walk(&dir, &needle, &mut out);
    out
}

pub fn lib_dirs(root: &Path, category: &str) -> Vec<PathBuf> {
    let samples = root.join("Samples");
    match category {
        "stems"    => vec![root.join("Stems")],
        "oneshots" => vec![samples.join("One-Shots")],
        "vocals"   => vec![samples.join("Vocals")],
        "chops"    => vec![samples.join("Chops")],
        "loops"    => vec![samples.join("Loops")],
        "kits"     => vec![samples.join("Kits")],
        "midi"     => vec![samples.join("MIDI")],
        "resynth"  => vec![samples.join("Resynth")],
        "mangled"  => vec![samples.join("Mangled")],
        _          => vec![],
    }
}
