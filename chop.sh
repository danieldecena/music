#!/usr/bin/env zsh
set -e

SCRIPT_DIR="${0:A:h}"
STEMS_DIR="$SCRIPT_DIR/Stems"
OUTPUT="$SCRIPT_DIR/Samples/Vocals"

echo "Vocal Chopper"
echo "-------------"
echo "Drag a vocals.wav file or a Stems folder here (or press Enter to use all stems):"
echo -n "> "
read INPUT
INPUT="${INPUT//\\ / }"
INPUT="${INPUT%"${INPUT##*[! ]}"}"

if [[ -z "$INPUT" ]]; then
  INPUT="$STEMS_DIR"
fi

if [[ ! -f "$INPUT" && ! -d "$INPUT" ]]; then
  echo "Invalid path. Exiting."
  exit 1
fi

echo ""
echo "Silence sensitivity:"
echo "  1) Tight   — splits on short pauses (more clips, good for ad-libs)"
echo "  2) Loose   — splits on longer gaps only (fewer clips, full phrases) (Recommended)"
echo -n "> "
read SENS

case "$SENS" in
  1) MIN_SILENCE=0.15 ; MIN_CLIP=0.3  ;;
  2) MIN_SILENCE=0.35 ; MIN_CLIP=0.8  ;;
  *) MIN_SILENCE=0.25 ; MIN_CLIP=0.5  ;;
esac

echo ""
echo "→ Chopping vocals..."
echo "   Output: $OUTPUT"
echo ""

source "$SCRIPT_DIR/.venv/bin/activate"
/opt/homebrew/bin/python3 "$SCRIPT_DIR/Scripts/chop.py" \
  "$INPUT" "$OUTPUT" \
  --min-silence "$MIN_SILENCE" \
  --min-clip "$MIN_CLIP"
