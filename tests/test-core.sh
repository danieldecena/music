#!/usr/bin/env zsh
source "${0:A:h}/../lib/music-core.sh"

fail=0
assert_eq() {
  if [[ "$1" != "$2" ]]; then
    echo "FAIL ($3): expected [$2] got [$1]"; fail=1
  else
    echo "ok: $3"
  fi
}

assert_eq "$(stem_profile_args acapella)" "--two-stems=vocals" "acapella profile args"
assert_eq "$(stem_profile_args fast)" "" "fast profile args"
assert_eq "$(stem_profile_args 6stem)" "-n htdemucs_6s" "6stem profile args"
assert_eq "$(stem_profile_args hq)" "-n htdemucs_6s --shifts 2 --overlap 0.5" "hq profile args"
assert_eq "$(stem_profile_model acapella)" "htdemucs" "acapella model dir"
assert_eq "$(stem_profile_model fast)" "htdemucs" "fast model dir"
assert_eq "$(stem_profile_model 6stem)" "htdemucs_6s" "6stem model dir"
assert_eq "$(stem_profile_model hq)" "htdemucs_6s" "hq model dir"
stem_profile_args bogus 2>/dev/null; assert_eq "$?" "1" "unknown profile args errors"
stem_profile_model bogus 2>/dev/null; assert_eq "$?" "1" "unknown profile model errors"
assert_eq "$(chop_sensitivity_args tight)" "--min-silence 0.15 --min-clip 0.3" "tight sensitivity"
assert_eq "$(chop_sensitivity_args loose)" "--min-silence 0.35 --min-clip 0.8" "loose sensitivity"
assert_eq "$(drum_split_args tight)" "--delta 0.04 --wait 0.05" "tight drum density"
assert_eq "$(drum_split_args loose)" "--delta 0.09 --wait 0.12" "loose drum density"
assert_eq "$(stem_presence_label -30 -2)" "present" "present loudness"
assert_eq "$(stem_presence_label -77.3 -26.2)" "faint" "faint loudness"
assert_eq "$(stem_presence_label -60 -55)" "silent" "silent loudness"
assert_eq "$(stem_presence_label -46 -50)" "faint" "peak -50 is not silent (boundary)"

# find_new_m4a: 2020 file is old, 2099 file is new, stamp is 2050 (epoch 2524608000)
tmp=$(mktemp -d)
touch -t 202001010000 "$tmp/old.m4a"
touch -t 209901010000 "$tmp/new.m4a"
result=$(find_new_m4a "$tmp" 2524608000)
assert_eq "${result:t}" "new.m4a" "find_new_m4a returns only files after stamp"
rm -rf "$tmp"

# stems_dir_for: prefers htdemucs, falls back to htdemucs_6s, empty when none
MUSIC_DIR=$(mktemp -d)
mkdir -p "$MUSIC_DIR/Stems/htdemucs_6s/Song"
assert_eq "$(stems_dir_for Song)" "$MUSIC_DIR/Stems/htdemucs_6s/Song" "stems_dir_for falls back to 6s"
mkdir -p "$MUSIC_DIR/Stems/htdemucs/Song"
assert_eq "$(stems_dir_for Song)" "$MUSIC_DIR/Stems/htdemucs/Song" "stems_dir_for prefers htdemucs"
assert_eq "$(stems_dir_for Missing)" "" "stems_dir_for empty when none"
rm -rf "$MUSIC_DIR"

