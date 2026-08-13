#!/usr/bin/env zsh
# run-music driver — the programmatic handle on the music toolkit.
#
#   driver.sh smoke                    headless: every step, real exit codes
#   driver.sh tui menu T X ""          drive a TUI, print the frame after each key
#   driver.sh tui-start rust           granular control (start / send / screen / stop)
#
# Three drivable surfaces (see SKILL.md):
#   menu    ./music                                zsh, line-based, keys need Enter
#   rust    music-menu/target/debug/music-menu     ratatui, raw keys, NO Enter
#   studio  StudioTUI/target/debug/studio-tui      ratatui, raw keys, NO Enter
#
# zsh, not bash: the toolkit is zsh and this reuses its idioms (${0:A:h}, (f)
# splitting). Under bash the array handling silently misbehaves.

set -u
emulate -L zsh
setopt no_nomatch

REPO="${0:A:h:h:h:h}"          # .../run-music/driver.sh -> up past skills/ and .claude/
cd "$REPO" || { print -u2 "cannot cd to repo root ($REPO)"; exit 2 }

PY="$REPO/.venv/bin/python"
SESSION="${MUSIC_SESSION:-music-drv}"
TMUXBIN="${MUSIC_TMUX:-tmux}"   # seam: point at a bad path to prove the launch guard fires
STATEF="${TMPDIR:-/tmp}/${SESSION}.app"
FIXTURE="${MUSIC_FIXTURE:-Stems/htdemucs_6s/02 Let Em' Know}"

pass=0; fail=0
ok()  { print "  [ok] $1"; (( pass++ )) }
bad() { print "  [x]  $1"; (( fail++ )) }

# ---------------------------------------------------------------- smoke

# Run a command, assert its exit code, show the first line of output.
# want=0 asserts success; want=n asserts a NON-zero exit (a negative control).
check() {
  local label="$1" want="$2"; shift 2
  local out rc
  out=$("$@" 2>&1); rc=$?
  # Explicit array, not ${${(f)out}[1]}: that nested form subscripts the STRING
  # when the split yields one line ("2.5.0" -> "2") and the ARRAY when it yields
  # more, so single-line output silently became one character.
  local -a lines; lines=( ${(f)out} )
  local first="${lines[1]}"
  if [[ "$want" == 0 && $rc -eq 0 ]]; then
    ok "$label — ${first:0:72}"
  elif [[ "$want" == n && $rc -ne 0 ]]; then
    ok "$label — exits $rc as it should — ${first:0:52}"
  else
    bad "$label — exit $rc (wanted ${want/n/non-zero})"
    print -r -- "$out" | sed 's/^/       /' | tail -6
  fi
}

smoke() {
  print "== music smoke =="
  print "repo: $REPO"

  [[ -x "$PY" ]] || { print -u2 "no venv at $PY — create it before running smoke"; exit 2 }
  check "venv numpy"          0 "$PY" -c 'import numpy; print(numpy.__version__)'
  check "core unit tests"     0 zsh tests/test-core.sh
  check "find_track fuzzy"    0 "$PY" Scripts/find_track.py "let em know" --tsv
  check "catalog stats"       0 "$PY" Scripts/catalog.py stats
  check "catalog mix"         0 "$PY" Scripts/catalog.py mix --limit 5

  # chords writes a sidecar; assert the FILE, not just the exit code.
  if [[ -d "$FIXTURE" ]]; then
    rm -f "$FIXTURE/chords.txt"
    check "chords.py on stems" 0 "$PY" Scripts/chords.py "$FIXTURE"
    if [[ -s "$FIXTURE/chords.txt" ]]; then
      ok "chords.txt written — $(wc -l < "$FIXTURE/chords.txt" | tr -d ' ') lines"
    else
      bad "chords.txt missing or empty after a clean exit"
    fi
  else
    bad "fixture missing: $FIXTURE (run a deconstruct first)"
  fi

  # Negative control. Without this the suite has never been observed to fail,
  # and a smoke that cannot fail proves nothing (~/.claude/rules/silent-failure.md).
  check "chords.py rejects a non-stem dir" n "$PY" Scripts/chords.py /tmp

  print ""
  print "$pass passed, $fail failed"
  (( fail == 0 ))
}

# ------------------------------------------------------------------ tui

