#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Click-Compare Tempo"
echo "-------------------"
echo "Drag an audio file or a Stems/<model>/<track> folder, then press Enter:"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -e "$INPUT" ]] && { echo "Invalid path. Exiting."; exit 1; }

echo "Base BPM estimate (blank = auto-detect):"
read "BPM?> "
echo "Known label BPM to also audition (blank = none):"
read "LABEL?> "

args=("$INPUT")
[[ -n "$BPM" ]] && args+=(--bpm "$BPM")
[[ -n "$LABEL" ]] && args+=(--label "$LABEL")

click_compare "${args[@]}"
