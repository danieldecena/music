#!/usr/bin/env zsh
# Smoke test for Tools/mu-analyze. Covers the argument surface and exit codes
# only -- the analysis itself needs real audio and a minute of wall time, so it
# is exercised by the Phase 1 batch rather than here.
set -u
ROOT="${0:A:h}/.."
BIN="$ROOT/Tools/mu-analyze"
fails=0

check() {
  if [ "$1" = 0 ]; then print "  ok   $2"
  else print "  FAIL $2"; fails=$((fails+1)); fi
}

[[ -x "$BIN" ]]
check $? "binary exists and is executable"

"$BIN" >/dev/null 2>&1
[[ $? -eq 2 ]]
check $? "no args exits 2"

"$BIN" /nonexistent-track.m4a >/dev/null 2>&1
[[ $? -eq 1 ]]
check $? "missing file exits 1"

print "mu-analyze: $((3 - fails))/3 passed"
exit $(( fails > 0 ))
