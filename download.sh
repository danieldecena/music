#!/usr/bin/env zsh
set -e
SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/lib/music-core.sh"

echo "Music Downloader"
echo "----------------"
echo "Paste a URL (Apple Music, SoundCloud, YouTube, Bandcamp, etc.):"
read "URL?> "
[[ -z "$URL" ]] && { echo "No URL provided. Exiting."; exit 1; }

download_url "$URL" "$SCRIPT_DIR/Apple Music"
