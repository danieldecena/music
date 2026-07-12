#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Build Logic Project"
echo "--------------------"
if [[ -n "${1:-}" ]]; then
  INPUT="$1"
else
  echo "Drag a Stems track folder (with drums/bass/other/vocals.wav):"
  read "INPUT?> "
fi
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -d "$INPUT" ]] && { echo "Need a Stems track folder. Exiting."; exit 1; }

TEMPO="${2:-}"
KEY="${3:-}"

echo "Analyzing for tempo/key..."
analyze_track "$INPUT"
build_logic_project "$INPUT" "$TEMPO" "$KEY"