# track_state: "stems drums shots kit chops"
MUSIC_DIR=$(mktemp -d)
assert_eq "$(track_state Song)" "0 0 0 0 0" "track_state all zero when nothing exists"
mkdir -p "$MUSIC_DIR/Stems/htdemucs/Song"
touch "$MUSIC_DIR/Stems/htdemucs/Song/vocals.wav" "$MUSIC_DIR/Stems/htdemucs/Song/no_vocals.wav"
assert_eq "$(track_state Song)" "1 0 0 0 0" "acapella split has stems but no drums"
# the drums live in the 6s dir that stems_dir_for does NOT prefer — still found
mkdir -p "$MUSIC_DIR/Stems/htdemucs_6s/Song"
touch "$MUSIC_DIR/Stems/htdemucs_6s/Song/drums.wav"
assert_eq "$(track_state Song)" "1 1 0 0 0" "drums found in the non-preferred model dir"
mkdir -p "$MUSIC_DIR/Samples/One-Shots/Song"
touch "$MUSIC_DIR/Samples/One-Shots/Song/drums_001.wav"
assert_eq "$(track_state Song)" "1 1 1 0 0" "one-shots detected"
mkdir -p "$MUSIC_DIR/Samples/One-Shots/Song/kick"
assert_eq "$(track_state Song)" "1 1 1 0 0" "empty kick/ is not a sorted kit"
touch "$MUSIC_DIR/Samples/One-Shots/Song/kick/kick_001.wav"
assert_eq "$(track_state Song)" "1 1 1 1 0" "populated kick/ is a sorted kit"
mkdir -p "$MUSIC_DIR/Samples/Chops/Song/other"
touch "$MUSIC_DIR/Samples/Chops/Song/other/other_001.wav"
assert_eq "$(track_state Song)" "1 1 1 1 1" "chops detected"
# glob metachars in the title must not be read as a pattern
mkdir -p "$MUSIC_DIR/Samples/One-Shots/Rambo [feat. X] (Live)"
touch "$MUSIC_DIR/Samples/One-Shots/Rambo [feat. X] (Live)/hit_001.wav"
assert_eq "$(track_state 'Rambo [feat. X] (Live)')" "0 0 1 0 0" "brackets in a title are literal"
rm -rf "$MUSIC_DIR"

# --- icloud_container / publish_to_icloud -----------------------------------
# HOME is redirected so the real container, if this Mac ever has one, cannot
# decide the result. A test whose outcome depends on the machine's iCloud state
# proves nothing about the code.
MUSIC_DIR=$(mktemp -d)
real_home="$HOME"
HOME=$(mktemp -d)
unset MUSIC_ICLOUD_DIR

icloud_container >/dev/null 2>&1
assert_eq "$?" "1" "icloud_container fails when there is no container"

cloud=$(mktemp -d)
MUSIC_ICLOUD_DIR="$cloud"
assert_eq "$(icloud_container)" "$cloud" "MUSIC_ICLOUD_DIR overrides the container path"

# A path-shaped name must be refused BEFORE anything is deleted: the destination
# is rsync --delete'd, so "../.." would prune outside the container.
publish_to_icloud "../../etc" >/dev/null 2>&1
assert_eq "$?" "2" "a path-shaped track name is refused"
publish_to_icloud "" >/dev/null 2>&1
assert_eq "$?" "2" "an empty track name is refused"

publish_to_icloud Song >/dev/null 2>&1
assert_eq "$?" "1" "no stems is a failure, not a silent success"

mkdir -p "$MUSIC_DIR/Stems/htdemucs/Song"
touch "$MUSIC_DIR/Stems/htdemucs/Song/drums.wav" "$MUSIC_DIR/Stems/htdemucs/Song/bass.wav"
publish_to_icloud Song >/dev/null 2>&1
assert_eq "$?" "1" "stems without an analysis is a failure"

mkdir -p "$MUSIC_DIR/Samples/Analysis"
echo '{"result":{}}' > "$MUSIC_DIR/Samples/Analysis/Song.json"
publish_to_icloud Song >/dev/null
assert_eq "$?" "0" "a track with stems and an analysis publishes"
assert_eq "$(ls "$cloud/Tracks/Song" | tr '\n' ' ')" "analysis.json bass.wav drums.wav " \
  "the stems and the analysis both land"

# A republish after a different stem profile must not leave the old model's
# stems behind for the phone to show as real.
rm "$MUSIC_DIR/Stems/htdemucs/Song/bass.wav"
publish_to_icloud Song >/dev/null
assert_eq "$(ls "$cloud/Tracks/Song" | tr '\n' ' ')" "analysis.json drums.wav " \
  "a republish prunes a stem the source no longer has"

# Glob metacharacters in a title are a name, not a pattern -- the same trap
# track_state carries a test for.
mkdir -p "$MUSIC_DIR/Stems/htdemucs/Rambo [feat. X]"
touch "$MUSIC_DIR/Stems/htdemucs/Rambo [feat. X]/drums.wav"
echo '{"result":{}}' > "$MUSIC_DIR/Samples/Analysis/Rambo [feat. X].json"
publish_to_icloud "Rambo [feat. X]" >/dev/null
assert_eq "$?" "0" "brackets in a title publish literally"

HOME="$real_home"
unset MUSIC_ICLOUD_DIR
rm -rf "$MUSIC_DIR" "$cloud" 

exit $fail
