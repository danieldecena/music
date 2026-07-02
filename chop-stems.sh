#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Stem Snippet Chopper"
echo "--------------------"
echo "Drag a Stems track folder (or a single stem .wav):"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -e "$INPUT" ]] && { echo "Invalid path. Exiting."; exit 1; }

read "SECS?Snippet length in seconds [8]> "
[[ -z "$SECS" ]] && SECS=8

chop_stems "$INPUT" "$SCRIPT_DIR/Samples/Chops" "$SECS"
