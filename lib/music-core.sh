#!/usr/bin/env zsh
# Non-interactive core for the music toolkit. Source, don't execute.

LIB_DIR="${${(%):-%x}:A:h}"
MUSIC_DIR="${LIB_DIR:h}"

stem_mode_args() {
  case "$1" in
    instrumental) print -- "--two-stems=vocals" ;;
    4stem)        print -- "" ;;
    6stem)        print -- "-n htdemucs_6s" ;;
    *)            return 1 ;;
  esac
}

chop_sensitivity_args() {
  case "$1" in
    tight) print -- "--min-silence 0.15 --min-clip 0.3" ;;
    loose) print -- "--min-silence 0.35 --min-clip 0.8" ;;
    *)     return 1 ;;
  esac
}

find_new_m4a() {
  # $1 = directory, $2 = epoch seconds.
  # BSD find (/usr/bin/find on macOS) can't parse -newermt "@epoch", so compare
  # against the mtime of a reference file stamped at the target time instead.
  local ref
  ref=$(mktemp)
  touch -t "$(date -r "$2" '+%Y%m%d%H%M.%S')" "$ref"
  find "$1" -name '*.m4a' -newer "$ref" 2>/dev/null
  rm -f "$ref"
}

download_url() {
  # $1 = url, $2 = apple-music output dir (other types derive siblings)
  local url="$1" am_out="$2"
  local cookies="$MUSIC_DIR/cookies.txt"

  if [[ "$url" == *"music.apple.com"* ]]; then
    if [[ ! -f "$cookies" ]]; then
      /opt/homebrew/bin/python3 "$MUSIC_DIR/get-cookies.py" "$cookies" || {
        echo "Cookie extraction failed. Sign into music.apple.com in Safari + grant Full Disk Access." >&2
        return 1
      }
    fi
    # NOTE: url/cookies/am_out are interpolated into this expect heredoc. Safe
    # because url reaches this branch only via trusted interactive paste of an
    # Apple Music URL. Do NOT route untrusted URLs here without escaping.
    expect -c "
      set timeout -1
      spawn gamdl --cookies-path [list ${cookies}] --output-path [list ${am_out}] [list ${url}]
      expect -re {[?>]}
      send \"\x01\"
      send \"\r\"
      interact
    "
  elif [[ "$url" == *"soundcloud.com"* ]]; then
    local sc_out="$MUSIC_DIR/SoundCloud"; mkdir -p "$sc_out"
    yt-dlp --format "bestaudio[ext=m4a]/bestaudio/best" --extract-audio \
      --audio-format mp3 --audio-quality 0 --embed-thumbnail --add-metadata \
      --output "$sc_out/%(uploader)s/%(title)s.%(ext)s" "$url"
  else
    local other="$MUSIC_DIR/Downloads"; mkdir -p "$other"
    yt-dlp --format "bestaudio[ext=m4a]/bestaudio/best" --extract-audio \
      --audio-format mp3 --audio-quality 0 --embed-thumbnail --add-metadata \
      --output "$other/%(uploader)s/%(title)s.%(ext)s" "$url"
  fi
}

separate_stems() {
  # $1 = file, $2 = mode, $3 = out_dir ; echoes vocals.wav path
  local file="$1" mode="$2" out="$3"
  local args
  args=$(stem_mode_args "$mode") || { echo "bad mode: $mode" >&2; return 1; }
  mkdir -p "$out"
  demucs ${=args} --out "$out" "$file" || return 1
  local model_dir=htdemucs
  [[ "$mode" == 6stem ]] && model_dir=htdemucs_6s
  print -- "$out/$model_dir/${file:t:r}/vocals.wav"
}

chop_vocals() {
  # $1 = vocals.wav, $2 = out_dir, $3 = sensitivity
  local vocals="$1" out="$2" sens="$3"
  local args
  args=$(chop_sensitivity_args "$sens") || { echo "bad sensitivity: $sens" >&2; return 1; }
  source "$MUSIC_DIR/.venv/bin/activate"
  /opt/homebrew/bin/python3 "$MUSIC_DIR/Scripts/chop.py" "$vocals" "$out" ${=args}
}
