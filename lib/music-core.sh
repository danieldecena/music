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

drum_split_args() {
  # Density knob for slice_drums.py onset detection. tight = more, shorter hits.
  case "$1" in
    tight) print -- "--delta 0.04 --wait 0.05" ;;
    loose) print -- "--delta 0.09 --wait 0.12" ;;
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

  [[ -z "$url" ]] && { echo "download_url: no URL given." >&2; return 2; }

  if [[ "$url" == *"music.apple.com"* ]]; then
    command -v gamdl >/dev/null || { echo "gamdl not found on PATH — install it (pipx install gamdl)." >&2; return 3; }
    command -v expect >/dev/null || { echo "expect not found on PATH — install it (brew install expect)." >&2; return 3; }
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
    command -v yt-dlp >/dev/null || { echo "yt-dlp not found on PATH — install it (brew install yt-dlp)." >&2; return 3; }
    local sc_out="$MUSIC_DIR/SoundCloud"; mkdir -p "$sc_out"
    yt-dlp --format "bestaudio[ext=m4a]/bestaudio/best" --extract-audio \
      --audio-format m4a --audio-quality 0 --embed-thumbnail --add-metadata \
      --output "$sc_out/%(uploader)s/%(title)s.%(ext)s" "$url"
  else
    command -v yt-dlp >/dev/null || { echo "yt-dlp not found on PATH — install it (brew install yt-dlp)." >&2; return 3; }
    local other="$MUSIC_DIR/Downloads"; mkdir -p "$other"
    yt-dlp --format "bestaudio[ext=m4a]/bestaudio/best" --extract-audio \
      --audio-format m4a --audio-quality 0 --embed-thumbnail --add-metadata \
      --output "$other/%(uploader)s/%(title)s.%(ext)s" "$url"
  fi
}

