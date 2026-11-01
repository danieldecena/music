#!/usr/bin/env zsh
# Failure reporting: each check pairs a broken input with a good one, so a step
# that always fails and a step that never reports both show up here.
#   zsh tests/test-pipeline.sh
REPO="${0:A:h:h}"
source "$REPO/lib/music-core.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
PY="$REPO/.venv/bin/python"
pass=0; fail=0
check() { if eval "$2"; then ((pass++)); print "ok: $1"; else ((fail++)); print "FAIL: $1"; fi; }
tone() { ffmpeg -nostdin -y -v error -f lavfi -i "$1" -t "$2" "$3"; }

# clean_path
[[ "$(clean_path 'a/Don\'"'"'t\ \(x\).m4a ')" == "a/Don't (x).m4a" ]]; check "dragged path unescapes quote and parens" "(( $? == 0 ))"
[[ "$(clean_path "a/Don't (x).m4a")" == "a/Don't (x).m4a" ]]; check "typed path stays as typed" "(( $? == 0 ))"

# download_and_locate keeps downloader output out of the file list
REAL_MUSIC_DIR="$MUSIC_DIR"; MUSIC_DIR="$TMP/dl"; mkdir -p "$MUSIC_DIR/am"
download_url() { echo "[download] 100% noise"; sleep 1; print x > "$2/song.m4a"; }
got=$(download_and_locate u "$MUSIC_DIR/am" 2>/dev/null); rc=$?
check "file list holds only the new file" '[[ "$got" == "$MUSIC_DIR/am/song.m4a" && $rc == 0 ]]'
download_url() { return 7; }
download_and_locate u "$MUSIC_DIR/am" >/dev/null 2>&1; rc=$?
check "a failed download is reported" '(( rc == 7 ))'

# deconstruct, with its steps stubbed and a fake catalog recording its arguments
MUSIC_DIR="$TMP/dc"; mkdir -p "$MUSIC_DIR/.venv/bin"; print x > "$TMP/s.m4a"
print -l '#!/bin/sh' 'printf "%s\n" "$@" > "'$TMP'/args"' > "$MUSIC_DIR/.venv/bin/python"; chmod +x "$MUSIC_DIR/.venv/bin/python"
analyze_track() { print "s.m4a: 93.4 BPM key Am"; }
separate_stems() { :; }; chop_drums() { print shots; }; sort_kit() { :; }; analyze_stems() { :; }
chop_stems() { :; }; chop_vocals() { :; }; apple_analyze() { return 1; }; icloud_container() { return 1; }
out=$(deconstruct "$TMP/s.m4a" 2>&1); rc=$?
check "clean run says complete" '[[ "$out" == *"Deconstruct complete"* ]]'
check "bpm reaches the catalog as two arguments" 'grep -qx -- --bpm "$TMP/args" && grep -qx 93 "$TMP/args"'
check "key reaches the catalog as two arguments" 'grep -qx -- --key "$TMP/args" && grep -qx Am "$TMP/args"'
for step in chop_drums sort_kit chop_stems chop_vocals analyze_track; do
  functions[orig]=$functions[$step]; functions[$step]='return 1'
  out=$(deconstruct "$TMP/s.m4a" 2>&1); rc=$?
  check "failing $step is not called complete" '(( rc == 1 )) && [[ "$out" != *"Deconstruct complete"* && "$out" == *"incomplete"* ]]'
  functions[$step]=$functions[orig]
done
MUSIC_DIR="$REAL_MUSIC_DIR"; source "$REPO/lib/music-core.sh"

# chop.py: trailing silence is not part of the last clip
mkdir -p "$TMP/c1" "$TMP/c2"
ffmpeg -nostdin -y -v error -f lavfi -i "sine=440:d=5" -f lavfi -i "anullsrc=r=44100:cl=mono:d=3" -filter_complex "[0:a]aresample=44100,aformat=channel_layouts=mono[a];[a][1:a]concat=n=2:v=0:a=1" "$TMP/tail.wav"
tone "sine=440" 5 "$TMP/plain.wav"
"$PY" "$REPO/Scripts/chop.py" "$TMP/tail.wav" "$TMP/c1" >/dev/null
"$PY" "$REPO/Scripts/chop.py" "$TMP/plain.wav" "$TMP/c2" >/dev/null
dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
f1=$(find "$TMP/c1" -name '*.wav' | head -1); f2=$(find "$TMP/c2" -name '*.wav' | head -1)
check "clip stops where the silence starts" '[[ -n "$f1" ]] && (( $(dur "$f1") < 6 ))'
check "a song with no trailing silence keeps its length" '[[ -n "$f2" ]] && (( $(dur "$f2") > 4.5 ))'

# slice_drums.py: a slice that cannot be written is not listed as saved
ffmpeg -nostdin -y -v error -f lavfi -i "sine=200:d=0.2,apad=pad_dur=0.3,aloop=loop=8:size=22050" -ar 44100 "$TMP/drums.wav"
"$PY" "$REPO/Scripts/slice_drums.py" "$TMP/drums.wav" "$TMP/ok" >/dev/null 2>&1; rc=$?
n=$(find "$TMP/ok" -name '*.wav' | wc -l)
check "good slices exit 0 and exist" '(( rc == 0 && n > 0 ))'
mkdir -p "$TMP/bad/${TMP:t}/drums_001.wav"
"$PY" "$REPO/Scripts/slice_drums.py" "$TMP/drums.wav" "$TMP/bad" >"$TMP/o" 2>&1; rc=$?
check "failed slice exits 1 and is named" '(( rc == 1 )) && grep -q "FAILED" "$TMP/o"'

# sort_drums.py: unreadable hits stay out of the kit
mkdir -p "$TMP/k1" "$TMP/k2"
for i in 1 2 3; do tone "sine=$((i*700)):d=0.2" 0.2 "$TMP/k1/h$i.wav"; tone "sine=$((i*700)):d=0.2" 0.2 "$TMP/k2/h$i.wav"; done
print junk > "$TMP/k2/bad.wav"
"$PY" "$REPO/Scripts/sort_drums.py" "$TMP/k1" >/dev/null 2>&1; rc=$?
check "readable kit sorts and exits 0" '(( rc == 0 )) && (( $(find "$TMP/k1" -mindepth 2 -name "*.wav" | wc -l) == 3 ))'
"$PY" "$REPO/Scripts/sort_drums.py" "$TMP/k2" >"$TMP/o" 2>&1; rc=$?
check "unreadable hit exits 1 and is named" '(( rc == 1 )) && grep -q "not sorted: bad.wav" "$TMP/o"'
check "unreadable hit is not filed" '[[ -z "$(find "$TMP/k2" -mindepth 2 -name bad.wav)" ]]'
check "readable hits still filed beside it" '(( $(find "$TMP/k2" -mindepth 2 -name "*.wav" | wc -l) == 3 ))'

# chop_stems reports any failed stem, not just the last
mkdir -p "$TMP/st/t"; tone "sine=300" 1 "$TMP/st/t/bass.wav"; tone "sine=300" 1 "$TMP/st/t/vocals.wav"
chop_stems "$TMP/st/t" "$TMP/so" 1 >/dev/null 2>&1; rc=$?
check "good stems exit 0" '(( rc == 0 ))'
print junk > "$TMP/st/t/bass.wav"
chop_stems "$TMP/st/t" "$TMP/so2" 1 >/dev/null 2>&1; rc=$?
check "an early bad stem still fails" '(( rc != 0 ))'

# stems.sh keeps going past a bad file
mkdir -p "$TMP/batch"; print junk > "$TMP/batch/a.wav"; print junk > "$TMP/batch/b.wav"
out=$(printf '%s\n1\n' "$TMP/batch" | zsh "$REPO/stems.sh" 2>&1); rc=$?
check "batch tries every file" '[[ "$out" == *"Processing: a.wav"* && "$out" == *"Processing: b.wav"* ]]'
check "batch reports failures and exits 1" '(( rc == 1 )) && [[ "$out" == *"2 file(s) failed"* && "$out" != *"Done."* ]]'

# unreadable audio gets a plain message, not a traceback
"$PY" "$REPO/Scripts/chop.py" "$TMP/batch/a.wav" "$TMP/j1" >"$TMP/o" 2>&1; rc=$?
check "chop names unreadable audio" '(( rc == 1 )) && grep -q "Cannot read audio" "$TMP/o" && ! grep -q Traceback "$TMP/o"'
"$PY" "$REPO/Scripts/slice_drums.py" "$TMP/batch/a.wav" "$TMP/j2" >"$TMP/o" 2>&1; rc=$?
check "slice names unreadable audio" '(( rc == 1 )) && grep -q "Cannot read audio" "$TMP/o" && ! grep -q Traceback "$TMP/o"'

# stem levels label an unreadable stem, and a good one normally
mkdir -p "$TMP/lv"; print junk > "$TMP/lv/bad.wav"; tone "sine=300" 1 "$TMP/lv/good.wav"
analyze_stems "$TMP/lv" >"$TMP/o" 2>&1
check "unreadable stem is labelled" 'grep -E "^bad " "$TMP/o" | grep -q unreadable'
check "good stem is not labelled unreadable" 'grep -E "^good " "$TMP/o" | grep -qv unreadable'

# lookups: a real "none" stays quiet, an outage says so; the oracle keeps no bad cache
"$PY" - "$REPO/Scripts" >"$TMP/o" 2>"$TMP/e" <<'PYEOF'
import sys, io, urllib.error, urllib.request, subprocess, types
sys.path.insert(0, sys.argv[1])
import lyrics, key_oracle
lyrics.CACHE_DIR = __import__("pathlib").Path("/nonexistent/lyr")
def raiser(exc):
    def f(*a, **k): raise exc
    return f
urllib.request.urlopen = raiser(urllib.error.HTTPError("u", 404, "nf", {}, None))
print("L404", lyrics.fetch_lyrics("a", "t1"))
urllib.request.urlopen = raiser(urllib.error.URLError("down"))
print("LDOWN", lyrics.fetch_lyrics("a", "t2"))
subprocess.run = lambda *a, **k: types.SimpleNamespace(returncode=22, stdout="", stderr="HTTP 500")
try:
    key_oracle._fetch("q"); print("ORACLE no-raise")
except RuntimeError:
    print("ORACLE raised")
subprocess.run = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="page", stderr="")
print("ORACLEOK", key_oracle._fetch("q"))
PYEOF
check "404 is quiet no-lyrics" 'grep -q "L404 None" "$TMP/o" && ! grep -q t1 "$TMP/e"'
check "outage is reported" 'grep -q "LDOWN None" "$TMP/o" && grep -q "lookup failed for t2" "$TMP/e"'
check "oracle failed fetch raises" 'grep -q "ORACLE raised" "$TMP/o"'
check "oracle good fetch returns the page" 'grep -q "ORACLEOK page" "$TMP/o"'

# the menu exits when its input closes
out=$(zsh -c 'cd "$1"; ./music </dev/null | head -2000 | wc -l' _ "$REPO")
check "menu exits at end of input" '(( out < 100 ))'

print "\n$pass passed, $fail failed"
(( fail == 0 ))
