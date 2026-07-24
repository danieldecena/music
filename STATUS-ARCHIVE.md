# STATUS archive — music toolkit

Decision-log entries rotated out of `STATUS.md`. Append-only; newest first.
Git holds the full history.

### 2026-07-21
- Decided: build `music-menu/` — a new ratatui menu-launcher for the flip path in
  the external "Ratatui Design" Claude Design system (navy/cream/yellow, JetBrains
  Mono, box-drawing, yellow reversed-video selection). Chosen over restyling
  StudioTUI so its LCD-Green/Phosphor look is untouched. Adapted the design kit's
  `script-menu` template; reused StudioTUI's `worker::run_zsh` pattern (stdin
  nulled, `sh_quote`) so it calls arg-driven `lib/music-core.sh` functions, never
  the interactive `*.sh` wrappers (which read stdin and would hang the TUI).
- Built warning-free (cargo build + clippy clean). Verified in tmux: renders to
  the design, source picker discovers the real library, and running Tempo & key
  streamed `analyze_track`'s live output + status. Note: analyze_track exits 0 but
  prints "analysis failed" on `03 Exchange.m4a` (corrupt mvhd time scale in that
  file) — a pre-existing pipeline/ffmpeg quirk, faithfully surfaced by the TUI,
  not a menu bug.
- Fixed the zsh `music` menu navigation the same session: Download (arm 1) now
  auto-selects the fetched track; arms 1/8 accept a pasted URL (download->select);
  "Need an audio file" now guides; blank Enter redraws. And logic-pro-mcp's
  `_ensure_logic_running` launched `open -a "Logic Pro"` (wrong app on this
  machine) and hung 30s — now launches `LOGIC_APP_NAME` (default "Logic Pro
  Creator Studio", env-overridable) and fails fast. Both committed + pushed.
- CORRECTION to the tmux-verification claim above: it was a false PASS. The
  "analysis failed" line was NOT the Exchange mvhd quirk — it was a path bug that
  broke EVERY source/stem step. `main.rs` took the CLI root arg raw; launched with
  a relative `..` (the README's own `cargo run -- ..`), `find_sources` baked `../`
  into every path while `run_zsh` also set cwd to `..`, so `../Apple Music/x`
  resolved from the wrong dir -> "No such file or directory". The earlier verify
  saw "analysis failed", pattern-matched it to the known mvhd issue, and never read
  the actual error text — the exact "can't tell no-diff from not-shown" trap logged
  on 2026-07-18. Reproduced on `01 Nikes.m4a` (a clean file), not just Exchange.
- Fixed: `let root = root.canonicalize().unwrap_or(root);` in main.rs, so discovery
  and run cwd are both absolute. Re-verified by driving the TUI with `..`:
  `analyze_track` now runs the absolute path and returns `69.1 BPM key C` + ✓ done.
  Also added 14 unit tests for the pure fns (sh_quote real-shell round-trip incl.
  injection, build fns, short_label, display_val) — these don't cover the path/cwd
  seam, which is why running the app caught what the tests couldn't.
- Two UX rough edges found while driving (NOW FIXED, main.rs key routing): in a
  filtered list the first Enter only committed the filter (a second opened the
  step) — Enter in filter mode now calls `start_selected()`, so one Enter runs the
  highlighted step. And Esc from a committed filter used to quit the app — menu-mode
  Esc now clears a non-empty filter first and only quits when there's nothing left
  to back out of. Re-verified in tmux: filter->Enter opens the step; Esc drops
  Steps (2)->Steps (8) with the app still alive, second Esc quits.
- Also unaddressed: the TUI marks a step `✓ done` purely on exit code, so a step
  that self-reports failure while exiting 0 (like analyze_track on a bad file) still
  reads green.

### 2026-07-18
- Decided: freeze a behavioural baseline BEFORE touching analyze_track.py. It
  proved the old detector was degenerate in three independent ways that were
  invisible without it: tempo railed at its 184.6 BPM ceiling on 28/120 rows
  (49/120 sat on just 3 integer lags), key collapsed to "F" on 53/120, and
  boundaries fired every 8s because the minimum-gap filter, not the threshold,
  was doing the work.
- Decided: do NOT commit the tempo octave fix until it is verified by ear. It is
  objectively correct on synthetic signals (140 BPM read as 69.8 before, 140.3
  after) and the sub-lag refinement is a genuine correctness fix -- at ~43
  envelope fps, integer lags cannot represent 140 BPM at all. But against
  published BPM it scored 6/13 both before and after, and the published values
  are one algorithm with the same octave bias. Reasoning that sounds right is
  not evidence.
- Learned: the plan's diagnosis of octave errors as a *scoring* problem was
  incomplete. The mechanism is lag quantization -- an 0.46-frame-per-beat error
  accumulates to a full beat of drift in 30s, which collapses the evidence for
  the FAST candidate while the slow one drifts half as fast. The resolution
  asymmetry itself biases toward halving.
- Learned: `entire contents of front window` returns ZERO elements for Logic
  Pro 12.3 even when frontmost, so logic_dump_ui_hierarchy silently returned "".
  Walk with `every UI element` and recurse through a handler parameter --
  storing element refs in a list and mutating it invalidates them (-10000).
- Learned: "simplify to only the provably-correct part" was itself falsified.
  Sub-lag refinement alone scored exact 3 / octave 5, worse than the original
  argmax (5/2), while refinement plus candidate scoring scored 6/1. The safe-
  looking subset was the worst of three variants -- measuring it before shipping
  it is the only reason that was caught.
- Learned: a verification step that cannot distinguish "no differences" from "I
  was not shown the differences" is worthless. Piping a replay through `tail -60`
  silently dropped every full-mix row (source paths sort before Stems/), and a
  confident drift summary was then built on the survivors. Same silent-failure
  shape as the dump returning "" and deconstruct's sed writing to /dev/null --
  three in one session. Counts now sum to a known total.

### 2026-07-12
- Decided: bundle stem quality as four named profiles (acapella/fast/6stem/hq)
  instead of exposing raw demucs model names. htdemucs_ft excluded — it is
  4-stem only and cannot produce guitar/piano, which is the user's goal; the
  only path to those is htdemucs_6s, cleaned up with --shifts 2 --overlap 0.5
  (the `hq` default). deconstruct kept on `fast` so the quick-prep path stays
  fast-by-default; keeper-track quality lives in Separate.
- Decided: per-stem analysis uses ffmpeg volumedetect (no new Python deps) and
  writes a human-readable analysis.txt beside the stems rather than into the
  catalog — the beside-stems report delivers the "which stems have audio" value
  without fighting the catalog's rebuild-on-scan model.
