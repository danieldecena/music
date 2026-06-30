#!/usr/bin/env zsh
set -e

SCRIPT_DIR="${0:A:h}"
OUTPUT="$SCRIPT_DIR/Stems"

echo "Stem Separator"
echo "--------------"
echo "Drag a file or folder here, then press Enter:"
echo -n "> "
read INPUT
INPUT="${INPUT//\\ / }"   # unescape spaces from drag-and-drop
INPUT="${INPUT%"${INPUT##*[! ]}"}"  # trim trailing whitespace

if [[ -z "$INPUT" || (! -f "$INPUT" && ! -d "$INPUT") ]]; then
  echo "Invalid path. Exiting."
  exit 1
fi

echo ""
echo "Separation mode:"
echo "  1) Instrumental only (vocals out) — fastest"
echo "  2) 4 stems: vocals, drums, bass, other"
echo "  3) 6 stems: vocals, drums, bass, guitar, piano, other"
echo -n "> "
read MODE

case "$MODE" in
  1)
    ARGS=(--two-stems=vocals)
    LABEL="instrumental"
    ;;
  2)
    ARGS=()
    LABEL="4-stem"
    ;;
  3)
    ARGS=(-n htdemucs_6s)
    LABEL="6-stem"
    ;;
  *)
    echo "Invalid choice. Exiting."
    exit 1
    ;;
esac

mkdir -p "$OUTPUT"

echo ""
echo "→ Running $LABEL separation..."
echo "   Output: $OUTPUT"
echo ""

if [[ -f "$INPUT" ]]; then
  demucs "${ARGS[@]}" --out "$OUTPUT" "$INPUT"
else
  # Directory — process all audio files
  find "$INPUT" -type f \( -name "*.m4a" -o -name "*.mp3" -o -name "*.flac" -o -name "*.wav" \) | while read -r f; do
    echo "Processing: ${f:t}"
    demucs "${ARGS[@]}" --out "$OUTPUT" "$f"
  done
fi

echo ""
echo "Done. Stems saved to: $OUTPUT"
