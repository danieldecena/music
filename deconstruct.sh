#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Deconstruct — full flip prep"
echo "----------------------------"
echo "Drag an audio file (analyzes tempo/key, splits stems, makes one-shots + kit + snippets):"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -f "$INPUT" ]] && { echo "Need an audio file. Exiting."; exit 1; }

echo "Drum density: 1) tight  2) loose"; read "d?> "
case "$d" in 1) DENS=tight;; 2) DENS=loose;; *) DENS=loose;; esac

deconstruct "$INPUT" "$DENS"
