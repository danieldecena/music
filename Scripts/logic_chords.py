#!/opt/homebrew/bin/python3
"""Chords for a song from Logic Pro's Chord ID, written as the song's chords.txt.

Opens the song in Logic (on the hidden screen), runs Apply Region Chords to Chord Track
(Ctrl-Opt-Shift-Cmd-C in Logic's Key Commands) on it (Chord ID analyzes the song as it goes) and reads every chord with its position from
the accessibility tree. The chords are laid on the grid of the chart already beside the song (its tempo and bar count, so
nudges made against it still hold), one chord per bar: the one that sounds longest in it.
The old chart is kept as "<name> chords (script).txt" the first time.

Logic stays in the background except for one second while its shortcut is sent: it ignores
menus and keys while inactive. Every other step is an accessibility action.
With the BetterDisplay hidden screen connected, Logic's window is moved there.

Usage: logic_chords.py "<song>.m4a"
Exit 1 when Logic is already open (the song would be added to your project), when there is no
chart beside the song to take the grid from, or when any Logic step does not happen.
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

APP = "Logic Pro Creator Studio"
APP_PATH = f"/Applications/{APP}.app"
VDISPLAY = Path.home() / "Bin/vdisplay.sh"
SCRIPTS = Path(__file__).resolve().parent
VENV_PYTHON = SCRIPTS.parent / ".venv/bin/python"
ALIGN = SCRIPTS / "align_chart.py"
SOURCE_NOTE = "# chords from Logic Pro Chord ID"
TICKS_PER_BEAT = 960

_NOTES = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
_SPELLING = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Logic's spoken qualities. "major 7" is the dominant seventh; "major major 7" the major seventh.
_QUALITIES = {
    "major": "",
    "minor": "m",
    "major 7": "7",
    "major major 7": "maj7",
    "minor 7": "m7",
    "major 6": "6",
    "minor 6": "m6",
    "7 sus4": "7sus4",
}
_POSITION = re.compile(
    r"(\d+) bars?(?: (\d+) beats?)?(?: (\d+) divisions?)?(?: (\d+) ticks?)?"
)


def item_seconds(position: str, bpm: float) -> float:
    """Seconds from the start for a Chord Track position such as "3 bars 4 beats 2 ticks"."""
    m = _POSITION.fullmatch(position.strip())
    if not m:
        raise ValueError(f"unreadable Chord Track position: {position!r}")
    bar = int(m.group(1))
    beat, division, tick = (int(g) if g else None for g in m.groups()[1:])
    beats = (bar - 1) * 4 + ((beat or 1) - 1) + ((division or 1) - 1) / 4
    return (beats + (tick or 0) / TICKS_PER_BEAT) * 60 / bpm


def split_item(description: str) -> tuple[str, str]:
    """A chord item's description into its spoken chord name and its position."""
    m = re.match(r"(.+?) (\d+ bars?\b.*)$", description.strip())
    if not m or description.startswith("chord group"):
        raise ValueError(f"not a Chord Track chord item: {description!r}")
    return m.group(1), m.group(2)


def _note(words: list[str]) -> tuple[int, list[str]]:
    if not words or words[0] not in _NOTES:
        raise ValueError(f"no note name in {' '.join(words)!r}")
    pc, rest = _NOTES[words[0]], words[1:]
    if rest[:1] == ["sharp"]:
        pc, rest = pc + 1, rest[1:]
    elif rest[:1] == ["flat"]:
        pc, rest = pc - 1, rest[1:]
    return pc % 12, rest


def chord_name(spoken: str) -> str:
    """Logic's spoken chord ("e flat major major 7", "g minor 7/d") in the chart's spelling."""
    if spoken == "No Chord":
        return "-"
    chord, _, bass = spoken.partition("/")
    root, rest = _note(chord.split())
    quality = " ".join(rest)
    if quality not in _QUALITIES:
        raise ValueError(
            f"chord quality Logic named that this script does not know: {spoken!r}"
        )
    name = _SPELLING[root] + _QUALITIES[quality]
    if bass:
        pc, left = _note(bass.split())
        if left:
            raise ValueError(f"unreadable bass note in {spoken!r}")
        name += "/" + _SPELLING[pc]
    return name


