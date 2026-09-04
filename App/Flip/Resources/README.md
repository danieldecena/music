# Bundled test clip

`testclip.m4a` is deliberately **not committed** — it is 30 seconds of a
copyrighted track, and this repo gitignores audio everywhere else.

Regenerate it before building:

```sh
ffmpeg -loglevel error -y -ss 60 -t 30 -vn \
  -i "Apple Music/Frank Ocean/Blonde/02 Ivy.m4a" \
  -c:a aac -b:a 128k App/Flip/Resources/testclip.m4a
```

`-vn` is load-bearing. The source `.m4a` carries embedded artwork as an h264
stream, and without it the ipod muxer writes a **zero-byte file** while the
error scrolls past. An empty result hashes to `e3b0c442...`; check the hash,
not the exit code.

The reference reading for that exact clip (sha `1552377b9407a32754e56e85`),
from `Tools/mu-analyze` on the Mac:

    BPM 116.598, 58 beats, 14 bars, key C major

The device must reproduce the BPM and bar count. **Section count is platform-
split, not a bug**: macOS reports 3 sections for this clip, iOS reports 2 —
`LoopScorerTests.swift` fixes its sections by hand for exactly this reason
rather than reading them off a device run. A device showing 2 sections is a
correct build, not a failed check. BPM and bars merely appearing on screen are
still not the check — a plausible wrong number is the failure that catches.

Regenerate the matching lyrics file the same way:

```sh
.venv/bin/python -c "
import sys; sys.path.insert(0,'Scripts')
from lyrics import timed_lrc
rows = timed_lrc(open('Apple Music/Frank Ocean/Blonde/02 Ivy.lrc').read())
for s,e,t in rows:
    if 60.0 <= s < 90.0:
        s -= 60.0
        print(f'[{int(s//60):02d}:{s%60:05.2f}]{t}')
" > App/Flip/Resources/testclip.lrc
```
