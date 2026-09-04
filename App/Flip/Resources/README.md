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

    BPM 116.598, 58 beats, 14 bars, 3 sections, key C major

The device must reproduce those numbers. A number merely appearing on screen is
not the check — a plausible wrong one is the failure this catches.
