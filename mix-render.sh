#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Mix Render"
echo "----------"
echo "Cuts both tracks on their bar grids and writes a real file."
echo "Run Z) Mix report first if you want a suggested pair."
echo

echo "Track A (the one that keeps its timing) — type a title:"
read "A?> "
[[ -z "$A" ]] && { echo "No track given. Exiting."; exit 1; }
echo "Start A at which bar? (see the loop candidates in the report)"
read "ABAR?> "

echo "Track B (the one stretched onto A's grid) — type a title:"
read "B?> "
[[ -z "$B" ]] && { echo "No track given. Exiting."; exit 1; }
echo "Start B at which bar?"
read "BBAR?> "

echo "How many bars? [8]"
read "BARS?> "
: "${BARS:=8}"

echo "Mode:  1) layer — both at once, pick stems   2) transition — A into B"
read "MODE?> "

if [[ "$MODE" == "2" ]]; then
  mix_render transition --a "$A" --a-bar "$ABAR" --b "$B" --b-bar "$BBAR" \
    --bars "$BARS" --out "Exports/mix.wav" --play
else
  echo "Stems from A? (mix, or e.g. drums,bass) [mix]"
  read "AST?> "; : "${AST:=mix}"
  echo "Stems from B? (mix, or e.g. vocals) [mix]"
  read "BST?> "; : "${BST:=mix}"
  mix_render layer --a "$A" --a-bar "$ABAR" --a-stems "$AST" \
    --b "$B" --b-bar "$BBAR" --b-stems "$BST" \
    --bars "$BARS" --out "Exports/mix.wav" --play
fi
