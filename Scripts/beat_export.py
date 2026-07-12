#!/usr/bin/env python3
"""Render a step-sequencer pattern to a MIDI file or a WAV loop.

Used by the Cowork Music Studio artifact's step sequencer (via Desktop
Commander). Rows are passed as repeated --row entries:

    --row "NAME:NOTE:PATTERN[:SAMPLE_PATH]"

  NAME        row label (kick, snare, hat, openhat, clap, 808, …)
  NOTE        GM MIDI note number for MIDI export (e.g. 36)
  PATTERN     step string of '1'/'0' (length == --steps)
  SAMPLE_PATH absolute path to a one-shot .wav (WAV export only; optional)

Examples:
  beat_export.py midi out.mid --bpm 90 --steps 16 --reps 2 \
      --row "kick:36:1000100010001000" --row "snare:38:0000100000001000"
  beat_export.py wav out.wav --bpm 90 --steps 16 --reps 2 \
      --row "kick:36:1000...:/abs/kick/drums_002.wav" \
      --row "hat:42:1010...:/abs/hat/drums_004.wav"
"""
import argparse
import os
import sys
import wave

DEFAULT_NOTE = {"kick": 36, "snare": 38, "hat": 42, "openhat": 46, "clap": 39, "808": 35}


def parse_rows(entries):
    rows = []
    for e in entries:
        parts = e.split(":", 3)
        if len(parts) < 3:
            continue
        name, note, pattern = parts[0], parts[1], parts[2]
        sample = parts[3] if len(parts) > 3 else ""
        try:
            note_n = int(note)
        except ValueError:
            note_n = DEFAULT_NOTE.get(name, 36)
        if "1" in pattern:
            rows.append({"name": name, "note": note_n, "pattern": pattern, "sample": sample})
    return rows


def _vlq(n):
    if n == 0:
        return bytes([0])
    out = [n & 0x7F]
    n >>= 7
    while n > 0:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def write_midi(out, bpm, steps, reps, rows):
    ppq = 480
    step_ticks = ppq // 4
    events = []
    for r in range(reps):
        for row in rows:
            for i, ch in enumerate(row["pattern"][:steps]):
                if ch == "1":
                    t = (r * steps + i) * step_ticks
                    events.append((t, 0x99, row["note"], 100))
                    events.append((t + step_ticks // 2, 0x89, row["note"], 0))
    events.sort(key=lambda e: (e[0], e[1] == 0x99))
    track = bytearray()
    track += bytes([0x00, 0xFF, 0x51, 0x03]) + int(60_000_000 / bpm).to_bytes(3, "big")
    last = 0
    for t, st, note, vel in events:
        track += _vlq(t - last) + bytes([st, note, vel])
        last = t
    track += bytes([0x00, 0xFF, 0x2F, 0x00])
    hdr = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big") + ppq.to_bytes(2, "big")
    trk = b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "wb") as f:
        f.write(hdr + trk)
    hits = sum(row["pattern"][:steps].count("1") for row in rows) * reps
    return f"Wrote {out}  ({bpm:g} BPM, {steps} steps x{reps}, {len(rows)} rows, {hits} hits)"


def _load_mono(path, target_sr=44100):
    import numpy as np
    w = wave.open(path, "rb")
    ch, sr, sw, n = w.getnchannels(), w.getframerate(), w.getsampwidth(), w.getnframes()
    raw = w.readframes(n)
    w.close()
    if sw == 2:
        a = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    elif sw == 4:
        a = np.frombuffer(raw, dtype="<i4").astype("float32") / 2147483648.0
    elif sw == 1:
        a = (np.frombuffer(raw, dtype="uint8").astype("float32") - 128) / 128.0
    else:
        a = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != target_sr and len(a) > 1:
        idx = np.linspace(0, len(a) - 1, int(len(a) * target_sr / sr))
        a = np.interp(idx, np.arange(len(a)), a).astype("float32")
    return a


def write_wav(out, bpm, steps, reps, rows):
    import numpy as np
    sr = 44100
    step_dur = (60.0 / bpm) / 4.0
    total = steps * reps
    buf = np.zeros(int(step_dur * total * sr) + sr, dtype="float32")
    used = []
    for row in rows:
        s = _load_mono(row["sample"]) if row["sample"] and os.path.isfile(row["sample"]) else None
        used.append(f"{row['name']}={os.path.basename(row['sample']) if s is not None else '(none)'}")
        if s is None:
            continue
        for r in range(reps):
            for i, ch in enumerate(row["pattern"][:steps]):
                if ch == "1":
                    start = int((r * steps + i) * step_dur * sr)
                    seg = s[: max(0, len(buf) - start)]
                    buf[start:start + len(seg)] += seg
    peak = float(np.max(np.abs(buf))) or 1.0
    out_i16 = (buf / peak * 0.89 * 32767).astype("<i2")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    w = wave.open(out, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(out_i16.tobytes())
    w.close()
    return f"Wrote {out}  ({len(out_i16)/sr:.2f}s, {bpm:g} BPM, {steps} steps x{reps})  [{', '.join(used)}]"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["midi", "wav"])
    ap.add_argument("out")
    ap.add_argument("--bpm", type=float, default=90.0)
    ap.add_argument("--steps", type=int, default=16)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--row", action="append", default=[])
    ns = ap.parse_args(argv)
    rows = parse_rows(ns.row)
    if not rows:
        print("No active steps in pattern.")
        return 1
    try:
        if ns.mode == "midi":
            print(write_midi(ns.out, ns.bpm, ns.steps, ns.reps, rows))
        else:
            print(write_wav(ns.out, ns.bpm, ns.steps, ns.reps, rows))
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
