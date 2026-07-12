---
description: One-command flip — URL or file → stems, one-shots, kit, chops (+ optional Logic session)
argument-hint: <url-or-file-path> [tight|loose]
---

Flip `$1` end to end using the music toolkit at `/Users/home/Developer/music`, via the Desktop Commander terminal backend.

1. If `$1` looks like a URL, download it: `cd '/Users/home/Developer/music' && source lib/music-core.sh && download_url '$1' 'Apple Music'`, then find the newest resulting audio file. Otherwise treat `$1` as the file path.
2. Deconstruct it (density = `$2` or `loose`): `cd '/Users/home/Developer/music' && source lib/music-core.sh && deconstruct '<file>' ${2:-loose}`. Wait for `✓ Deconstruct complete`.
3. Report BPM/key and the output locations (Stems, One-Shots + kit, Chops, Vocals).
4. Ask if Daniel wants a Logic session built from the stems (`build_logic_project 'Stems/htdemucs/<track>'`).

Follow the `flip-track` skill for details and the full function reference.
