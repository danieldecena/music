#!/usr/bin/env python3
"""Fan a sample (or a folder of samples) out into transformed variants — the
'flip fuel' generator. numpy only.

Transforms:
  halfspeed  octave down + half tempo (classic flip)
  pitchdown  -4 semitones (resample; slower/lower)
  pitchup    +5 semitones (resample; faster/higher)
  reverse    reversed
  freeze     granular freeze/smear -> texture/pad
  stutter    glitchy slice-repeat
  bitcrush   bit + sample-rate reduction (lo-fi/digital grit)
  tape       soft-clip saturation + slow wow
  smear      spectral phase-randomise (reverb-like wash)
  telephone  band-limited + grit (radio/phone character)
  conv       convolved THROUGH a kick one-shot (imprints its body)  [needs a kit]

Output: Samples/Mangled/<track>/<stem>_<variant>.wav

Usage: mangle.py <input.wav | folder> [--track NAME] [--kick <wav>]
       [--out Samples/Mangled] [--only a,b,c] [--max N]
"""
import argparse
import glob
import os
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(os.environ.get("LOGIC_STUDIO_MUSIC_ROOT", Path(__file__).resolve().parent.parent))
SR = 44100
ALL = ["halfspeed", "pitchdown", "pitchup", "reverse", "freeze", "stutter",
       "bitcrush", "tape", "smear", "telephone", "conv"]


def load_mono(path):
    w = wave.open(str(path), "rb")
    ch, sr, sw, n = w.getnchannels(), w.getframerate(), w.getsampwidth(), w.getnframes()
    raw = w.readframes(n); w.close()
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
    if sr != SR and len(a) > 1:
        idx = np.linspace(0, len(a) - 1, int(len(a) * SR / sr))
        a = np.interp(idx, np.arange(len(a)), a).astype("float32")
    return a


def write_wav(path, x):
    peak = float(np.max(np.abs(x))) or 1.0
    y = (x / peak * 0.89 * 32767).astype("<i2")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w = wave.open(str(path), "wb")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(y.tobytes()); w.close()


def _resample_pitch(x, st):
    r = 2 ** (st / 12.0)
    idx = np.arange(0, len(x), r)
    return np.interp(idx, np.arange(len(x)), x).astype("float32")


def t_halfspeed(x): return _resample_pitch(x, -12)
def t_pitchdown(x): return _resample_pitch(x, -4)
def t_pitchup(x): return _resample_pitch(x, 5)
def t_reverse(x): return x[::-1].copy()


