#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Harmonic Mix-Match"
echo "------------------"
echo "Finds pairs of analyzed catalog tracks that mix well (compatible key + tempo)."
read "ly?Match lyric themes too? (slower, needs network) [y/N]> "
args=()
[[ "$ly" == (y|Y|yes) ]] && args+=(--lyrics)
mix_match "${args[@]}"
