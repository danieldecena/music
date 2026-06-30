# Music Production Folder Structure

**Date:** 2026-06-29
**DAW:** Logic Pro (.logicx bundles)
**Workflow:** Sample-based + original beats, multiple genres

## Structure

```
~/Developer/music/
  Projects/
    Active/       ← in-progress Logic project bundles
    Archive/      ← finished or shelved projects
    Templates/    ← blank Logic starters per genre/mood
  Samples/
    One-Shots/    ← single hits: drums, FX, foley
    Loops/        ← drum and melodic loops
    Chops/        ← pre-chopped material ready to drop into Logic
    Kits/         ← organized drum kits (folder per kit)
  Stems/          ← demucs output (already exists, auto-populated by stems.sh)
  Exports/
    Drafts/       ← WIP bounces for feedback
    Finals/       ← mastered or release-ready files
  References/     ← A/B reference tracks for mixing sessions
  Apple Music/    ← downloaded source music (already exists)
  Scripts/        ← automation scripts (download.sh, stems.sh)
```

## Rules

- One `.logicx` bundle per beat in `Projects/Active/`. Move to `Archive/` when done.
- `Samples/Chops/` is for processed material only — raw downloads stay in `Apple Music/`, stems stay in `Stems/`.
- `Exports/Finals/` is write-once — never overwrite a final, version with a suffix if needed (e.g. `beat-name-v2.wav`).
- `References/` holds full tracks only, not loops or one-shots.
