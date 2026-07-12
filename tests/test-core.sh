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

exit $fail
