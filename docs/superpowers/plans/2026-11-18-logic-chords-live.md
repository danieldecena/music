# Plan: get Logic's chords live again (2026-11-18)

Goal: WALKING AWAY on the phone with Logic's chords and a start time, and Logic's
chord step working for every new song again. Findings so far: STATUS.md, Known
broken, first entry.

## Done when

- A scratch copy of DAISIES run through `logic_chords.py` gives the same chord
  changes as the saved `02 DAISIES logic.tsv` from 11-17 morning (the control).
- `10 WALKING AWAY chords.txt` starts with Logic's source line and has a
  `start <s> s` on its tempo line, and the iCloud copy matches it.
- On the phone, opening Chordbook shows "New chords from the Mac: 10 WALKING AWAY".

## Steps

1. **See the menu.** Rerun the scratchpad probe on the DAISIES copy (it now answers
   Logic's sample-rate question while waiting), screenshot the hidden screen right
   after AXShowMenu, and dump every AXMenu in the window and at the process's top
   level. Answers: does a menu open at all, where does it appear, and what is it called.
2. **Check Logic's right-click setting.** Logic > Settings > General > Editing,
   "Right Mouse Button". It must open the shortcut menu. Read it through accessibility;
   if it changed, Daniel sets it back (his app setting, not changed by Claude).
3. **Fix the menu step** in `Scripts/logic_chords.py` to match what step 1 shows
   (where the menu is searched for, its name, how long to wait). Add a pure test
   where the change allows; run `tests/test-logic-chords.py` and `tests/test-core.sh`.
4. **Prove it on the control.** DAISIES copy in the scratchpad; compare against the
   saved `logic.tsv`. A mismatch means the fix is wrong, not the song.
5. **Run WALKING AWAY** through `logic_chords` in `lib/music-core.sh` (Logic's chords,
   line-up to the beat, publish to Chordbook Songs). Check the chart header and the
   iCloud copy.
6. **Daniel, on the phone:** open Chordbook, look for the "New chords from the Mac"
   alert, play WALKING AWAY with Strum on and check it sits on the guitar.

## Not in this plan

- **TestFlight.** Build 8 already has the song-refresh code, so new charts reach the
  phone without a new build. A build 9 is only needed when the app itself changes,
  such as the Lyrics tab on its own branch, which is Daniel's call to ship.

## Rules that apply

- Logic only on the hidden screen, never brought to the front; quit only a Logic this
  script opened.
- Each Logic run is about two minutes: one run per question, no blind reruns.
