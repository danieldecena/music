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

assert_eq "$(stem_mode_args instrumental)" "--two-stems=vocals" "instrumental mode"
assert_eq "$(stem_mode_args 4stem)" "" "4stem mode"
assert_eq "$(stem_mode_args 6stem)" "-n htdemucs_6s" "6stem mode"
assert_eq "$(chop_sensitivity_args tight)" "--min-silence 0.15 --min-clip 0.3" "tight sensitivity"
assert_eq "$(chop_sensitivity_args loose)" "--min-silence 0.35 --min-clip 0.8" "loose sensitivity"

# find_new_m4a: 2020 file is old, 2099 file is new, stamp is 2050 (epoch 2524608000)
tmp=$(mktemp -d)
touch -t 202001010000 "$tmp/old.m4a"
touch -t 209901010000 "$tmp/new.m4a"
result=$(find_new_m4a "$tmp" 2524608000)
assert_eq "${result:t}" "new.m4a" "find_new_m4a returns only files after stamp"
rm -rf "$tmp"

exit $fail
