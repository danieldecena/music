#!/usr/bin/env zsh
set -e

SCRIPT_DIR="${0:A:h}"
COOKIES="$SCRIPT_DIR/cookies.txt"
AM_OUTPUT="$SCRIPT_DIR/Apple Music"
SC_OUTPUT="$SCRIPT_DIR/SoundCloud"
OTHER_OUTPUT="$SCRIPT_DIR/Downloads"

if [[ ! -f "$COOKIES" ]]; then
  echo "cookies.txt not found — extracting from Safari..."
  /opt/homebrew/bin/python3 "$SCRIPT_DIR/get-cookies.py" "$COOKIES"
  if [[ $? -ne 0 ]]; then
    echo ""
    echo "Auto-extract failed. Make sure:"
    echo "  1. You're signed into music.apple.com in Safari"
    echo "  2. Your terminal has Full Disk Access:"
    echo "     System Settings → Privacy & Security → Full Disk Access"
    exit 1
  fi
fi

echo "Music Downloader"
echo "----------------"
echo "Paste a URL (Apple Music, SoundCloud, YouTube, Bandcamp, etc.):"
echo -n "> "
read URL

if [[ -z "$URL" ]]; then
  echo "No URL provided. Exiting."
  exit 1
fi

if [[ "$URL" == *"music.apple.com"* ]]; then
  echo "→ Apple Music"
  expect -c "
    set timeout -1
    spawn gamdl --cookies-path [list ${COOKIES}] --output-path [list ${AM_OUTPUT}] [list ${URL}]
    expect -re {[?>]}
    send \"\x01\"
    send \"\r\"
    interact
  "

elif [[ "$URL" == *"soundcloud.com"* ]]; then
  echo "→ SoundCloud"
  mkdir -p "$SC_OUTPUT"
  yt-dlp \
    --format "bestaudio[ext=m4a]/bestaudio/best" \
    --extract-audio \
    --audio-format mp3 \
    --audio-quality 0 \
    --embed-thumbnail \
    --add-metadata \
    --output "$SC_OUTPUT/%(uploader)s/%(title)s.%(ext)s" \
    "$URL"

else
  echo "→ yt-dlp"
  mkdir -p "$OTHER_OUTPUT"
  yt-dlp \
    --format "bestaudio[ext=m4a]/bestaudio/best" \
    --extract-audio \
    --audio-format mp3 \
    --audio-quality 0 \
    --embed-thumbnail \
    --add-metadata \
    --output "$OTHER_OUTPUT/%(uploader)s/%(title)s.%(ext)s" \
    "$URL"
fi
