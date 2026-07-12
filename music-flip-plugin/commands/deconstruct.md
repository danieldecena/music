---
description: Deconstruct an existing track into stems, one-shots, kit, and chops
argument-hint: <file-path> [tight|loose]
---

Deconstruct the local audio file `$1` using `/Users/home/Developer/music`, via Desktop Commander:

`cd '/Users/home/Developer/music' && source lib/music-core.sh && deconstruct '$1' ${2:-loose}`

Wait for `✓ Deconstruct complete`, then report the estimated BPM/key and where the outputs landed (Stems, One-Shots + sorted kit, Chops, Vocals). See the `flip-track` skill for the manual step-by-step variant.