separate_stems() {
  # $1 = file, $2 = mode, $3 = out_dir ; echoes vocals.wav path
  local file="$1" mode="$2" out="$3"
  local args
  args=$(stem_mode_args "$mode") || { echo "bad mode: $mode" >&2; return 1; }
  # demucs lives in the venv, not on the global PATH — activate it here so this
  # works standalone (via ./stems.sh or the menu), matching chop_vocals.
  [[ -z "${VIRTUAL_ENV:-}" ]] && source "$MUSIC_DIR/.venv/bin/activate"
  command -v demucs >/dev/null || { echo "demucs not found even after venv activate — run: pip install -r requirements? (see .venv)" >&2; return 1; }
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

chop_drums() {
  # $1 = drums.wav (or Stems folder), $2 = out_dir, $3 = density (tight|loose)
  # Splits a drum stem into one-shot hits via onset detection. Uses the venv's
  # python directly because slice_drums.py needs numpy (chop.py is stdlib-only).
  local input="$1" out="$2" sens="$3"
  local args
  args=$(drum_split_args "$sens") || { echo "bad density: $sens" >&2; return 1; }
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/slice_drums.py" "$input" "$out" ${=args}
}

chop_stems() {
  # $1 = a Stems/<model>/<track> folder (or a single stem .wav), $2 = out_root,
  # $3 = snippet seconds (default 8). Fixed-length chops per stem into
  # <out_root>/<track>/<stem>/<stem>_NNN.wav — the auditioning layout.
  local input="$1" out="$2" secs="${3:-8}"
  local -a stems
  local track
  if [[ -d "$input" ]]; then
    track="${input:t}"
    stems=("$input"/*.wav(N))
  else
    track="${input:h:t}"
    stems=("$input")
  fi
  [[ ${#stems} -eq 0 ]] && { echo "No stem .wav files in $input" >&2; return 1; }
  local stem name dest
  for stem in $stems; do
    name="${stem:t:r}"
    dest="$out/$track/$name"; mkdir -p "$dest"
    ffmpeg -nostdin -y -v error -i "$stem" -f segment -segment_time "$secs" \
      -segment_start_number 1 -c copy -reset_timestamps 1 "$dest/${name}_%03d.wav" \
      && echo "  $name -> $dest"
  done
}

sort_kit() {
  # $1 = a One-Shots folder of drum hits. Classifies into kick/snare/hat subdirs.
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/sort_drums.py" "$1"
}

analyze_track() {
  # $1 = an audio file (or folder). Prints estimated BPM + key per file.
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/analyze_track.py" "$1"
}

bass_to_midi() {
  # $1 = bass.wav (monophonic stem), $2 = out .mid, $3 = tempo BPM (default 120).
  # Best-effort: reliable only for clean single-note lines; polyphony won't transcribe.
  local input="$1" out="$2" tempo="${3:-120}"
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/bass_to_midi.py" "$input" "$out" --tempo "$tempo"
}

build_logic_project() {
  # $1 = a Stems/<model>/<track> folder, $2 = tempo (optional), $3 = key (optional).
  # Loads the stems as audio tracks in a new Logic project. If a bass.wav is
  # present it is transcribed to MIDI and imported as a software-instrument
  # track too (so the bass can be re-voiced). Shells out to the logic-pro-mcp
  # CLI, which drives Logic Pro (best-effort UI scripting; Logic is launched if
  # not already open).
  local stems="$1" tempo="$2" key="$3"
  local mcp="$MUSIC_DIR/logic-pro-mcp"
  local py="$mcp/.venv/bin/python"
  [[ ! -x "$py" ]] && { echo "logic-pro-mcp venv not found at $py — set it up first." >&2; return 1; }
  local -a args=("$mcp/build_project.py" "$stems")
  [[ -n "$tempo" ]] && args+=(--tempo "$tempo")
  [[ -n "$key" ]] && args+=(--key "$key")
  # Transcribe the bass to MIDI so the build can add it as an instrument track.
  local bass="$stems/bass.wav" midi=""
  if [[ -f "$bass" ]]; then
    midi="$MUSIC_DIR/Samples/MIDI/${stems:t}_bass.mid"
    mkdir -p "${midi:h}"
    if bass_to_midi "$bass" "$midi" "${tempo:-120}" >/dev/null 2>&1 && [[ -f "$midi" ]]; then
      args+=(--midi "$midi")
    fi
  fi
  "$py" "${args[@]}"
}

resynth_instrument() {
  # $1 = input .wav (monophonic melodic stem), $2 = out_dir, $3 = instrument,
  # $4 = tempo BPM (default 120), $5 = soundfont name/path (optional). Transcribes
  # the line then renders it as the chosen instrument via Scripts/resynth.py.
  local input="$1" out="$2" instrument="$3" tempo="${4:-120}" soundfont="$5"
  local -a args=("$MUSIC_DIR/Scripts/resynth.py" "$input" "$out"
    --instrument "$instrument" --tempo "$tempo")
  [[ -n "$soundfont" ]] && args+=(--soundfont "$soundfont")
  "$MUSIC_DIR/.venv/bin/python" "${args[@]}"
}

revoice_melody() {
  # $1 = input .wav (monophonic melodic stem), $2 = instrument (default guitar),
  # $3 = tempo BPM (default 120), $4 = soundfont name/path (optional).
  # Wraps resynth_instrument with the Samples/Resynth/<name> output convention
  # used by the `music` menu's Re-voice step.
  local input="$1" instrument="${2:-guitar}" tempo="${3:-120}" soundfont="$4"
  local out="$MUSIC_DIR/Samples/Resynth/${input:t:r}"
  resynth_instrument "$input" "$out" "$instrument" "$tempo" "$soundfont"
}

mangle() {
  # $1 = a sample .wav OR a folder of samples (e.g. Samples/Chops/<track>/other),
  # $2 = comma-separated transforms (optional; default = all),
  # $3 = max files when $1 is a folder (default 8).
  # Fans each sample out into transformed variants under Samples/Mangled/<track>/.
  local input="$1" only="$2" maxn="${3:-8}"
  [[ ! -e "$input" ]] && { echo "mangle: need a .wav or folder, got '$input'" >&2; return 2; }
  local -a args=("$MUSIC_DIR/Scripts/mangle.py" "$input" --max "$maxn")
  [[ -n "$only" ]] && args+=(--only "$only")
  "$MUSIC_DIR/.venv/bin/python" "${args[@]}"
}

deconstruct() {
  # $1 = audio file, $2 = drum density (tight|loose, default loose).
  # One-command flip prep: tempo/key -> 4-stem split -> drum one-shots ->
  # sort kit (kick/snare/hat) -> 8s stem snippets -> vocal phrase chops.
  # Chains the reliable steps.
  local file="$1" dens="${2:-loose}"
  [[ ! -f "$file" ]] && { echo "deconstruct: need an audio file, got '$file'" >&2; return 2; }
  local track="${file:t:r}"
  local stemdir="$MUSIC_DIR/Stems/htdemucs/$track"
  echo "→ Tempo & key:"
  local _analysis; _analysis=$(analyze_track "$file"); print -r -- "$_analysis"
  echo "→ Separating 4 stems (drums/bass/other/vocals)…"
  separate_stems "$file" 4stem "$MUSIC_DIR/Stems" >/dev/null || return 1
  echo "→ Drum one-shots…"
  chop_drums "$stemdir/drums.wav" "$MUSIC_DIR/Samples/One-Shots" "$dens" | tail -1
  echo "→ Sorting kit (kick/snare/hat)…"
  sort_kit "$MUSIC_DIR/Samples/One-Shots/$track"
  echo "→ 8s stem snippets…"
  chop_stems "$stemdir" "$MUSIC_DIR/Samples/Chops" 8 >/dev/null
  echo "→ Vocal phrase chops…"
  chop_vocals "$stemdir/vocals.wav" "$MUSIC_DIR/Samples/Vocals" loose >/dev/null
  echo "✓ Deconstruct complete: $track"
  echo "  Stems: $stemdir"
  echo "  One-shots + kit: Samples/One-Shots/$track"
  echo "  Snippets: Samples/Chops/$track"
  echo "  Vocal chops: Samples/Vocals/$track"
  # Catalog (best-effort): parse BPM/key from the analysis and index this track.
  local _bpm _key
  _bpm=$(print -r -- "$_analysis" | sed -nE 's/.*[^0-9]([0-9]{2,3})(\.[0-9]+)?[[:space:]]*BPM.*/\1/p' | head -1)
  _key=$(print -r -- "$_analysis" | sed -nE 's/.*[Kk]ey[[:space:]]+([A-Ga-g][b#]?m?).*/\1/p' | head -1)
  if [[ -x "$MUSIC_DIR/.venv/bin/python" ]]; then
    "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/catalog.py" index-track "$track" ${_bpm:+--bpm $_bpm} ${_key:+--key $_key} >/dev/null 2>&1
  fi
}
