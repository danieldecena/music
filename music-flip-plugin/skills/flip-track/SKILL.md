---
name: flip-track
description: Turn a song into flippable material and a Logic session. Use whenever Daniel wants to sample, flip, or chop a track — "flip this", "deconstruct <song>", "make a beat from <url>", "give me stems/one-shots/a kit from X", or "open these stems in Logic". Runs the music-core.sh pipeline (download → stems → one-shots → sort kit → chops → vocal chops) on the Mac and can build a Logic Pro project from the result.
---

# Flip a track

Drives the toolkit at `/Users/home/Developer/music` (the `MUSIC` dir below). Run everything through a terminal backend — **Desktop Commander** (`start_process`) is the reliable choice; iTerm2 works too. Every step is a shell command of the form:

```
cd '<MUSIC>' && source lib/music-core.sh && <function> <args...>
```

`MUSIC = /Users/home/Developer/music`

## The fast path (recommended)

1. **Download** (if given a URL): `download_url '<url>' 'Apple Music'` — Apple Music via gamdl, SoundCloud/other via yt-dlp. Files land under `Apple Music/<Artist>/<Album>/`.
2. **Deconstruct**: `deconstruct '<file>' loose` — one command that chains analyze (BPM+key) → 4-stem split → drum one-shots → sort kit (kick/snare/hat) → 8s stem snippets → vocal chops. Everything lands under `Samples/`.
3. Report the estimated BPM/key and where the outputs are (`Stems/htdemucs/<track>`, `Samples/One-Shots/<track>`, `Samples/Chops/<track>`, `Samples/Vocals/<track>`).

Deconstruct is CPU-heavy (demucs ≈ 1-2 min/track). Poll the process until it prints `✓ Deconstruct complete`.

## Manual path (control each step)

- `analyze_track '<file-or-folder>'` — estimate BPM + key (set your Logic project to these).
- `separate_stems '<file>' <mode> Stems` — mode = `instrumental` (2-stem) | `4stem` | `6stem`.
- `chop_vocals '<Stems/model/track>/vocals.wav' Samples/Vocals <tight|loose>` — phrase-length vocal clips.
- `chop_drums '<Stems/model/track>/drums.wav' Samples/One-Shots <tight|loose>` — one-shot hits.
- `sort_kit 'Samples/One-Shots/<track>'` — classify hits into kick/snare/hat.
- `chop_stems '<Stems/model/track>' Samples/Chops <seconds>` — fixed-length stem snippets (default 8).
- `bass_to_midi '<Stems/model/track>/bass.wav' 'Samples/MIDI/<track>_bass.mid' <tempo>` — monophonic bass → MIDI.
- `resynth_instrument '<mono.wav>' 'Samples/Resynth/<name>' '<instrument>' <tempo>` — re-voice a mono line (35 GM instruments; needs a soundfont in `soundfonts/`).

Density/sensitivity: `loose` = more, longer clips; `tight` = fewer, cleaner. Start loose.

## Build a Logic session

- `build_logic_project '<Stems/model/track>' [tempo] [key]` (a `music-core` function) — or the MCP tool **`logic_new_project_with_stems`** — loads the stems as audio tracks; if a `bass.wav` is present it's transcribed and imported as a MIDI instrument track too.
- Transport / tracks via the **logic-pro MCP**: `logic_play/stop/record`, `logic_get_tempo/key/bar_position`, `logic_list_tracks`, `logic_select_track(name|index)`, `logic_mute_track(track=)`, `logic_solo_track(track=)`, `logic_save`, `logic_bounce`, `logic_export`.
- Logic UI-scripting is best-effort — Logic must be open with Accessibility + Automation granted. If a selector misfires, re-derive it with `entire contents of front window`.

## Step sequencer / beat export (no Logic needed)

`Scripts/beat_export.py` renders a kick/snare/hat/openhat/clap/808 pattern to MIDI or a WAV loop built from a sorted kit:

```
cd '<MUSIC>' && .venv/bin/python Scripts/beat_export.py wav 'Samples/Loops/<name>.wav' \
  --bpm 90 --steps 16 --reps 2 \
  --row 'kick:36:1000100010001000:<abs path to a kick one-shot>' \
  --row 'snare:38:0000100000001000:<abs path to a snare>' \
  --row 'hat:42:1010101010101010:<abs path to a hat>'
```

Use `midi` mode (no `--kit`/sample paths needed) for a GM drum MIDI file. The Music Studio artifact (`artifacts/music-studio.html`) is a visual front-end for all of this.

## Notes
- Never route untrusted URLs through `download_url`'s Apple Music branch (it interpolates into an `expect` heredoc).
- If the terminal backend is unreachable, say so and stop — don't fabricate results.
