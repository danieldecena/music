#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Click-Compare Tempo"
echo "-------------------"
echo "Type a song title (typos OK) or drag an audio file / Stems folder, then Enter:"
read "RAW?> "
INPUT="$(resolve_target "$RAW")"
[[ -z "$INPUT" || ! -e "$INPUT" ]] && { echo "No match. Exiting."; exit 1; }
echo "Using: ${INPUT:t}"

echo "Base BPM estimate (blank = auto-detect):"
read "BPM?> "
echo "Known label BPM to also audition (blank = none):"
read "LABEL?> "

args=("$INPUT")
[[ -n "$BPM" ]] && args+=(--bpm "$BPM")
[[ -n "$LABEL" ]] && args+=(--label "$LABEL")

click_compare "${args[@]}"
