# StudioTUI — Implementation Plan (pass 3: functions + automations)

## Goal
Wire every rendered control to real behavior, fix key-routing bugs, and add automations
(job queue, batch deconstruct, watch mode, catalog badges, pattern save/load, dark theme,
help overlay). Verify by building on macOS and capturing each tab in tmux.

## Brainstorm decisions
- **Bypass interactive wrappers.** `stems.sh`/`chop-drums.sh`/`chop.sh` `read` from stdin —
  spawned from the TUI they hang and steal keystrokes. New `worker::run_zsh(cmd)` runs
  `zsh -c 'source lib/music-core.sh; <fn> args… 2>&1'` with `stdin(null)`. Alternative
  considered: patching every wrapper to accept args — rejected, core functions already
  have clean signatures.
- **Job queue over ad-hoc chaining.** `VecDeque<Job>`; `poll_worker` starts the next job on
  `Done`. Gives Full Pipeline, batch mode, and watch mode one mechanism. Alternative
  (nested callbacks per action) rejected as unmaintainable.
- **Key routing: input-focus → tab handler → global fallback.** Fixes global `c` shadowing
  Logic connect, and Library's dead 1-9 keys (categories move to h/l only; 1-4 stay tabs).
- **Catalog via `catalog.py ready --json`** at startup (blocking `Command::output`, sqlite is
  fast) into `HashMap<track,(bpm,key)>` — no sqlite crate, deps stay at 3.
- **Pattern save/load: plain text** (`Samples/Patterns/<name>.pattern`, `k=v` + 16-char 0/1
  rows) — no serde dep.
- **Kits = subfolders of `Samples/One-Shots`** (sort_kit output layout); kit scopes
  `find_sample_for`.

## Work items
| # | Item | File(s) | Depends on | Parallel | Owner |
|---|------|---------|-----------|----------|-------|
| F1 | Key routing rework (focus → tab → global); `?` help state; `0` theme toggle; `W` watch toggle | app.rs | — | no | main |
| F2 | `run_zsh` + stdin(null) + stderr capture everywhere; shell quoting helper | worker.rs | — | no | main |
| F3 | Job queue (`Job`, `VecDeque`, auto-advance, `a` batch-deconstruct-all, Esc cancels queue) | app.rs | F2 | no | main |
| F4 | Pipeline params live: s/d/g cycle stem-mode/density/chop; t tempo input; [/] stem folder; every action passes params via core fns; Full Pipeline = analyze→stems→chop_vocals queue | app.rs | F2,F3 | no | main |
| F5 | Watch mode: rescan sources every 2 s, auto-queue deconstruct for new files | app.rs, fs.rs | F3 | no | main |
| F6 | Catalog map at startup + `meta_for` helper (BPM·key badges) | app.rs, fs.rs | — | no | main |
| F7 | Sequencer: n name edit, b BPM edit, B bars (1/2/4/8 → --reps), K kit cycle, x clear, S/L pattern save/load; kit-scoped samples | app.rs, fs.rs | F1 | no | main |
| F8 | Library: o reveal-in-Finder, / filter, category via h/l | app.rs | F1 | no | main |
| F9 | `Theme::dark()` (Atom One Dark) + `theme_name()`; dynamic header; help overlay render | theme.rs, ui/mod.rs | F1 | no | main |
| P1 | Pipeline panel redesign: live param chips (accent = focused), queue count, batch hint | ui/pipeline.rs | F1-F6 | YES | subagent |
| P2 | Sequencer panel redesign: live BARS/KIT/NAME fields, edit-focus underline, pattern hints | ui/sequencer.rs | F7 | YES | subagent |
| P3 | Logic panel: replace double-width emoji with 1-cell glyphs, use theme style ctors | ui/logic.rs | F1 | YES | subagent |
| P4 | Library panel: BPM·key badges, filter line, updated hints | ui/library.rs | F6,F8 | YES | subagent |
| V | Build on macOS, tmux-verify all four tabs + help overlay + dark theme, fix, commit | all | P1-P4 | no | main |

## Sequencing
F1→F9 land sequentially in one owner (all touch app.rs). P1-P4 are four distinct render
files read-only over app state → dispatched as parallel subagents in one batch. V last.

## Acceptance criteria
- F1: on Logic tab `c` runs connect; `?` opens/closes help anywhere; inputs capture all chars.
- F2/F4: running Separate Stems never blocks on stdin; console shows demucs output; chosen
  stem mode/density/chop seconds visibly appear in the spawned command line logged.
- F3: Full Pipeline enqueues 3 jobs that run back-to-back; `a` enqueues deconstruct for every
  real source; Esc empties the queue and logs it.
- F5: with watch on, dropping a new audio file under a source dir logs detection and queues
  deconstruct within ~2 s.
- F6/P4: Stems rows whose track exists in catalog show `⟨bpm·key⟩` badge.
- F7/P2: name/bpm editable with underline focus style; bars cycles 1/2/4/8 and export uses
  it as --reps; K cycles kits incl. "any"; S then L round-trips a pattern.
- F8: `o` opens Finder revealing the file; `/`-filter narrows list live.
- F9: `0` swaps light/dark instantly everywhere; header shows the active palette name;
  help overlay lists per-tab + global keys and closes on Esc/?.
- P1-P4: no `Color::Rgb` outside theme.rs; 1-cell glyphs only; hint bars updated to real keys.
- V: `cargo build` clean (no warnings from our code); tmux captures of 4 tabs + overlay look
  aligned; committed.
