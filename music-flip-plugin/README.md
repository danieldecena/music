# music-flip

Sample-flip studio for Claude — download tracks, split stems, chop one-shots, sort drum kits, sequence beats, and drive Logic Pro Creator Studio. Wraps the toolkit at `~/Developer/music`.

## What's inside

- **MCP server** — `logic-pro` (23 Logic Pro tools: transport, tracks, tempo/key, bounce/export, new-project-with-stems). Declared in `.claude-plugin/plugin.json`.
- **Skill** — `flip-track`: the full pipeline reference (download → deconstruct → stems/one-shots/kit/chops → Logic session → beat export).
- **Commands** — `/flip <url-or-file>` (end-to-end) and `/deconstruct <file>` (existing file).
- **Artifact** — `artifacts/music-studio.html`: the visual Music Studio control panel + library browser + step sequencer + Logic panel.

## Requirements

- The music workspace and scripts at `/Users/home/Developer/music` (music-core.sh, Scripts/, .venv with demucs/numpy, gamdl/yt-dlp/ffmpeg on PATH).
- A terminal backend (Desktop Commander preferred) for running steps.
- Logic Pro Creator Studio open with Accessibility + Automation granted for the Logic tools (best-effort UI scripting).

## Install (Claude Code)

```
/plugin marketplace add /Users/home/Developer/music/music-flip-plugin
/plugin install music-flip@daniel-music
```

Restart so the `logic-pro` MCP server loads. In Cowork, the server is also registered in `claude_desktop_config.json`.

## Notes

Paths are pinned to Daniel's machine (this is a personal plugin, not a portable distribution). To relocate, update the paths in `.claude-plugin/plugin.json` and the skill.
