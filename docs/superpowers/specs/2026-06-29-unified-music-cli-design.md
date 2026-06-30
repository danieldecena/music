# Unified Music CLI Design

**Date:** 2026-06-29
**Project:** `~/Developer/music`
**Depends on:** existing `download.sh`, `stems.sh`, `chop.sh`, `Scripts/chop.py`

## Goal

One interactive entry point — `music` — that wraps downloading, stem separation, and vocal chopping, and can chain all three in a single end-to-end pipeline. Replaces the habit of running three separate drag-and-drop scripts.

## Architecture — core + menu

Split each script's logic into a non-interactive core function. The menu does all prompting and calls the cores; the standalone wrappers also call the cores, so no logic is duplicated.

```text
music/
  music                  ← NEW: interactive menu, the single entry point. All prompting lives here.
  lib/
    music-core.sh        ← NEW: non-interactive functions, no prompts, each echoes its output path(s)
  download.sh            ← slimmed to source lib + keep its prompt (standalone still works)
  stems.sh               ← slimmed likewise
  chop.sh                ← slimmed likewise
  Scripts/chop.py        ← unchanged (logic core for chopping)
```

## Core functions (`lib/music-core.sh`)

All non-interactive. Each takes explicit arguments and echoes its primary output path so callers can chain.

- `download_url <url> <output_dir>` → runs the gamdl/yt-dlp logic from `download.sh`; echoes the output directory that received files.
- `separate_stems <file> <mode> <out_dir>` → runs `demucs` with the mode's args; echoes the produced `vocals.wav` path. Modes: `instrumental` (`--two-stems=vocals`), `4stem` (default), `6stem` (`-n htdemucs_6s`).
- `chop_vocals <vocals_wav> <out_dir> <sensitivity>` → calls `Scripts/chop.py` with the sensitivity's `--min-silence`/`--min-clip`; echoes the clip count. Sensitivity: `tight` / `loose`.

## Menu (`music`)

Run bare, shows:

```text
Music Toolkit
-------------
1) Download
2) Separate stems
3) Chop vocals
4) Full pipeline (download → stems → chop)
5) Quit
```

Options 1–3 prompt for their single input (URL or file/folder, plus mode/sensitivity where relevant) and call the matching core.

## Full pipeline (option 4) — timestamp handoff

gamdl downloads a whole album to a path not fully known in advance, so the pipeline detects newly-created files by modification time:

1. Snapshot the start time: `STAMP=$(date +%s)`.
2. `download_url <url> "Apple Music"`.
3. `find "Apple Music" -name '*.m4a' -newermt "@$STAMP"` → the freshly downloaded tracks.
4. For each new file → `separate_stems <file> instrumental Stems` → `vocals.wav`.
5. Each `vocals.wav` → `chop_vocals <vocals.wav> Samples/Vocals loose` → clips in `Samples/Vocals/<track>/`.

Pipeline uses sensible defaults (instrumental split, loose chop) to stay non-interactive once started; a single prompt up front confirms the mode.

## Data flow

```text
URL ──download_url──▶ Apple Music/<artist>/<album>/*.m4a
                          │ (find -newermt)
                          ▼
                    separate_stems ──▶ Stems/htdemucs/<track>/vocals.wav
                          │
                          ▼
                     chop_vocals ──▶ Samples/Vocals/<track>/<track>_NNN.wav
```

## Error handling

- Download yields zero new `.m4a` → print "nothing downloaded", abort pipeline.
- A track produces no `vocals.wav` → warn, skip that track's chop, continue to the next.
- Chop finds no clips → existing "No clips found" message from `chop.py`.
- Invalid menu choice → reprint menu.

## Testing

- Core functions wrap external tools (gamdl / demucs / ffmpeg); verified by a manual smoke run: pipeline one short track end-to-end and confirm clips land in `Samples/Vocals/`.
- The unit-testable logic (`compute_segments` in `chop.py`) is covered by the separate plan `2026-06-29-chop-hardening.md`. This CLI design adds no new pure logic that needs unit tests.

## Out of scope (YAGNI)

- Subcommand interface (`music download <url>`) — interactive menu only for now.
- BPM/key auto-tagging of clips.
- Progress bars / parallel stem separation.
