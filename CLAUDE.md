# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Run the toolkit: `music.sh` or `music` from anywhere (both are `~/Bin` symlinks to the repo's `music`; `~/Bin` is on PATH and the script resolves its own repo via `${0:A:h}`), or `./music` from the repo root — interactive menu (Download / Separate stems / Chop vocals / Split drums / Chop stems / Sort kit / Analyze tempo+key / Deconstruct / Full pipeline / Quit)
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
- `click_compare(file_or_folder, [--bpm B] [--label L])` — runs `Scripts/click_compare.py` (venv python, numpy; reuses `analyze_track`'s decode/tempo). Auditions the tempo estimate against its half/double/1.5x/0.667x octaves (plus any `--label`) by laying a metronome click over a short excerpt (drums stem if a Stems folder) and playing each via `afplay`, so the ear settles which BPM locks. Interactive; `--render-only DIR` writes the mixes non-interactively. Menu `T` in Tools / `./click-compare.sh`
- `find_tracks(query)` / `pick_track(query)` / `resolve_target(raw)` — type-a-title track input. `Scripts/find_track.py` (stdlib difflib) fuzzy-ranks Stems folders + source audio (Apple Music/SoundCloud/Downloads) against a typed title (typos tolerated), collapsing a track that is both source and stem to one stem row and trimming the weak tail. `resolve_target` passes an existing path through untouched and only searches non-paths; `pick_track` auto-resolves a lone match, else shows a numbered picker (Enter = best, q = cancel). Used by `click-compare.sh` and the menu's generic-file / no-current-track stems prompts so any track-level prompt accepts a title. Not on the bass-stem or One-Shots-folder prompts (those want a specific sub-asset). `find_track.py`: CLI `find_track.py "<query>" [--tsv|--json] [--limit N]`
- `mix_report(seed, [--lyrics] [--preview] [--limit N] [--tempo-tol F] [--json])` — runs `catalog.py mix --seed`, which pivots on one track instead of dumping every library pair. Prints a verdict line, a why-line that leads with the tempo fact and hedges the key claim (key detection is the weak half at 2/13 exact), shared lyric words ranked rarest-first, and near misses explaining what the tempo ruled out. `--preview` renders the top pair as a tempo-matched crossfade via `Scripts/mix_preview.py` and plays it with `afplay`. Rendering lives in `Scripts/mix_report.py` (pure; text + JSON from one dict). Menu `Z` in Tools / `./mix-report.sh`
- `deconstruct(file, density)` — one-command flip prep chaining the reliable steps: `analyze_track` → `separate_stems` (4stem) → `chop_drums` → `sort_kit` → `chop_stems`. Menu option 8 / `./deconstruct.sh`
- `Scripts/bass_to_midi.py` (not yet wired into a menu step) — monophonic bass→MIDI via autocorrelation pitch detection + a hand-written MIDI writer. Best-effort; single-note lines only
- `Scripts/key_oracle.py` (dev tool, no menu step) — grades `detect_key` against an **independent** key source so accuracy can be measured without circularity: every label in `tests/fixtures-analysis.tsv` is Echo Nest-derived, so scoring against them is self-referential. `fetch` sweeps Ultimate Guitar's search (shells out to `curl` — `urllib` gets a 404 there), reads the `tonality_name` each tab states, weights by votes (+1 so a 0-vote licensed `Official` tab still counts), matches artist AND title (a cover band's tab can out-vote the real one), caches to `Samples/KeyLabels/` (gitignored), and writes `tests/fixtures-keys-ug.tsv`. `score` runs the **live** `detect_key` on each track's audio (via `_analyzer_key`, a lazy `analyze_track` import) and classifies it via the mix report's Camelot logic (`harmonic_mix.key_compatible`), so enharmonics count as exact and a major/minor flip reads as `relative`. Result (live analyzer vs UG, 10/13 rows carry a UG label): **1/10 exact, 3/10 share the pitch-class set — the dominant error is wrong pitch class, not mode.** NOTE: `score` grades `detect_key` output, NOT fixtures column 3 — column 3 is the Echo Nest ground truth this oracle exists to bypass. An earlier version graded column 3 and so measured Echo-Nest-vs-UG (reporting a misleading 4/10 exact / mode-flip story); that was a measurement bug, fixed 2026-07-24

All `Scripts/*.py` except `chop.py`, `catalog.py`, `find_track.py`, `lyrics.py`, `mix_report.py`, and `mix_preview.py` (stdlib-only) require the venv's numpy and are invoked via `.venv/bin/python` directly rather than `source activate`. `key_oracle.py`'s label helpers are stdlib-only, but `score`/`fetch` now lazily import `analyze_track` (numpy) to grade the live analyzer, so run them from the venv.

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
