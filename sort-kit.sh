#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Drum Kit Sorter"
echo "---------------"
echo "Drag a One-Shots folder of drum hits to classify into kick/snare/hat:"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -d "$INPUT" ]] && { echo "Invalid folder. Exiting."; exit 1; }

sort_kit "$INPUT"
