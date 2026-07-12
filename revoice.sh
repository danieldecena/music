#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Re-voice Melody"
echo "----------------"
if [[ -n "${1:-}" ]]; then
  INPUT="$1"
else
  echo "Drag a monophonic melodic stem (.wav -- a lead/bass/vocal line):"
  read "INPUT?> "
fi
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"

if [[ -d "$INPUT" ]]; then
  STEM=$(find "$INPUT" -type f \( -name 'other.wav' -o -name 'bass.wav' -o -name 'vocals.wav' \) | head -1)
  [[ -z "$STEM" ]] && { echo "No melodic stem (other/bass/vocals.wav) under that folder."; exit 1; }
  INPUT="$STEM"
fi
[[ ! -f "$INPUT" ]] && { echo "Need an audio file. Exiting."; exit 1; }

INSTR="${2:-guitar}"
TEMPO="${3:-120}"
SOUNDFONT="${4:-}"

revoice_melody "$INPUT" "$INSTR" "$TEMPO" "$SOUNDFONT"
