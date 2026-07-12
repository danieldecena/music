#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Stem Analyzer"
echo "-------------"
echo "Drag a Stems/<model>/<track> folder (or a single stem .wav), then press Enter:"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -e "$INPUT" ]] && { echo "Invalid path. Exiting."; exit 1; }

analyze_stems "$INPUT"