def t_freeze(x, out_dur=None, grain_ms=90, density=4.0):
    g = int(SR * grain_ms / 1000)
    if len(x) < g:
        return x
    win = np.hanning(g).astype("float32")
    out_len = int(out_dur if out_dur else max(len(x) * 2, SR))
    out = np.zeros(out_len + g, dtype="float32")
    hop = max(1, int(g / density))
    s0 = len(x) // 3
    s1 = min(len(x), s0 + max(g, len(x) // 3))
    rng = np.random.default_rng(0)
    pos = 0
    while pos < out_len:
        s = s0 + int(rng.integers(0, max(1, s1 - s0 - g)))
        out[pos:pos + g] += x[s:s + g] * win
        pos += hop
    return out[:out_len]


def t_stutter(x):
    g = max(1, int(SR * 0.06))
    if len(x) < g:
        return x
    rng = np.random.default_rng(1)
    parts = []
    i = 0
    while i < len(x):
        seg = x[i:i + g]
        for _ in range(int(rng.choice([1, 1, 2, 3, 4]))):
            parts.append(seg)
        i += g
    return np.concatenate(parts).astype("float32") if parts else x


def t_bitcrush(x, bits=6, ds=4):
    q = 2 ** bits
    y = np.round(x * q) / q
    idx = (np.arange(len(y)) // ds) * ds
    return y[idx].astype("float32")


def t_tape(x, drive=3.0):
    y = np.tanh(x * drive)
    t = np.arange(len(y))
    mod = 1 + 0.003 * np.sin(2 * np.pi * t / (SR * 1.5))
    idx = np.cumsum(mod)
    idx = idx / idx[-1] * (len(y) - 1)
    return np.interp(idx, t, y).astype("float32")


def t_smear(x):
    X = np.fft.rfft(x)
    rng = np.random.default_rng(2)
    ph = np.angle(X) + rng.normal(0, 1.2, size=X.shape)
    y = np.fft.irfft(np.abs(X) * np.exp(1j * ph), n=len(x))
    return y.astype("float32")


def t_telephone(x):
    X = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    y = np.fft.irfft(X * ((freqs > 300) & (freqs < 3000)), n=len(x))
    return np.tanh(y * 2.0).astype("float32")


def t_conv(x, ir):
    ir = ir[: int(SR * 0.4)]
    ir = ir / (np.max(np.abs(ir)) or 1.0)
    return np.convolve(x, ir).astype("float32")


TF = {
    "halfspeed": t_halfspeed, "pitchdown": t_pitchdown, "pitchup": t_pitchup,
    "reverse": t_reverse, "freeze": t_freeze, "stutter": t_stutter,
    "bitcrush": t_bitcrush, "tape": t_tape, "smear": t_smear, "telephone": t_telephone,
}


def _find_kick(track, override):
    if override and os.path.isfile(override):
        return override
    for pat in (ROOT / "Samples" / "One-Shots" / str(track) / "kick" / "*.wav",
                ROOT / "Samples" / "One-Shots" / "*" / "kick" / "*.wav"):
        hits = sorted(glob.glob(str(pat)))
        if hits:
            return hits[0]
    return None


def _infer_track(inp: Path):
    parts = inp.parts
    for anchor in ("One-Shots", "Chops", "Vocals", "Stems", "Loops", "Resynth", "Mangled"):
        if anchor in parts:
            i = parts.index(anchor)
            if i + 1 < len(parts):
                return parts[i + 1]
    return inp.stem


def mangle_one(inp: Path, only, out_root, kick_override):
    x = load_mono(inp)
    if len(x) < 8:
        return []
    rel = inp.resolve()
    track = _infer_track(rel.relative_to(ROOT) if str(rel).startswith(str(ROOT)) else rel)
    outdir = Path(out_root) / str(track)
    made = []
    for name in only:
        try:
            if name == "conv":
                kick = _find_kick(track, kick_override)
                if not kick:
                    continue
                y = t_conv(x, load_mono(kick))
            else:
                fn = TF.get(name)
                if not fn:
                    continue
                y = fn(x)
            p = outdir / f"{inp.stem}_{name}.wav"
            write_wav(str(p), y)
            made.append(str(p.relative_to(ROOT)) if str(p).startswith(str(ROOT)) else str(p))
        except Exception as exc:
            print(f"  ! {name} failed: {exc}")
    return made


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--track", default=None)
    ap.add_argument("--kick", default=None)
    ap.add_argument("--out", default=str(ROOT / "Samples" / "Mangled"))
    ap.add_argument("--only", default=",".join(ALL))
    ap.add_argument("--max", type=int, default=8, help="max files when input is a folder")
    ns = ap.parse_args(argv)

    only = [w.strip() for w in ns.only.split(",") if w.strip() in ALL]
    inp = Path(ns.input)
    targets = []
    if inp.is_dir():
        targets = sorted(inp.rglob("*.wav"))[: ns.max]
    elif inp.is_file():
        targets = [inp]
    else:
        print(f"ERROR: no file/folder at {inp}")
        return 1

    total = 0
    for f in targets:
        made = mangle_one(f, only, ns.out, ns.kick)
        total += len(made)
        print(f"Mangled {f.stem} → {len(made)} variants")
    print(f"✓ {total} variants written under {ns.out}")
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
