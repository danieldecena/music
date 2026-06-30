#!/usr/bin/env zsh
# Non-interactive core for the music toolkit. Source, don't execute.

LIB_DIR="${${(%):-%x}:A:h}"
MUSIC_DIR="${LIB_DIR:h}"

stem_mode_args() {
  case "$1" in
    instrumental) print -- "--two-stems=vocals" ;;
    4stem)        print -- "" ;;
    6stem)        print -- "-n htdemucs_6s" ;;
    *)            return 1 ;;
  esac
}

chop_sensitivity_args() {
  case "$1" in
    tight) print -- "--min-silence 0.15 --min-clip 0.3" ;;
    loose) print -- "--min-silence 0.35 --min-clip 0.8" ;;
    *)     return 1 ;;
  esac
}

find_new_m4a() {
  # $1 = directory, $2 = epoch seconds.
  # BSD find (/usr/bin/find on macOS) can't parse -newermt "@epoch", so compare
  # against the mtime of a reference file stamped at the target time instead.
  local ref
  ref=$(mktemp)
  touch -t "$(date -r "$2" '+%Y%m%d%H%M.%S')" "$ref"
  find "$1" -name '*.m4a' -newer "$ref" 2>/dev/null
  rm -f "$ref"
}
