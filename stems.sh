#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Stem Separator"
echo "--------------"
echo "Drag a file or folder here, then press Enter:"
read "INPUT?> "
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -e "$INPUT" ]] && { echo "Invalid path. Exiting."; exit 1; }

echo "Mode: 1) instrumental  2) 4stem  3) 6stem"; read "m?> "
case "$m" in 1) MODE=instrumental;; 2) MODE=4stem;; 3) MODE=6stem;; *) echo "Invalid."; exit 1;; esac

if [[ -f "$INPUT" ]]; then
  separate_stems "$INPUT" "$MODE" "$SCRIPT_DIR/Stems"
else
  find "$INPUT" -type f \( -name '*.m4a' -o -name '*.mp3' -o -name '*.flac' -o -name '*.wav' \) | while read -r f; do
    echo "Processing: ${f:t}"; separate_stems "$f" "$MODE" "$SCRIPT_DIR/Stems"
  done
fi
echo "Done. Stems saved to: $SCRIPT_DIR/Stems"
