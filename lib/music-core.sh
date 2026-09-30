#!/usr/bin/env zsh
# Non-interactive core for the music toolkit. Source, don't execute.

LIB_DIR="${${(%):-%x}:A:h}"
MUSIC_DIR="${LIB_DIR:h}"

stem_profile_args() {
  # Quality profile -> demucs args. hq is the cleanest 6-stem (guitar/piano).
  case "$1" in
    acapella) print -- "--two-stems=vocals" ;;
    fast)     print -- "" ;;
    6stem)    print -- "-n htdemucs_6s" ;;
    hq)       print -- "-n htdemucs_6s --shifts 2 --overlap 0.5" ;;
    *)        return 1 ;;
  esac
}

stem_profile_model() {
  # Quality profile -> output model directory under Stems/.
  case "$1" in
    acapella|fast) print -- "htdemucs" ;;
    6stem|hq)      print -- "htdemucs_6s" ;;
    *)             return 1 ;;
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

stems_dir_for() {  # echoes existing Stems/<model>/<name> dir, htdemucs preferred
  local name="$1" m
  for m in htdemucs htdemucs_6s; do
    if [[ -d "$MUSIC_DIR/Stems/$m/$name" ]]; then
      print -- "$MUSIC_DIR/Stems/$m/$name"; return 0
    fi
  done
  return 0
}

