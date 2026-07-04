#!/usr/bin/env python3
"""
Transcribe a MONOPHONIC stem (bass line) to a MIDI file. Pure numpy for pitch
detection (autocorrelation per onset segment) + a hand-written minimal MIDI
writer, so no external deps.

ADVANCED / BEST-EFFORT: reliable only for clean single-note lines like bass.
Polyphonic material (chords, full "other" stems) will not transcribe well.

Usage:
    bass_to_midi.py <bass.wav> <out.mid> [--tempo BPM]
"""

import argparse
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 22050
FRAME = 2048
HOP = 512


def decode_mono(path: Path) -> np.ndarray:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            str(SR),
            "-f",
            "s16le",
            "-",
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="ignore") or "decode failed")
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def pitch_hz(seg: np.ndarray, lo_hz: float = 40.0, hi_hz: float = 400.0) -> float:
    """Fundamental via autocorrelation, restricted to [lo_hz, hi_hz]."""
    seg = seg - seg.mean()
    if np.sqrt((seg**2).mean()) < 0.005:  # silence gate
        return 0.0
    ac = np.correlate(seg, seg, mode="full")[len(seg) - 1 :]
    lo = int(SR / hi_hz)
    hi = int(SR / lo_hz)
    if hi >= len(ac):
        hi = len(ac) - 1
    if lo < 1 or hi <= lo:
        return 0.0
    lag = lo + int(np.argmax(ac[lo:hi]))
    return SR / lag if lag else 0.0


def hz_to_midi(hz: float) -> int:
    return int(round(69 + 12 * np.log2(hz / 440.0))) if hz > 0 else 0


def transcribe(
    audio: np.ndarray, lo_hz: float = 40.0, hi_hz: float = 400.0
) -> list[tuple[int, int, int]]:
    """Return list of (midi_note, start_frame, end_frame) merging equal pitches."""
    n = 1 + (len(audio) - FRAME) // HOP
    notes = []
    for i in range(max(n, 0)):
        s = i * HOP
        note = hz_to_midi(pitch_hz(audio[s : s + FRAME], lo_hz, hi_hz))
        notes.append(note)
    # Merge consecutive identical notes into sustained events.
    events, i = [], 0
    while i < len(notes):
        if notes[i] == 0:
            i += 1
            continue
        j = i
        while j + 1 < len(notes) and notes[j + 1] == notes[i]:
            j += 1
        if j - i >= 2:  # drop 1-frame blips
            events.append((notes[i], i, j + 1))
        i = j + 1
    return events


def _var_len(n: int) -> bytes:
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def write_midi(
    events, path: Path, tempo_bpm: float, program: int | None = None
) -> None:
    tpqn = 480
    sec_per_frame = HOP / SR
    sec_per_beat = 60.0 / (tempo_bpm or 120.0)
    ticks_per_frame = tpqn / sec_per_beat * sec_per_frame

    track = bytearray()
    us_per_beat = int(60_000_000 / (tempo_bpm or 120.0))
    track += b"\x00\xff\x51\x03" + us_per_beat.to_bytes(3, "big")  # set tempo
    if program is not None:  # GM program change on channel 0, delta 0
        track += bytes([0x00, 0xC0, program & 0x7F])

    cursor = 0.0
    last_tick = 0
    for note, start_f, end_f in events:
        on_tick = int(start_f * ticks_per_frame)
        off_tick = int(end_f * ticks_per_frame)
        track += _var_len(on_tick - last_tick) + bytes([0x90, note, 90])
        track += _var_len(off_tick - on_tick) + bytes([0x80, note, 0])
        last_tick = off_tick
    track += b"\x00\xff\x2f\x00"  # end of track

    with open(path, "wb") as fh:
        fh.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpqn))
        fh.write(b"MTrk" + struct.pack(">I", len(track)) + track)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Transcribe a monophonic bass stem to MIDI"
    )
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--tempo", type=float, default=120.0)
    args = ap.parse_args()

    events = transcribe(decode_mono(Path(args.input)))
    if not events:
        print("No pitched notes detected.")
        sys.exit(1)
    write_midi(events, Path(args.output), args.tempo)
    print(f"✓ {len(events)} notes -> {args.output} (tempo {args.tempo} BPM)")


if __name__ == "__main__":
    main()
