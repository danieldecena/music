# music-menu

A [Ratatui](https://ratatui.rs) terminal menu for the music flip toolkit, in the
**Ratatui Design** visual language (flat navy surfaces, cream/yellow accents,
box-drawing borders, `> ` reversed-video selection). A searchable list of the
flip-path steps on the left; the selected step's inputs, command, run status and
**live streaming output** on the right.

It is the graphical twin of the interactive `./music` menu — but instead of
running the interactive `*.sh` wrappers (which read stdin and would hang a TUI),
it collects each step's inputs in the UI and calls the argument-driven
`lib/music-core.sh` functions directly, streaming their output.

## Run it

```sh
cd music-menu
cargo run -- ..                 # operate on the parent music repo
cargo run -- ~/Developer/music  # or point it at any music checkout
```

The directory you pass must be a music checkout containing `lib/music-core.sh`;
that shell library resolves its own `MUSIC_DIR`, so paths just work. Requires a
Rust toolchain, `zsh`, and the pipeline's own deps (`demucs`, `ffmpeg`,
`gamdl`/`yt-dlp`, the `.venv`) for the steps that use them.

## Flow

1. `↑↓`/`j k` move; `/` searches; `f` pins a step to ★ Favorites.
2. `↵` on a step collects its inputs one field at a time:
   - **text** (URL, seconds) — type it, `↵` commits.
   - **choice** (density, quality) — `↑↓` cycles, `↵` commits.
   - **picker** (source track, stem folder, one-shots) — a discovered list of
     the real files under `Apple Music/` · `SoundCloud/` · `Downloads/`,
     `Stems/` and `Samples/One-Shots/`; `↑↓` then `↵`.
3. After the last field it runs `source lib/music-core.sh; <fn …>` and streams
   stdout+stderr into the Output panel, ending with `✓ done` / `✗ failed` and a
   duration.

`t` toggles the dark (brand navy) / light (warm paper) theme. `Esc` cancels an
input; `q` quits.

## Steps

| Step | core call |
|------|-----------|
| Download | `download_url <url> "Apple Music"` |
| Deconstruct | `deconstruct <src> <density>` |
| Separate stems | `separate_stems <src> <quality> Stems` |
| Tempo & key | `analyze_track <src>` |
| Chop vocals | `chop_vocals <stemdir>/vocals.wav Samples/Vocals <sens>` |
| Split drums | `chop_drums <stemdir>/drums.wav Samples/One-Shots <density>` |
| Sort kit | `sort_kit <oneshots-folder>` |
| Chop stems | `chop_stems <stemdir> Samples/Chops <seconds>` |

## Layout

- `src/main.rs` — terminal init + poll/tick event loop, key routing (menu / filter / input)
- `src/app.rs` — state: filter, selection, input-collection state machine, run lifecycle
- `src/steps.rs` — the flip-path catalog + library discovery for the pickers
- `src/worker.rs` — spawn `zsh -c`, stdin nulled, stream merged output over a channel
- `src/theme.rs` — the Ratatui Design dark / light `Theme`
- `src/ui.rs` — header, step list, details, live output, input forms, footer

Design system: the "Ratatui Design" Claude Design project (SKILL.md golden rules —
the terminal is the canvas; icons are Unicode glyphs, never emoji; selection is
reversed video). Adapted from that kit's `script-menu` template.