def bar_labels(
    changes: list[tuple[float, str]], bpm: float, bars: int, start: float = 0.0
) -> list[str]:
    """One chord per bar on a steady 4/4 grid from `start` seconds: the one sounding longest in it."""
    bar_len = 4 * 60 / bpm
    spans = [
        (at, changes[i + 1][0] if i + 1 < len(changes) else float("inf"), name)
        for i, (at, name) in enumerate(changes)
    ]
    labels = []
    for b in range(bars):
        lo, hi = start + b * bar_len, start + (b + 1) * bar_len
        best, best_len = "-", 0.0
        for begin, end, name in spans:
            overlap = min(hi, end) - max(lo, begin)
            if overlap > best_len:
                best, best_len = name, overlap
        labels.append(best)
    return labels


def bar_halves(
    changes: list[tuple[float, str]], bpm: float, bars: int, start: float = 0.0
) -> tuple[list[str], dict[int, str]]:
    """Like bar_labels, but a bar whose two halves play different chords (each for at least a
    beat) keeps the first half's chord and gets the second half's as a change on beat 3, keyed
    by bar index. DAISIES plays two chords a bar; one chord per bar dropped half of them."""
    bar_len = 4 * 60 / bpm
    beat = bar_len / 4
    spans = [
        (at, changes[i + 1][0] if i + 1 < len(changes) else float("inf"), name)
        for i, (at, name) in enumerate(changes)
    ]

    def longest(lo: float, hi: float) -> tuple[str, float]:
        best, best_len = "-", 0.0
        for begin, end, name in spans:
            overlap = min(hi, end) - max(lo, begin)
            if overlap > best_len:
                best, best_len = name, overlap
        return best, best_len

    labels, mids = [], {}
    for b in range(bars):
        lo = start + b * bar_len
        first, first_len = longest(lo, lo + bar_len / 2)
        second, second_len = longest(lo + bar_len / 2, lo + bar_len)
        if first != second and first_len >= beat - 1e-9 and second_len >= beat - 1e-9:
            labels.append(first)
            mids[b] = second
        else:
            labels.append(longest(lo, lo + bar_len)[0])
    return labels, mids


def read_grid(chart: str) -> tuple[str, str, float, int, float]:
    """Title line, key, tempo, bar count and bar 1's start (seconds) of an existing chords.txt."""
    title = next(
        (l for l in chart.splitlines() if "Chords --" in l), "# Chords -- untitled"
    )
    m = re.search(r"key\s+(\S+)\s+([0-9.]+)\s*BPM", chart)
    rows = [
        int(l.split()[0]) for l in chart.splitlines() if re.match(r"\s*\d+\s+\S", l)
    ]
    if not m or not rows:
        raise ValueError("the chart has no tempo line or no bars")
    started = re.search(r"start\s+([0-9.]+)\s*s\b", chart)
    return (
        title,
        m.group(1),
        float(m.group(2)),
        max(rows),
        float(started.group(1)) if started else 0.0,
    )


def chart_text(
    grid: tuple[str, str, float, int, float],
    labels: list[str],
    mids: dict[int, str] | None = None,
) -> str:
    title, key, bpm, bars, start = grid
    tempo = f"# key {key}  {bpm} BPM  {bars} bars" + (
        f"  start {start:.3f} s" if start else ""
    )
    lines = [title, tempo, SOURCE_NOTE]
    for i, c in enumerate(labels, 1):
        lines.append(f"{i}\t{c}")
        # "5.3<TAB>Fm": the chord changes on beat 3 of bar 5. Older Chordbook builds skip the line.
        if mids and i - 1 in mids:
            lines.append(f"{i}.3\t{mids[i - 1]}")
    return "\n".join(lines) + "\n"


def save_changes(path: Path, changes: list[tuple[float, str]]) -> None:
    """Logic's chord changes as seconds<TAB>chord, so the chart can be laid again without Logic."""
    path.write_text("".join(f"{t:.3f}\t{c}\n" for t, c in changes))


def load_changes(path: Path) -> list[tuple[float, str]]:
    rows = [line.split("\t") for line in path.read_text().splitlines() if line.strip()]
    return [(float(t), c) for t, c in rows]


