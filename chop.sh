#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Vocal Chopper"
echo "-------------"
echo "Drag a vocals.wav file or a Stems folder here (or press Enter for all stems):"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ -z "$INPUT" ]] && INPUT="$SCRIPT_DIR/Stems"
[[ ! -e "$INPUT" ]] && { echo "Invalid path. Exiting."; exit 1; }

echo "Sensitivity: 1) tight  2) loose"; read "s?> "
case "$s" in 1) SENS=tight;; 2) SENS=loose;; *) SENS=loose;; esac

chop_vocals "$INPUT" "$SCRIPT_DIR/Samples/Vocals" "$SENS"
