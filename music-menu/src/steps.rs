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

#[cfg(test)]
mod tests {
    use super::{catalog, short_label};
    use std::path::Path;

    /// Look up a step's `build` fn by menu name.
    fn build_for(name: &str) -> fn(&[String]) -> String {
        catalog()
            .into_iter()
            .find(|s| s.name == name)
            .unwrap_or_else(|| panic!("no step named {name}"))
            .build
    }

    fn vals(xs: &[&str]) -> Vec<String> {
        xs.iter().map(|s| s.to_string()).collect()
    }

    /// Run a built command line through zsh with every core function stubbed to
    /// print each argument on its own line, so we recover the exact argv the
    /// shell parsed. Proves the build fn + sh_quote hand core the right words.
    fn argv_through_shell(cmdline: &str) -> Vec<String> {
        let prelude = "for _n in download_url deconstruct separate_stems \
             analyze_track chop_vocals chop_drums chop_stems sort_kit; do \
             eval \"$_n(){ for _a in \\\"\\$@\\\"; do printf '%s\\n' \\\"\\$_a\\\"; done; }\"; \
             done; ";
        let out = std::process::Command::new("zsh")
            .arg("-c")
            .arg(format!("{prelude}{cmdline}"))
            .output()
            .expect("spawn zsh");
        assert!(out.status.success(), "zsh failed for: {cmdline}");
        String::from_utf8(out.stdout)
            .expect("utf8")
            .lines()
            .map(|s| s.to_string())
            .collect()
    }

    #[test]
    fn download_builds_the_documented_command() {
        assert_eq!(
            build_for("Download")(&vals(&["https://x/y"])),
            "download_url 'https://x/y' 'Apple Music'"
        );
    }

    #[test]
    fn deconstruct_passes_source_and_density() {
        assert_eq!(
            build_for("Deconstruct")(&vals(&["track.m4a", "tight"])),
            "deconstruct 'track.m4a' 'tight'"
        );
    }

    #[test]
    fn separate_appends_the_stems_output_dir() {
        assert_eq!(
            build_for("Separate stems")(&vals(&["track.m4a", "hq"])),
            "separate_stems 'track.m4a' 'hq' 'Stems'"
        );
    }

    #[test]
    fn chop_vocals_appends_vocals_wav_to_the_stem_dir() {
        let argv = argv_through_shell(&build_for("Chop vocals")(&vals(&[
            "Stems/htdemucs/Song", "loose",
        ])));
        assert_eq!(
            argv,
            vec!["Stems/htdemucs/Song/vocals.wav", "Samples/Vocals", "loose"]
        );
    }

    #[test]
    fn chop_drums_appends_drums_wav_to_the_stem_dir() {
        let argv = argv_through_shell(&build_for("Split drums")(&vals(&[
            "Stems/htdemucs/Song", "tight",
        ])));
        assert_eq!(
            argv,
            vec!["Stems/htdemucs/Song/drums.wav", "Samples/One-Shots", "tight"]
        );
    }

    #[test]
    fn a_source_with_spaces_stays_one_argument() {
        // The real library has paths like "Apple Music/03 Exchange.m4a".
        let argv = argv_through_shell(&build_for("Tempo & key")(&vals(&[
            "Apple Music/03 Exchange.m4a",
        ])));
        assert_eq!(argv, vec!["Apple Music/03 Exchange.m4a"]);
    }

    #[test]
    fn a_malicious_source_reaches_core_as_one_inert_literal() {
        // If quoting leaked, the substitution would run and argv would differ.
        let evil = "$(touch /tmp/music_menu_pwned); rm -rf ~";
        let argv = argv_through_shell(&build_for("Tempo & key")(&vals(&[evil])));
        assert_eq!(argv, vec![evil]);
        assert!(
            !Path::new("/tmp/music_menu_pwned").exists(),
            "command substitution executed — quoting leaked"
        );
    }

    #[test]
    fn short_label_keeps_the_last_two_components() {
        assert_eq!(short_label(Path::new("/a/b/Stems/htdemucs/Song")), "htdemucs/Song");
        assert_eq!(short_label(Path::new("Apple Music/track.m4a")), "Apple Music/track.m4a");
    }

    #[test]
    fn short_label_bare_name_has_no_parent_component() {
        assert_eq!(short_label(Path::new("track.m4a")), "track.m4a");
    }
}
