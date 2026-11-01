#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Mangle — flip-fuel variants"
echo "---------------------------"
if [[ -n "${1:-}" ]]; then
	INPUT="$1"
else
	echo "Drag a sample .wav or a folder of samples:"
	read "INPUT?> "
fi
INPUT="$(clean_path "$INPUT")"
[[ ! -e "$INPUT" ]] && { echo "Need a .wav or folder. Exiting."; exit 1; }

# $2 optional comma-separated transform list (default = all)
mangle "$INPUT" "${2:-}"