# app -> launch command. Rust binaries are debug builds; `cargo build` in the
# crate dir refreshes them (music-menu ~10s, StudioTUI ~6s warm).
app_cmd() {
  case "$1" in
    menu)   print -r -- "./music" ;;
    rust)   print -r -- "./music-menu/target/debug/music-menu" ;;
    studio) print -r -- "./StudioTUI/target/debug/studio-tui" ;;
    *) print -u2 "unknown app '$1' — use menu | rust | studio"; return 2 ;;
  esac
}

# Poll until two consecutive captures match. The TUIs redraw asynchronously; a
# fixed sleep either races the redraw or wastes a second on every key.
settle() {
  local prev="" cur="" i
  for i in {1..25}; do
    cur=$("$TMUXBIN" capture-pane -t "$SESSION" -p 2>/dev/null)
    [[ -n "$cur" && "$cur" == "$prev" ]] && { print -r -- "$cur"; return 0 }
    prev="$cur"; sleep 0.2
  done
  print -r -- "$cur"
}

tui_start() {
  local app="${1:-menu}" cmd
  cmd=$(app_cmd "$app") || return 2
  [[ "$app" != menu && ! -x "$cmd" ]] && {
    print -u2 "$cmd not built — run: (cd ${cmd%%/target/*} && cargo build)"; return 2 }
  "$TMUXBIN" has-session -t "$SESSION" 2>/dev/null && "$TMUXBIN" kill-session -t "$SESSION"
  # Gate on the launch. Unchecked, a missing tmux / unwritable TMUX_TMPDIR / a
  # stale session surviving the kill above all still printed "up" and returned 0
  # (print was the last statement), so `tui_start || return` never fired.
  "$TMUXBIN" new-session -d -s "$SESSION" -x 200 -y 50 "cd ${(q)REPO} && $cmd" || {
    print -u2 "tmux new-session failed — cannot start '$app'"; return 2 }
  print -r -- "$app" > "$STATEF"
  settle >/dev/null
  print "$app up (tmux session '$SESSION')"
}

# The zsh menu reads whole lines, so a key only registers with Enter. The
# ratatui apps read raw keypresses, where a stray Enter ACTIVATES the selected
# row — sending it there fires a step instead of navigating.
tui_send() {
  "$TMUXBIN" has-session -t "$SESSION" 2>/dev/null || { print -u2 "no session — run tui-start"; return 2 }
  local app="menu"; [[ -r "$STATEF" ]] && app=$(<"$STATEF")
  if [[ "$app" == menu ]]; then
    "$TMUXBIN" send-keys -t "$SESSION" "$1" Enter
  else
    "$TMUXBIN" send-keys -t "$SESSION" "$1"
  fi
  settle >/dev/null
}

tui_screen() {
  "$TMUXBIN" has-session -t "$SESSION" 2>/dev/null || { print -u2 "no session — run tui-start"; return 2 }
  "$TMUXBIN" capture-pane -t "$SESSION" -p
}

tui_stop() {
  "$TMUXBIN" has-session -t "$SESSION" 2>/dev/null && "$TMUXBIN" kill-session -t "$SESSION"
  rm -f "$STATEF"
  print "tui down"
}

# tui <app> [key...] — start, send each key, print the frame after each, tear down.
tui_run() {
  local app="${1:-menu}"; shift 2>/dev/null || true
  tui_start "$app" || return 2
  # Track loop failures. tui_send/tui_screen print "no session" to stderr, but
  # unchecked their exit codes vanished: tui_run ended on tui_stop (always 0), so
  # an app that panicked mid-run looked exactly like every key landing.
  local rc=0 k
  print "\n--- opening frame ---"; tui_screen || rc=1
  for k in "$@"; do
    tui_send "$k" || rc=1
    print "\n--- after '${k:-<enter>}' ---"; tui_screen || rc=1
  done
  tui_stop
  (( rc == 0 )) || print -u2 "one or more keys/captures failed — the session died mid-run"
  return $rc
}

# ------------------------------------------------------------------ cli

case "${1:-}" in
  smoke)      smoke ;;
  tui)        shift; tui_run "$@" ;;
  tui-start)  tui_start "${2:-menu}" ;;
  tui-send)   tui_send "${2?key required (use '' for a bare Enter)}" ;;
  tui-screen) tui_screen ;;
  tui-stop)   tui_stop ;;
  *)
    print "usage: driver.sh smoke"
    print "       driver.sh tui <menu|rust|studio> [key...]"
    print "       driver.sh tui-start <menu|rust|studio>"
    print "       driver.sh tui-send <key> | tui-screen | tui-stop"
    exit 2 ;;
esac
