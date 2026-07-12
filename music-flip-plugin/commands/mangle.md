---
description: Fan a sample (or folder) out into transformed flip-fuel variants
argument-hint: <sample.wav-or-folder> [transforms] 
---

Generate transformed variants of `$1` using the music toolkit at `/Users/home/Developer/music`, via Desktop Commander:

`cd '/Users/home/Developer/music' && source lib/music-core.sh && mangle '$1' '$2'`

`$1` is a sample `.wav` or a folder of samples (e.g. `Samples/Chops/09 Rambo/other`). `$2` is an optional comma-separated transform list (default = all): `halfspeed,pitchdown,pitchup,reverse,freeze,stutter,bitcrush,tape,smear,telephone,conv`.

Output lands in `Samples/Mangled/<track>/<stem>_<variant>.wav`. After it runs, refresh the catalog (`.venv/bin/python Scripts/catalog.py scan`) and report what was created, then remind Daniel he can audition them in the Music Studio artifact's Mangled tab. See the `flip-track` skill for the full pipeline.
