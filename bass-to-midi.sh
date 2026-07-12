#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Bass -> MIDI"
echo "------------"
if [[ -n "${1:-}" ]]; then
  INPUT="$1"
else
  echo "Drag a bass.wav or a Stems track folder:"
  read "INPUT?> "
fi
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -e "$INPUT" ]] && { echo "Invalid path. Exiting."; exit 1; }

if [[ -d "$INPUT" ]]; then
  BASS=$(find "$INPUT" -type f -name 'bass.wav' | head -1)
  [[ -z "$BASS" ]] && { echo "No bass.wav under that folder."; exit 1; }
else
  BASS="$INPUT"
fi

TEMPO="${2:-120}"
OUT="$SCRIPT_DIR/Samples/MIDI/${BASS:h:t}_bass.mid"
mkdir -p "${OUT:h}"
bass_to_midi "$BASS" "$OUT" "$TEMPO"
echo "Wrote $OUT"
