# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Run the toolkit: `music` from anywhere (symlinked into `~/Bin`, which is on PATH; the script resolves its own repo via `${0:A:h}`), or `./music` from the repo root — interactive menu (Download / Separate stems / Chop vocals / Split drums / Chop stems / Sort kit / Analyze tempo+key / Deconstruct / Full pipeline / Quit)
- Or run a single step directly: `./download.sh`, `./stems.sh`, `./chop.sh`, `./chop-drums.sh`, `./chop-stems.sh`, `./sort-kit.sh`, `./analyze.sh`, `./deconstruct.sh` — each prompts for input then calls the matching `music-core.sh` function
- Run tests: `zsh tests/test-core.sh` — hand-rolled assertions (no framework) covering `stem_mode_args`, `chop_sensitivity_args`, `drum_split_args`, `find_new_m4a`
- Python steps need the venv: `source .venv/bin/activate` before invoking `Scripts/chop.py` directly. `chop_vocals()` in music-core already does this itself, so `./chop.sh` and pipeline runs don't need manual activation.
- No lint/build config exists in this repo (no ruff config, no package manifest) — don't invent commands for these.

## Architecture

**Core/wrapper split.** `lib/music-core.sh` holds all non-interactive, argument-driven logic. `music`, `download.sh`, `stems.sh`, `chop.sh` are thin interactive shells: they prompt for input, then call a core function. Never duplicate logic into a wrapper — add it to `music-core.sh` so both the standalone scripts and the unified `music` menu stay in sync.

Core functions and what they shell out to:
- `download_url(url, apple_music_out)` — routes by URL: `music.apple.com` → `gamdl` (auth via cookies.txt, extracted from Safari by `get-cookies.py` on first run, automated past its interactive prompt with `expect`); `soundcloud.com` and everything else → `yt-dlp`
- `separate_stems(file, mode, out_dir)` — runs `demucs` inside `.venv`; `mode` is `instrumental` (2-stem), `4stem`, or `6stem` (mapped to CLI args by `stem_mode_args`)
- `chop_vocals(vocals_wav, out_dir, sensitivity)` — activates `.venv` and runs `Scripts/chop.py`, which uses `ffmpeg silencedetect` to find phrase boundaries and slices clips with `ffmpeg -c copy`; `sensitivity` is `tight` or `loose` (mapped to silence/clip-length thresholds by `chop_sensitivity_args`)
- `chop_drums(input, out_dir, density)` — runs `Scripts/slice_drums.py` (venv python; needs numpy) to slice a drum stem into one-shot hits via spectral-flux onset detection; `density` is `tight`/`loose` (mapped by `drum_split_args`). Output: `Samples/One-Shots/<track>/<stem>_NNN.wav`
- `chop_stems(track_folder, out_root, seconds)` — pure-ffmpeg fixed-length chops of every stem in a `Stems/<model>/<track>` folder into `Samples/Chops/<track>/<stem>/<stem>_NNN.wav` (auditioning layout; default 8s)
- `sort_kit(oneshots_folder)` — runs `Scripts/sort_drums.py` to classify drum one-shots into `kick/`, `snare/`, `hat/` subfolders by spectral centroid + band energy (heuristic)
- `analyze_track(file_or_folder)` — runs `Scripts/analyze_track.py` to estimate BPM (onset-autocorrelation) and key (Krumhansl-Schmuckler chroma). Estimates only
- `deconstruct(file, density)` — one-command flip prep chaining the reliable steps: `analyze_track` → `separate_stems` (4stem) → `chop_drums` → `sort_kit` → `chop_stems`. Menu option 8 / `./deconstruct.sh`
- `Scripts/bass_to_midi.py` (not yet wired into a menu step) — monophonic bass→MIDI via autocorrelation pitch detection + a hand-written MIDI writer. Best-effort; single-note lines only

All `Scripts/*.py` except `chop.py` and `catalog.py` (both stdlib-only) require the venv's numpy and are invoked via `.venv/bin/python` directly rather than `source activate`.

**Catalog (`Scripts/catalog.py`, sqlite3 stdlib).** Maintains `catalog.sqlite` (gitignored) — a `tracks` table (source path, artist/album, bpm, key, model, deconstructed_at), an `assets` table (every stem/one-shot/kit/loop/chop/vocal/midi/resynth file), and a `runs` log. `deconstruct()` calls `catalog.py index-track <track> --bpm --key` on completion (parsed from its own `analyze_track` output), so the DB stays current without a separate scan. CLI: `scan` (full rebuild of assets; tracks keep bpm/key), `ready`/`pending`/`recent`/`stats` (with `--json`) power the scheduled `auto-deconstruct-new-tracks` and `ready-to-flip-digest` tasks and can back the Music Studio artifact. Assets are rebuilt every scan; `tracks` rows persist.

**Full-pipeline chaining.** `music` option 4 (download → stems → chop) stamps `$(date +%s)` before downloading, then calls `find_new_m4a(dir, stamp)` to discover which files the download step produced — neither `gamdl` nor `yt-dlp` return paths directly. `find_new_m4a` works around BSD `find` not supporting `-newermt "@epoch"` on macOS by `touch -t`-ing a reference file at the target timestamp and diffing against that.

**Data flow.**
```
Apple Music/ (or SoundCloud/, Downloads/)      [downloads are .m4a]
  → Stems/htdemucs[_6s]/<track>/{vocals,drums,bass,other}.wav
    → Samples/Vocals/<track>/<track>_NNN.wav        (chop_vocals, silence)
    → Samples/One-Shots/<track>/<stem>_NNN.wav       (chop_drums, onsets → sort_kit → kick/snare/hat)
    → Samples/Chops/<track>/<stem>/<stem>_NNN.wav    (chop_stems, fixed length)
```
`Projects/`, `Exports/`, `References/` are Logic Pro workspace directories, mostly gitignored alongside `Stems/`, downloaded source audio, and `cookies.txt`.

**Trust boundary.** `download_url`'s Apple Music branch interpolates `$url`/`$cookies`/`$am_out` into an `expect` heredoc that spawns a shell command. This is safe only because URLs reach it via trusted interactive paste — do not route untrusted or programmatically-sourced URLs through this path without escaping.

**Design docs.** `docs/superpowers/specs/` and `docs/superpowers/plans/` hold the spec-driven-development artifacts this codebase was built from (unified CLI design, folder-structure design, an in-progress Logic Pro MCP design). Check these before large structural changes.
