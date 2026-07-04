#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Deconstruct — full flip prep"
echo "----------------------------"
if [[ -n "${1:-}" ]]; then
	INPUT="$1"
else
	echo "Drag an audio file (analyzes tempo/key, splits stems, makes one-shots + kit + snippets):"
	read "INPUT?> "
fi
INPUT="${INPUT//\\ / }"; INPUT="${INPUT%"${INPUT##*[! ]}"}"
[[ ! -f "$INPUT" ]] && { echo "Need an audio file. Exiting."; exit 1; }

if [[ -n "${2:-}" ]]; then
	case "$2" in
		tight|loose) DENS="$2" ;;
		*) echo "Invalid density '$2' (use tight|loose). Exiting."; exit 1 ;;
	esac
else
	echo "Drum density: 1) tight  2) loose"
	read "d?> "
	case "$d" in 1) DENS=tight;; 2) DENS=loose;; *) DENS=loose;; esac
fi

deconstruct "$INPUT" "$DENS" 