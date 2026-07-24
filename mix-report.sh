#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Mix Report"
echo "----------"
echo "Type a song title (typos OK), then Enter:"
read "SEED?> "
[[ -z "$SEED" ]] && { echo "No track given. Exiting."; exit 1; }

echo "Play a preview of the top pair? [y/N]"
read "ANS?> "

args=("$SEED" --lyrics)
[[ "$ANS" == [yY]* ]] && args+=(--preview)

mix_report "${args[@]}"