dir_has() {  # $1 = dir. True if it holds at least one entry. [1] stops the glob
  local f=("$1"/*(N[1]))  # at the first match instead of listing hundreds.
  (( ${#f} ))
}

track_state() {
  # $1 = track name. Echoes "stems drums shots kit chops" as 1/0 flags — what
  # this track already has, so a caller can name the next step. Owns the output
  # layout the chop_* / sort_kit writers below produce.
  local name="$1" m
  local stems=0 drums=0 shots=0 kit=0 chops=0
  # Check every model dir, not just the one stems_dir_for prefers: a track split
  # acapella (htdemucs, no drums) and again 6-stem (htdemucs_6s, drums) has drums.
  for m in htdemucs htdemucs_6s; do
    [[ -d "$MUSIC_DIR/Stems/$m/$name" ]] && stems=1
    [[ -f "$MUSIC_DIR/Stems/$m/$name/drums.wav" ]] && drums=1
  done
  dir_has "$MUSIC_DIR/Samples/One-Shots/$name" && shots=1
  dir_has "$MUSIC_DIR/Samples/One-Shots/$name/kick" && kit=1
  dir_has "$MUSIC_DIR/Samples/Chops/$name" && chops=1
  print -- "$stems $drums $shots $kit $chops"
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
      python3 "$MUSIC_DIR/get-cookies.py" "$cookies" || {
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

download_and_locate() {
  # $1 = url, $2 = apple-music output dir. Downloads, then prints the
  # newline-separated paths of the .m4a files that appeared. download_url routes
  # Apple Music -> am_out, SoundCloud -> $MUSIC_DIR/SoundCloud, else -> Downloads,
  # so check each root that exists for files newer than the pre-download stamp.
  local url="$1" am_out="$2" stamp d
  stamp=$(date +%s)
  download_url "$url" "$am_out" || return
  for d in "$am_out" "$MUSIC_DIR/SoundCloud" "$MUSIC_DIR/Downloads"; do
    [[ -d "$d" ]] && find_new_m4a "$d" "$stamp"
  done
}

separate_stems() {
  # $1 = file, $2 = profile, $3 = out_dir ; echoes vocals.wav path
  local file="$1" profile="$2" out="$3"
  local args
  args=$(stem_profile_args "$profile") || { echo "bad profile: $profile" >&2; return 1; }
  # demucs lives in the venv, not on the global PATH — activate it here so this
  # works standalone (via ./stems.sh or the menu), matching chop_vocals.
  [[ -z "${VIRTUAL_ENV:-}" ]] && source "$MUSIC_DIR/.venv/bin/activate"
  command -v demucs >/dev/null || { echo "demucs not found even after venv activate — run: pip install -r requirements? (see .venv)" >&2; return 1; }
  mkdir -p "$out"
  demucs ${=args} --out "$out" "$file" || return 1
  local model_dir
  model_dir=$(stem_profile_model "$profile")
  print -- "$out/$model_dir/${file:t:r}/vocals.wav"
}

chop_vocals() {
  # $1 = vocals.wav, $2 = out_dir, $3 = sensitivity
  local vocals="$1" out="$2" sens="$3"
  local args
  args=$(chop_sensitivity_args "$sens") || { echo "bad sensitivity: $sens" >&2; return 1; }
  source "$MUSIC_DIR/.venv/bin/activate"
  python3 "$MUSIC_DIR/Scripts/chop.py" "$vocals" "$out" ${=args}
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

stem_presence_label() {
  # $1 = mean dBFS, $2 = max dBFS -> silent | faint | present.
  # zsh has no native float <, so compare in awk.
  awk -v m="$1" -v x="$2" 'BEGIN{
    if (x < -50) print "silent";
    else if (m < -45) print "faint";
    else print "present";
  }'
}

analyze_stems() {
  # $1 = a Stems/<model>/<track> folder (or a single stem .wav). Prints a
  # presence/loudness table per stem (ffmpeg volumedetect) and writes it to
  # <folder>/analysis.txt. Read-only; never modifies the stems.
  local input="$1"
  local -a stems
  local dir
  if [[ -d "$input" ]]; then
    dir="$input"
    stems=("$input"/*.wav(N))
  else
    dir="${input:h}"
    stems=("$input")
  fi
  [[ ${#stems} -eq 0 ]] && { echo "No stem .wav files in $input" >&2; return 1; }
  local report="$dir/analysis.txt"
  local stem name vd mean max label
  {
    printf "%-10s %9s %9s  %s\n" "stem" "mean" "peak" "presence"
    for stem in $stems; do
      name="${stem:t:r}"
      vd=$(ffmpeg -nostdin -i "$stem" -af volumedetect -f null - 2>&1)
      mean=$(print -r -- "$vd" | awk -F': ' '/mean_volume:/{print $2+0}')
      max=$(print -r -- "$vd" | awk -F': ' '/max_volume:/{print $2+0}')
      label=$(stem_presence_label "$mean" "$max")
      printf "%-10s %6s dB %6s dB  %s\n" "$name" "$mean" "$max" "$label"
    done
  } | tee "$report"
  echo "  Report: $report" >&2
}

sort_kit() {
  # $1 = a One-Shots folder of drum hits. Classifies into kick/snare/hat subdirs.
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/sort_drums.py" "$1"
}

analyze_track() {
  # $1 = an audio file (or folder). Prints estimated BPM + key per file.
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/analyze_track.py" "$1"
}

chord_progression() {
  # $1 = an audio file or a Stems/<model>/<track> folder. Prints a bar-by-bar
  # chord chart and writes <input>/chords.txt (read-only; never re-encodes).
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/chords.py" "$1"
}

mix_match() {
  # Ranks catalog track pairs that mix well (Camelot key + tempo). Reads the
  # catalog; takes no track path. Flags pass through to `catalog.py mix`
  # (e.g. --lyrics, --limit N, --tempo-tol F).
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/catalog.py" mix "$@"
}

mix_report() {
  # $1 = a track title (fuzzy). Ranks the rest of the catalog against that one
  # track and prints a verdict, why it works, shared lyric words and near
  # misses. Extra flags pass through to `catalog.py mix` (--lyrics, --preview,
  # --limit N, --tempo-tol F, --json).
  local seed="$1"; shift
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/catalog.py" mix --seed "$seed" "$@"
}

apple_analyze() {
  # $1 = audio file. Runs Tools/mu-analyze, ingests the result and scores loop
  # regions, so the track gains the bar grid mix_render cuts on. Separate from
  # analyze_track: that estimates BPM/key from this repo's own analyzer, while
  # this persists Apple's beats, bars, sections and instrument activity.
  local file="$1" track="${1:t:r}"
  local mu="$MUSIC_DIR/Tools/mu-analyze" py="$MUSIC_DIR/.venv/bin/python"
  if [[ ! -x "$mu" ]]; then
    echo "apple_analyze: Tools/mu-analyze is not built -- mix-render needs its bar grid" >&2
    return 1
  fi
  if [[ ! -f "$file" ]]; then
    echo "apple_analyze: no such audio file: '$file'" >&2
    return 1
  fi
  # Keep mu-analyze's own stderr: a missing file and an unsupported OS are
  # different failures, and collapsing both into one guess is how a wrong
  # cause gets written down as fact.
  #
  # The JSON is kept, not written to a temp file and deleted. Samples/Analysis/
  # is where score_apple.py, test_catalog_ingest.py and catalog.py backfill-grid
  # all look, and publish_to_icloud has nothing to hand the phone without it.
  # Regenerating means re-decoding the audio, so throwing it away was the more
  # expensive of the two options as well as the inconsistent one.
  local outdir="$MUSIC_DIR/Samples/Analysis"
  mkdir -p "$outdir"
  local json="$outdir/$track.json" err
  if ! err=$("$mu" "$file" 2>&1 >"$json"); then
    rm -f "$json"
    echo "apple_analyze: mu-analyze failed on '$file': ${err:-no error text}" >&2
    return 1
  fi
  if ! "$py" "$MUSIC_DIR/Scripts/catalog.py" ingest "$track" "$json" >/dev/null; then
    echo "apple_analyze: could not ingest the analysis for '$track'" >&2
    return 1
  fi
  "$py" "$MUSIC_DIR/Scripts/catalog.py" regions "$track" --bars 4 >/dev/null
}

mix_render() {
  # $1 = mode (layer|transition). Remaining args pass through to
  # Scripts/mix_render.py, which cuts both tracks on their persisted bar grids.
  # Unlike mix_report's preview this writes a real file: `layer` plays both
  # sides at once so one track's stems sit under the other's.
  local mode="$1"; shift
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/mix_render.py" "$mode" "$@"
}

click_compare() {
  # $1 = an audio file or a Stems/<model>/<track> folder; extra flags pass
  # through (--bpm B, --label L, --dur S, --start S). Interactive: auditions
  # the tempo estimate against its octave/3:2 partners over the audio so the
  # ear settles which BPM locks. Needs speakers; plays via afplay.
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/click_compare.py" "$@"
}

find_tracks() {  # $1 = title query. Prints "score<TAB>kind<TAB>label<TAB>path" rows, best first.
  "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/find_track.py" "$1" --tsv 2>/dev/null
}

pick_track() {
  # $1 = a typed song title (typos tolerated). Fuzzy-resolves it to a path and
  # echoes that path on stdout; the match list and prompts go to stderr so a
  # caller can capture the path with $(pick_track ...). A lone match is returned
  # without a menu; Enter takes the top (best) match. Returns 1 (empty stdout)
  # when nothing matches or the user cancels with q.
  local q="$1"
  local -a rows; rows=("${(@f)$(find_tracks "$q")}"); rows=("${(@)rows:#}")
  if (( ${#rows} == 0 )); then
    echo "No track matches \"$q\" — try fewer letters, or drag the file/folder." >&2
    return 1
  fi
  if (( ${#rows} == 1 )); then
    local -a p=("${(@s:	:)rows[1]}"); print -- "$p[4]"; return 0
  fi
  echo "Matches for \"$q\":" >&2
  local i=1 r
  for r in "${rows[@]}"; do
    local -a p=("${(@s:	:)r}")
    printf "  %d) [%s] %s\n" "$i" "$p[2]" "$p[3]" >&2
    ((i++))
  done
  local pick; read "pick?Pick # (Enter = 1, q = cancel)> "
  [[ "$pick" == (q|Q) ]] && return 1
  [[ -z "$pick" ]] && pick=1
  [[ "$pick" == <-> && "$pick" -ge 1 && "$pick" -le ${#rows} ]] || { echo "Invalid pick." >&2; return 1; }
  local -a p=("${(@s:	:)rows[$pick]}"); print -- "$p[4]"
}

resolve_target() {
  # $1 = raw typed input — a dragged path or a song title. Echoes a resolved
  # path (empty + return 1 on no match/cancel). An existing path is passed
  # through untouched; anything else is fuzzy-matched via pick_track.
  local raw="$1"
  raw="${raw//\\ / }"; raw="${raw%"${raw##*[! ]}"}"
  [[ -z "$raw" ]] && return 1
  [[ -e "$raw" ]] && { print -- "$raw"; return 0; }
  pick_track "$raw"
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

icloud_container() {
  # Absolute path of the Flip app's iCloud Documents container, printed on
  # stdout; non-zero and silent when there isn't one.
  #
  # MUSIC_ICLOUD_DIR overrides it. That exists so the copy logic is testable
  # without a registered container -- the container is created by iCloud once
  # the app carries the entitlement, and nothing this repo does can conjure one.
  if [[ -n "$MUSIC_ICLOUD_DIR" ]]; then
    print -r -- "$MUSIC_ICLOUD_DIR"
    return 0
  fi
  # Existence is enough of a test: ~/Library/Mobile Documents is not writable
  # by hand (mkdir there is Permission denied), so only `bird` can have made
  # this, and a stray local folder cannot pose as a synced container. The
  # directory appears once an entitled process claims the container at runtime.
  local c="$HOME/Library/Mobile Documents/iCloud~com~danieldecena~flip/Documents"
  [[ -d "$c" ]] || return 1
  print -r -- "$c"
}

publish_to_icloud() {
  # $1 = track name. Copies the track's stems and its analysis JSON into the
  # iCloud container as Tracks/<track>/, which is what the phone reads.
  #
  # Fails loudly with no container: this is only called directly when someone
  # asked for it, and "nothing to publish to" is not the same as "published".
  # deconstruct() probes icloud_container first and reports rather than failing.
  local track="$1"
  [[ -z "$track" ]] && { echo "publish_to_icloud: need a track name" >&2; return 2; }
  # The destination is rsync --delete'd, so a track name that can escape its own
  # directory would delete somewhere else entirely.
  case "$track" in
    */*|*..*) echo "publish_to_icloud: refusing a path-shaped track name: '$track'" >&2; return 2 ;;
  esac

  local container
  if ! container=$(icloud_container); then
    echo "publish_to_icloud: no iCloud container. The Flip app needs an iCloud" >&2
    echo "  Documents entitlement before one exists; set MUSIC_ICLOUD_DIR to" >&2
    echo "  publish somewhere else meanwhile." >&2
    return 1
  fi

  # Whichever model holds this track. Several can: a track split fast and then
  # again at hq lands under both htdemucs and htdemucs_6s. Take the newest and
  # say which, rather than picking one silently.
  local -a candidates
  candidates=("$MUSIC_DIR"/Stems/*/"$track"(/Nom))
  if (( ${#candidates} == 0 )); then
    echo "publish_to_icloud: no stems for '$track' under $MUSIC_DIR/Stems" >&2
    return 1
  fi
  local src="${candidates[1]}"
  (( ${#candidates} > 1 )) && echo "  (several models have '$track'; publishing ${src:h:t})"

  local json="$MUSIC_DIR/Samples/Analysis/$track.json"
  if [[ ! -f "$json" ]]; then
    echo "publish_to_icloud: no analysis for '$track' -- run apple_analyze first" >&2
    return 1
  fi

  local dest="$container/Tracks/$track"
  mkdir -p "$dest" || return 1
  # --delete so a republish after a different stem profile does not leave the
  # previous model's stems behind for the phone to show as real. Bounded to the
  # one directory this function owns, whose name was validated above.
  rsync -a --delete --exclude 'analysis.json' "$src/" "$dest/" || return 1
  cp "$json" "$dest/analysis.json" || return 1

  # rsync's exit code says the transfer ran, not that the phone has anything to
  # read. Count what actually landed.
  local -a landed
  landed=("$dest"/*(.N))
  if (( ${#landed} < 2 )); then
    echo "publish_to_icloud: '$track' published but $dest holds ${#landed} files" >&2
    return 1
  fi
  echo "  Published ${#landed} files to $dest"
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
  separate_stems "$file" fast "$MUSIC_DIR/Stems" >/dev/null || return 1
  echo "→ Drum one-shots…"
  chop_drums "$stemdir/drums.wav" "$MUSIC_DIR/Samples/One-Shots" "$dens" | tail -1
  echo "→ Sorting kit (kick/snare/hat)…"
  sort_kit "$MUSIC_DIR/Samples/One-Shots/$track"
  echo "→ Stem presence & loudness…"
  analyze_stems "$stemdir" >/dev/null
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
  # Capture the decimal too, then round — catalog stores bpm as INTEGER, and
  # truncating 93.5 to 93 loses the nearer value.
  _bpm=$(print -r -- "$_analysis" | sed -nE 's/.*[^0-9]([0-9]{2,3}(\.[0-9]+)?)[[:space:]]*BPM.*/\1/p' | head -1)
  _bpm=${_bpm:+$(printf '%.0f' "$_bpm")}
  _key=$(print -r -- "$_analysis" | sed -nE 's/.*[Kk]ey[[:space:]]+([A-Ga-g][b#]?m?).*/\1/p' | head -1)
  if [[ -x "$MUSIC_DIR/.venv/bin/python" ]]; then
    "$MUSIC_DIR/.venv/bin/python" "$MUSIC_DIR/Scripts/catalog.py" index-track "$track" ${_bpm:+--bpm $_bpm} ${_key:+--key $_key} >/dev/null 2>&1
  fi
  # Apple's bar grid, so the track is mixable. Reported rather than swallowed:
  # without it mix_render has nothing to cut on, and a silent skip would leave
  # that discoverable only when a mix is attempted much later.
  echo "→ Bar grid & loop candidates…"
  if apple_analyze "$file"; then
    echo "  Loop candidates: catalog.py regions \"$track\""
    # Publishing is the phone's only source. Reported either way: a deconstruct
    # that quietly did not publish looks identical to one that did, and the
    # container legitimately does not exist yet.
    if icloud_container >/dev/null; then
      echo "→ Publishing to iCloud…"
      publish_to_icloud "$track" || echo "  (publish failed -- the stems stayed local)" >&2
    else
      echo "  (no iCloud container yet -- nothing published; R4b in STATUS)"
    fi
  else
    echo "  (no bar grid -- mix-render will not accept this track yet)" >&2
  fi
}
