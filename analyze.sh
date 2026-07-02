#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Tempo & Key Analyzer"
echo "--------------------"
echo "Drag an audio file or a folder:"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -e "$INPUT" ]] && { echo "Invalid path. Exiting."; exit 1; }

analyze_track "$INPUT"