# --- Driving Logic -------------------------------------------------------------------------

_AX = r"""
on findEl(el, r, d, depth)
  if depth > 11 then return missing value
  tell application "System Events"
    try
      set kids to every UI element of el
    on error
      return missing value
    end try
    repeat with k in kids
      try
        if (role of k) is r and ((description of k as string) is d or (name of k as string) is d) then return k
      end try
      set f to my findEl(k, r, d, depth + 1)
      if f is not missing value then return f
    end repeat
  end tell
  return missing value
end findEl

-- Logic can open an empty project of its own beside the song's, so every step works in the
-- window main() found holding the song's region (LOGIC_CHORDS_WINDOW), not whichever is first.
on trackWin()
  set n to system attribute "LOGIC_CHORDS_WINDOW"
  tell application "System Events" to tell process "__APP__"
    if n is not "" then return first window whose name is n
    return first window whose name ends with "- Tracks"
  end tell
end trackWin

on frontName()
  tell application "System Events" to return name of first process whose frontmost is true
end frontName

on refront(n)
  tell application "System Events" to set frontmost of process n to true
end refront

on run argv
  set act to item 1 of argv
  tell application "System Events" to tell process "__APP__"
    if act is "windows" then
      set out to ""
      repeat with w in every window
        -- A window can close mid-list (a dialog answered, a quit); skip it rather than fail.
        try
          set winText to (subrole of w) & tab & (name of w as string) & tab
          repeat with e in (every UI element of w)
            try
              if role of e is "AXButton" then set winText to winText & "[" & (name of e as string) & "]"
              if role of e is "AXStaticText" then set winText to winText & (value of e as string) & " "
            end try
          end repeat
          set out to out & winText & linefeed
        end try
      end repeat
      return out
    else if act is "press" then
      repeat with w in every window
        try
          click button (item 2 of argv) of w
          return "pressed"
        end try
      end repeat
      return "no such button"
    else if act is "move" then
      set position of (my trackWin()) to {(item 2 of argv) as integer, (item 3 of argv) as integer}
      return "moved"
    else if act is "song-window" then
      repeat with w in (every window whose name ends with "- Tracks")
        if my findEl(w, "AXLayoutItem", item 2 of argv, 0) is not missing value then return name of w as string
      end repeat
      return ""
    else if act is "control" then
      set w to my trackWin()
      set c to my findEl(toolbar 1 of w, item 2 of argv, item 3 of argv, 0)
      if c is missing value then return ""
      return value of c as string
    else if act is "apply-chords" then
      -- Logic ignores pop-up menus and keys posted to it while it is in the background (found
      -- 2026-11-18), so it is made active for the length of one keystroke, then focus goes back.
      -- Logic must have "Apply Region Chords to Chord Track" assigned to Ctrl-Opt-Shift-Cmd-C.
      set w to my trackWin()
      set reg to my findEl(w, "AXLayoutItem", item 2 of argv, 0)
      if reg is missing value then return "no region"
      set sel to false
      try
        set sel to value of attribute "AXSelected" of reg
      end try
      -- Setting AXSelected toggles it, so only set it when the region is not already selected.
      if sel is not true then
        set value of attribute "AXSelected" of reg to true
      end if
      set prev to my frontName()
      set frontmost to true
      -- The keys go to whatever is active, so they are only sent once Logic is.
      repeat 10 times
        if my frontName() is "__APP__" then exit repeat
        delay 0.5
        set frontmost to true
      end repeat
      if my frontName() is not "__APP__" then return "not active: " & my frontName()
      delay 0.5
      key code 8 using {control down, option down, shift down, command down}
      delay 0.5
      if prev is not "__APP__" then
        try
          my refront(prev)
        end try
      end if
      return "sent"
    else if act is "show-chord-track" then
      set w to my trackWin()
      if my findEl(w, "AXLayoutArea", "chord track", 0) is not missing value then return "already"
      set mi to menu item "Chord Track" of menu 1 of menu item "Global Tracks" of menu 1 of menu bar item "Track" of menu bar 1
      set mark to missing value
      try
        set mark to value of attribute "AXMenuItemMarkChar" of mi
      end try
      if mark is not missing value and mark is not "" then return "on, not drawn yet"
      click mi
      return "shown"
    else if act is "chord-items" then
      set w to my trackWin()
      set c to my findEl(w, "AXLayoutArea", "chord container", 0)
      if c is missing value then return ""
      set out to ""
      repeat with e in (every UI element of c)
        set out to out & (description of e as string) & linefeed
      end repeat
      return out
    end if
  end tell
end run
""".replace("__APP__", APP)


