#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Drum Splitter"
echo "-------------"
echo "Drag a drums.wav file or a Stems folder here (or press Enter for all stems):"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ -z "$INPUT" ]] && INPUT="$SCRIPT_DIR/Stems"
[[ ! -e "$INPUT" ]] && { echo "Invalid path. Exiting."; exit 1; }

echo "Density: 1) tight (more, shorter hits)  2) loose (fewer)"; read "s?> "
case "$s" in 1) SENS=tight;; 2) SENS=loose;; *) SENS=loose;; esac

chop_drums "$INPUT" "$SCRIPT_DIR/Samples/One-Shots" "$SENS"