_WINDOW = {"name": ""}  # the song's project window, once main() has found it


def ax(*args: str) -> str:
    done = subprocess.run(
        ["osascript", "-", *args],
        input=_AX,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LOGIC_CHORDS_WINDOW": _WINDOW["name"]},
    )
    if os.environ.get("LOGIC_CHORDS_TRACE"):
        print(
            f"  ax {args} -> {done.returncode} {done.stdout.strip()[:160]!r} {done.stderr.strip()[:160]!r}",
            flush=True,
        )
    if done.returncode != 0:
        raise RuntimeError(f"Logic step {args[0]} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def wait(what: str, check, timeout: float = 90.0, every: float = 2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = check()
        if got:
            return got
        time.sleep(every)
    raise RuntimeError(f"timed out after {int(timeout)} s waiting for {what}")


def logic_running() -> bool:
    return (
        subprocess.run(
            ["pgrep", "-x", APP], capture_output=True, check=False
        ).returncode
        == 0
    )


# Logic's questions on the way in and out, and the answer each gets. Any other dialog is left
# open, so the wait times out and names it rather than the script guessing.
_ANSWERS = (
    (
        "[Change Project]",
        "Change Project",
    ),  # the song's sample rate differs from the project's
    (
        "[Don’t Import]",
        "Don’t Import",
    ),  # tempo found in the file: keep Logic's steady tempo
)


def answer_dialog(windows: str, quitting: bool = False) -> bool:
    """Answers the one dialog Logic is showing, when it is a known one. True when answered."""
    if "AXDialog" not in windows:
        return False
    answers = _ANSWERS + ((("[Don’t Save]", "Don’t Save"),) if quitting else ())
    if "audio interface" in windows.lower():
        answers += (("[OK]", "OK"),)
    for shown, button in answers:
        if shown in windows:
            ax("press", button)
            return True
    return False


def open_song(audio: Path) -> None:
    subprocess.run(["open", "-g", "-a", APP_PATH, str(audio)], check=True)

    def project_ready():
        windows = ax("windows")
        if answer_dialog(windows):
            return False
        return "- Tracks\t" in windows and "AXDialog" not in windows

    wait(
        "Logic's project window (an unexpected dialog may be open)", project_ready, 120
    )


def park() -> None:
    """Moves Logic's window onto the hidden screen when one is connected; else says so."""
    status = subprocess.run(
        [str(VDISPLAY), "status"], capture_output=True, text=True, check=False
    ).stdout
    m = re.search(r"origin=\((-?\d+),(-?\d+)\)", status)
    if not m or "DISCONNECTED" in status:
        print(
            "No hidden screen connected: Logic's window shows on the main screen, in the background."
        )
        return
    ax("move", str(int(m.group(1)) + 20), str(int(m.group(2)) + 20))


def read_chords(region: str) -> tuple[list[str], float]:
    """Analyzes the song's region and returns Logic's chord items and the project tempo."""
    bpm = float(wait("Logic's tempo", lambda: ax("control", "AXSlider", "Tempo"), 30))
    signature = ax("control", "AXPopUpButton", "Time Signature")
    if signature != "4/4":
        raise RuntimeError(
            f"Logic's project is in {signature}; this script reads 4/4 only"
        )
    # Apply analyzes the region as it goes. It is asked for once: a second press would only
    # re-run Chord ID on a song it is already working through.
    if ax("apply-chords", region) != "sent":
        raise RuntimeError(f"Logic has no region {region!r} to analyze")
    seen: list[str] = []

    def settled():
        # Logic renames or re-lists its window while it analyzes (seen after the focus flip), so
        # the project window is looked up again on every poll; none yet means ask again later.
        name = ax("song-window", region)
        if not name:
            return None
        _WINDOW["name"] = name
        ax("show-chord-track")
        items = [l for l in ax("chord-items").splitlines() if l.strip()]
        if items and items == seen:
            return items
        seen[:] = items
        return None

    return wait("the Chord Track's chords", settled, 300, 5), bpm


def quit_logic() -> None:
    """Quits Logic and throws the scratch project away. The quit is asked again until Logic is
    gone: one sent while another dialog is up is dropped."""

    def gone():
        if not logic_running():
            return True
        windows = ax("windows")
        if not answer_dialog(windows, quitting=True) and "AXDialog" not in windows:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    # "is running" first: telling an app that has just quit to quit launches it again.
                    f'if application "{APP}" is running then\nignoring application responses\ntell application "{APP}" to quit\nend ignoring\nend if',
                ],
                capture_output=True,
                check=False,
            )
        return False

    try:
        wait("Logic to quit", gone, 90)
    except RuntimeError:
        # Only reached for a Logic this script opened (main refuses to run when one was
        # already open), so it holds nothing but the scratch project.
        print("Logic would not quit (a dialog it cannot answer?); ending its process.")
        subprocess.run(["pkill", "-TERM", "-x", APP], capture_output=True, check=False)
        wait("Logic to end", lambda: not logic_running(), 30, 1)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 1
    audio = Path(argv[0]).expanduser().resolve()
    chart = audio.with_name(f"{audio.stem} chords.txt")
    backup = audio.with_name(f"{audio.stem} chords (script).txt")
    if not audio.is_file():
        print(f"No audio file at {audio}")
        return 1
    if not chart.is_file():
        print(
            f"No chart at {chart}: run the Guitar chords step first, which sets the bar grid."
        )
        return 1
    if logic_running():
        print(
            "Logic is open. Close it first: the song would be added to the project it has open."
        )
        return 1
    grid = read_grid(chart.read_text())
    print("Running Logic's Chord ID in the background (a minute or two)...", flush=True)
    try:
        open_song(audio)
        _WINDOW["name"] = wait(
            f"a project window holding the region {audio.stem!r}",
            lambda: ax("song-window", audio.stem),
            60,
        )
        park()
        if os.environ.get(
            "LOGIC_CHORDS_DRYRUN"
        ):  # open and quit only, for testing the run
            print("dry run: opened the song, quitting")
            return 0
        items, logic_bpm = read_chords(audio.stem)
    finally:
        quit_logic()
    changes, unknown = [], set()
    for item in items:
        spoken, position = split_item(item)
        try:
            changes.append((item_seconds(position, logic_bpm), chord_name(spoken)))
        except ValueError:
            unknown.add(spoken)
    if unknown:
        # All of them at once, so one more run does not stop on the next new name.
        print(
            f"Nothing written: Logic named chords this script cannot spell yet: {sorted(unknown)}"
        )
        return 1
    save_changes(audio.with_name(f"{audio.stem} logic.tsv"), changes)
    labels, mids = bar_halves(changes, grid[2], grid[3], start=grid[4])
    old = chart.read_text()
    if not backup.exists() and SOURCE_NOTE not in old:
        backup.write_text(old)
    chart.write_text(chart_text(grid, labels, mids))
    before = [l.split("\t")[1] for l in old.splitlines() if re.match(r"\d+\t", l)]
    changed = sum(1 for a, b in zip(before, labels) if a != b)
    print(
        f"Logic found {len(changes)} chord changes; {changed} of {len(labels)} bars differ from the old chart."
    )
    print(f"Wrote {chart.name}; the old chart is {backup.name}.")
    # Then line it up with the record's beat and downbeat (numpy, so the venv's python).
    aligned = subprocess.run(
        [str(VENV_PYTHON), str(ALIGN), str(audio)],
        capture_output=True,
        text=True,
        check=False,
    )
    print(aligned.stdout.strip())
    if aligned.returncode != 0:
        why = (aligned.stdout + aligned.stderr).strip()[-300:]
        print(
            f"Lining the chart up with the record failed, so it keeps its old grid: {why}"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
