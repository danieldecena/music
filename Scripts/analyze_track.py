#!/usr/bin/env python3
"""
Detect tempo (BPM) and musical key of an audio file. Pure numpy — decodes via
ffmpeg, so no librosa/aubio needed (works on the demucs venv, incl. Python 3.14).

Tempo:  onset-strength envelope -> autocorrelation -> best lag in 60-180 BPM.
Key:    average chroma vector -> Krumhansl-Schmuckler profile correlation over
        all 24 major/minor keys.

Estimates, not ground truth — good enough to line up chops and pick a repitch.

Usage:
    analyze_track.py <audio file | folder>
"""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SR = 22050
FRAME = 2048
HOP = 512
PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
AUDIO_EXT = (".m4a", ".mp3", ".wav", ".flac")
STEM_NAMES = ("vocals", "drums", "bass", "other", "guitar", "piano")

# Krumhansl-Schmuckler key profiles.
_MAJ = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_MIN = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)


def decode_mono(path: Path, sr: int) -> np.ndarray:
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
            str(sr),
            "-f",
            "s16le",
            "-",
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.decode(errors="ignore") or "ffmpeg decode failed"
        )
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def _frames(audio: np.ndarray) -> np.ndarray:
    n = 1 + (len(audio) - FRAME) // HOP
    if n < 2:
        return np.empty((0, FRAME))
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(n)[:, None]
    return audio[idx] * np.hanning(FRAME).astype(np.float32)


@dataclass
class Spec:
    """One pass of spectral analysis, shared by all three detectors.

    `flux` is the RAW onset-strength envelope. detect_tempo subtracts its mean
    and estimate_boundaries does not, so the mean subtraction stays at the call
    site — folding it in here would silently change one of them.
    """

    mag: np.ndarray  # (n_frames, n_bins) magnitude spectrogram
    flux: np.ndarray  # (n_frames-1,) raw spectral flux
    fps: float  # envelope frames per second

    @property
    def n_frames(self) -> int:
        return self.mag.shape[0]


def spectra(audio: np.ndarray) -> Spec:
    """Frame, FFT, and difference the signal once.

    The FFT runs in chunks so the frame matrix and its transform are not both
    fully materialized — a 5-minute track is ~13k frames x 2048 samples.
    """
    frames = _frames(audio)
    fps = SR / HOP
    if frames.shape[0] == 0:
        return Spec(
            np.empty((0, FRAME // 2 + 1), np.float32), np.empty(0, np.float32), fps
        )
    chunks = [
        np.abs(np.fft.rfft(frames[i : i + 2048], axis=1)).astype(np.float32)
        for i in range(0, frames.shape[0], 2048)
    ]
    mag = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
    flux = np.sqrt((np.maximum(np.diff(mag, axis=0), 0.0) ** 2).sum(axis=1))
    return Spec(mag, flux, fps)


def _ac_at(ac: np.ndarray, lag: float) -> float:
    """Autocorrelation at a fractional lag, linearly interpolated."""
    i = int(lag)
    if i < 1 or i + 1 >= len(ac):
        return 0.0
    f = lag - i
    return float((1.0 - f) * ac[i] + f * ac[i + 1])


def _refine_lag(ac: np.ndarray, i: int) -> float:
    """Refine an integer autocorrelation peak to sub-frame precision.

    At HOP=512/SR=22050 the envelope runs at ~43 fps, so the whole 50-210 BPM
    range spans only integer lags 12-51. A 140 BPM pulse sits at lag 18.46 and
    can otherwise only be read as 143.6 (lag 18) or 136.1 (lag 19).

    This is not merely a precision issue. An 0.46-frame-per-beat error
    accumulates to a full beat of drift within 30 seconds, which collapses both
    the harmonic evidence and the grid support for the FAST candidate, while the
    slow candidate at roughly twice the lag drifts half as fast per beat. Scoring
    unrefined integer lags therefore has a systematic bias toward the halved
    reading — the exact error this function exists to prevent.
    """
    if i < 1 or i + 1 >= len(ac):
        return float(i)
    denom = ac[i - 1] - 2.0 * ac[i] + ac[i + 1]
    if denom == 0:
        return float(i)
    delta = 0.5 * (ac[i - 1] - ac[i + 1]) / denom
    if not -1.0 < delta < 1.0:
        return float(i)
    return float(i) + float(delta)


# How far _grid_support may nudge a candidate lag to find its true alignment.
# Wide enough to absorb _refine_lag's error on short lags, far too narrow to
# reach an octave (100%) or 3:2 (50%) neighbour.
_GRID_LAG_TOL = 0.02


def _grid_support(env: np.ndarray, lag: float) -> float:
    """Energy on the beat grid vs. the grids between beats — halves and thirds.

    This is what actually separates 70 from 140, and 3:2/2:3 misreads from the
    true pulse. Harmonic evidence alone cannot: a true 140 and a true 70 both put
    energy every 140-lag, so the score is near-symmetric under doubling by
    construction.

    Two off-grids are tested against the on-beat energy:

      * the HALFWAY point (0.5) separates duple octave errors. At a real 140 the
        odd-numbered beats carry comparable energy; at a real 70 the halfway
        points are relatively empty.
      * the THIRDS (1/3, 2/3) separate 3:2 metrical errors. A candidate at 3/2 or
        2/3 of the true lag leaves the real onsets sitting on its thirds while its
        own halfway point stays empty — so the halfway test alone rates it as a
        clean pulse. Penalizing a candidate whose thirds are as full as its beats
        rejects the triple-meter misread. Straight duple music leaves the thirds
        empty, so the penalty is ~1.0 there.

    The 1.0 floor was removed so this penalty can push a misread BELOW a clean
    candidate rather than merely denying it the bonus. Returns roughly 0.5-1.5:
    high for the true pulse, low for a double-time or triple-meter misread.

    The grid phase is searched, not assumed — starting at sample 0 would score a
    track with any pickup or leading silence against a misaligned grid.

    The LAG is searched too, over a narrow band. The autocorrelation's resolution
    is one frame, which at a short lag is enormous: at lag 16 (~160 BPM, 43 fps)
    consecutive integer lags are 160.8 and 152.0 BPM, ~9 BPM apart. `_refine_lag`
    interpolates between them but lands within only ~0.5%, and because this grid
    is rigid across the whole track that error compounds — 0.076 frames/beat over
    521 beats walks the grid 2.5 whole beats off the music, collapsing a true
    candidate's score (measured on Exchange: 1.14 at the exact lag, 0.64 at the
    refined one). Searching +/-2% recovers the alignment the AC was too coarse to
    express. It cannot rescue a real 3:2 or octave misread, which is 50% or 100%
    away, so the discrimination above is untouched.
    """
    best = 0.0
    for lag_try in lag * np.linspace(1.0 - _GRID_LAG_TOL, 1.0 + _GRID_LAG_TOL, 9):
        n = int(len(env) / lag_try)
        if n < 8:
            continue
        k = np.arange(n)
        for phase in np.linspace(0.0, lag_try, 8, endpoint=False):
            base = phase + k * lag_try
            on_idx = np.rint(base).astype(int).clip(0, len(env) - 1)
            off_idx = np.rint(base + 0.5 * lag_try).astype(int).clip(0, len(env) - 1)
            t1_idx = np.rint(base + lag_try / 3.0).astype(int).clip(0, len(env) - 1)
            t2_idx = (
                np.rint(base + 2.0 * lag_try / 3.0).astype(int).clip(0, len(env) - 1)
            )
            on, off = env[on_idx].mean(), env[off_idx].mean()
            tot = on + off
            if tot <= 0:
                continue
            third = 0.5 * (env[t1_idx].mean() + env[t2_idx].mean())
            duple = on / (on + third) if on + third > 0 else 1.0
            score = (0.5 + on / tot) * duple
            if score > best:
                best = score
    return best if best > 0 else 1.0


# Lag multiples scored as evidence for a candidate, with their weights.
_TEMPO_MULTS = ((0.5, 0.55), (1.0, 1.0), (2.0, 0.85), (3.0, 0.45), (4.0, 0.30))
_PRIOR_CENTER, _PRIOR_SIGMA = 120.0, 0.85  # sigma in log2 units
_BPM_MIN, _BPM_MAX = 50.0, 210.0


def detect_tempo(sp: Spec) -> float:
    """Estimate BPM, resolving the half/double-time ambiguity.

    Taking the plain argmax of the autocorrelation (the previous approach) picks
    whichever of t, t/2, 2t happens to peak highest, so halftime-feel tracks
    reported half their true tempo. Each candidate peak is instead scored on
    three terms: evidence at its own harmonics, a perceptual prior, and grid
    support.
    """
    if sp.n_frames < 4:
        return 0.0
    env = np.maximum(sp.flux - sp.flux.mean(), 0.0)  # half-wave rectify
    if len(env) < 16 or not env.any():
        return 0.0
    fps = sp.fps
    ac = np.correlate(env, env, mode="full")[len(env) - 1 :]
    # Correlation at lag L averages over fewer products than at lag 0; without
    # this the raw curve slopes down and biases every comparison toward short
    # lags (fast tempi).
    ac = ac / np.arange(len(ac), 0, -1)
    if ac[0] > 0:
        ac = ac / ac[0]

    lo = max(1, int(fps * 60 / _BPM_MAX))
    hi = min(len(ac) - 2, int(fps * 60 / _BPM_MIN))
    if hi <= lo + 2:
        return 0.0
    band = ac[lo : hi + 1]
    cand = lo + 1 + np.flatnonzero((band[1:-1] > band[:-2]) & (band[1:-1] >= band[2:]))
    if cand.size == 0:
        return 0.0
    cand = cand[np.argsort(ac[cand])[::-1][:24]]

    best_score, best_lag = -1e9, 0.0
    for i in cand:
        lag = _refine_lag(ac, int(i))
        bpm = 60.0 * fps / lag
        if not _BPM_MIN <= bpm <= _BPM_MAX:
            continue
        evidence = sum(w * _ac_at(ac, lag * m) for m, w in _TEMPO_MULTS)
        prior = np.exp(-0.5 * (np.log2(bpm / _PRIOR_CENTER) / _PRIOR_SIGMA) ** 2)
        score = evidence * prior * _grid_support(env, lag)
        if score > best_score:
            best_score, best_lag = score, lag
    if best_lag == 0.0:
        return 0.0
    return round(60.0 * fps / best_lag, 1)


# Subharmonic summation: a bin at n * f0 is evidence for f0's pitch class, not
# just its own. n=2/4 are skipped -- they already fold to the same pitch class
# as n=1 under octave equivalence, so voting there again adds no new signal.
# n=3/5 are where a single-projection scheme is wrong: a fifth-heavy or
# third-heavy harmonic spectrum (common on bass/guitar with a weak fundamental)
# piles votes onto the harmonic's own pitch class instead of the true tonic's.
_HARMONICS = ((1, 1.0), (3, 0.5), (5, 0.35))


def _chroma_projection() -> tuple[np.ndarray, np.ndarray]:
    """Bin mask and (n_kept_bins, 12) pitch-class projection matrix.

    Range is 55-2000 Hz, narrowed from the original 27.5-5000. Below 55 Hz a
    2048-point FFT at 22050 Hz has ~10.8 Hz resolution, so a single bin spans
    more than a semitone — those bins were charging noise to a pitch class.
    Above ~2000 Hz is mostly cymbals and air.

    The Gaussian weight favours roughly C3-C6, the register where pitch class is
    legible, instead of treating every octave as equally informative.

    Each bin also casts a smaller vote for its 3rd- and 5th-subharmonic pitch
    class (see `_HARMONICS`), so a bin that IS a 3rd/5th harmonic of some lower
    fundamental reinforces that fundamental's pitch class instead of only its
    own.

    The per-pitch-class column totals are then equalized. Linear FFT bin
    spacing vs. logarithmic semitone spacing means a fixed bin can span more
    than one semitone at the low end of the range, and `np.rint(midi) % 12`
    rounds each such bin to a single pitch class -- which pitch classes
    happen to catch the extra bins is an accident of where 55-2000 Hz lands
    on the frequency grid, not anything about the audio. Measured: unweighted,
    white noise (zero tonal content) still resolves to a specific key (`D`,
    total column weight ~16.2 vs. ~11.3 for C#/D#) -- a content-independent
    bias baked into every track's chroma. Equalizing collapses that bias
    (white-noise chroma spread 0.030 -> 0.001) and, combined with the
    subharmonic votes above, moved the independent UG key-oracle score from
    1/10 exact to 4/10 exact, 7/10 sharing the pitch-class set.
    """
    freqs = np.fft.rfftfreq(FRAME, 1.0 / SR)
    keep = (freqs >= 55.0) & (freqs <= 2000.0)
    midi = 69 + 12 * np.log2(freqs[keep] / 440.0)
    register = np.exp(-0.5 * ((midi - 60.0) / 18.0) ** 2)
    proj = np.zeros((keep.sum(), 12), np.float32)
    idx = np.arange(keep.sum())
    for n, w in _HARMONICS:
        pc = np.rint(midi - 12 * np.log2(n)).astype(int) % 12
        proj[idx, pc] += (register * w).astype(np.float32)
    totals = proj.sum(axis=0, keepdims=True)
    proj = np.divide(proj, totals, out=np.zeros_like(proj), where=totals > 0)
    proj *= totals.mean()
    return keep, proj


_KEEP, _PROJ = _chroma_projection()


def _chroma_vector(sp: Spec) -> np.ndarray | None:
    """Average energy per pitch class, L1-normalized. None if nothing to read.

    Three cheap defenses against percussive smear, in place of a median-filter
    HPSS that would cost far more memory than it is worth here:

      1. log1p compression, so one loud hit cannot dominate the average;
      2. per-frame L1 normalization, so a snare frame counts the same as a frame
         of sustained pads rather than eight times as much;
      3. dropping the top 15% of frames by spectral flux — transients are
         exactly where broadband energy smears across every pitch class.
    """
    if sp.n_frames < 2:
        return None
    m = np.log1p(sp.mag[:, _KEEP])
    if sp.flux.size and m.shape[0] > 1:
        quiet = np.ones(m.shape[0], bool)
        quiet[1:] = sp.flux <= np.percentile(sp.flux, 85)
        if quiet.sum() >= 8:
            m = m[quiet]
    c = m @ _PROJ
    total = c.sum(axis=1, keepdims=True)
    c = np.divide(c, total, out=np.zeros_like(c), where=total > 0)
    chroma = c.mean(axis=0).astype(np.float64)
    if chroma.sum() == 0:
        return None
    return chroma / chroma.sum()


def _key_profiles() -> tuple[np.ndarray, list[str]]:
    """All 24 rotated key profiles, z-scored, plus their names."""
    rows, names = [], []
    for i in range(12):
        for prof, mode in ((_MAJ, ""), (_MIN, "m")):
            rows.append(np.roll(prof, i))
            names.append(f"{PITCHES[i]}{mode}")
    p = np.array(rows)
    p = (p - p.mean(axis=1, keepdims=True)) / p.std(axis=1, keepdims=True)
    return p, names


_PROFILES, _PROFILE_NAMES = _key_profiles()


def _key_from_chroma(chroma: np.ndarray | None) -> str:
    """Best-correlating Krumhansl-Schmuckler key for a chroma vector.

    Correlating against all 24 profiles at once: z-scoring both sides makes the
    Pearson correlation a plain dot product, so this is one (24,12) @ (12,)
    instead of 24 separate np.corrcoef calls.
    """
    if chroma is None or chroma.sum() == 0:
        return "unknown"
    std = chroma.std()
    if std == 0:
        return "unknown"
    z = (chroma - chroma.mean()) / std
    return _PROFILE_NAMES[int(np.argmax(_PROFILES @ z))]


def detect_key(sp: Spec) -> str:
    return _key_from_chroma(_chroma_vector(sp))


def _pick_boundaries(nov: np.ndarray, period: float, fps: float) -> list[float]:
    """Peaks of a beat-indexed novelty curve, snapped to the bar grid.

    The threshold is a local mean over +-8 bars rather than a global constant, so
    a quiet intro and a dense chorus are judged against their own surroundings.

    Snapping assumes the downbeat is beat 0, so a track with a pickup can be off
    by up to 3 beats (~1.5 s at 120 BPM). Accepted — real downbeat estimation is
    out of scope. Snapping can also collide two nearby peaks onto one bar, so the
    minimum gap is re-enforced afterwards.
    """
    w = 32
    pad = np.pad(nov, w, mode="edge")
    local = np.array([pad[i : i + 2 * w + 1].mean() for i in range(len(nov))])
    thr = local + 0.6 * nov.std()
    is_peak = (nov[1:-1] > nov[:-2]) & (nov[1:-1] >= nov[2:]) & (nov[1:-1] > thr[1:-1])
    peaks = np.flatnonzero(is_peak) + 1
    if peaks.size == 0:
        return []

    chosen: list[int] = []
    for p in peaks[np.argsort(nov[peaks])[::-1]]:
        if all(abs(int(p) - q) >= 8 for q in chosen):
            chosen.append(int(p))

    bars = sorted({int(round(p / 4.0)) * 4 for p in chosen})
    out: list[int] = []
    for b in bars:
        if b > 0 and (not out or b - out[-1] >= 8):
            out.append(b)
    return [round(b * period / fps, 1) for b in out]


def _checkerboard(m: int) -> np.ndarray:
    """Gaussian-tapered checkerboard kernel (Foote novelty).

    Positive on the two diagonal quadrants, negative on the off-diagonal ones,
    so sliding it along the self-similarity diagonal scores "these two stretches
    resemble themselves but not each other" — i.e. a section boundary.
    """
    g = np.arange(-m, m) + 0.5
    x, y = np.meshgrid(g, g)
    k = (
        np.exp(-0.5 * ((x / (m / 2.0)) ** 2 + (y / (m / 2.0)) ** 2))
        * np.sign(x)
        * np.sign(y)
    )
    return k / np.abs(k).sum()


def _beat_features(sp: Spec, bpm: float) -> tuple[np.ndarray, float] | None:
    """Beat-synchronous chroma+timbre features, unit-normed per beat.

    Aggregating to beats first is the memory guard: an SSM at frame rate for a
    5-minute track would be 13k x 13k. At 120 BPM the same track is ~600 beats,
    so the SSM is ~1.4 MB. Beats are capped so a pathological tempo cannot blow
    that up.
    """
    if bpm <= 0 or sp.n_frames < 16:
        return None
    period = sp.fps * 60.0 / bpm
    n = int(sp.n_frames / period)
    if n < 16:
        return None
    while n > 2000:  # aggregate to bars rather than beats
        period *= 4.0
        n = int(sp.n_frames / period)
    edges = np.rint(np.arange(n + 1) * period).astype(int).clip(0, sp.n_frames)
    logmag = np.log1p(sp.mag)
    seg = [logmag[a:b].mean(axis=0) for a, b in zip(edges[:-1], edges[1:]) if b > a]
    if len(seg) < 16:
        return None
    beats = np.stack(seg)

    chroma = beats[:, _KEEP] @ _PROJ
    chroma /= np.maximum(chroma.sum(axis=1, keepdims=True), 1e-9)

    # 16 log-spaced band energies -> DCT-II. An MFCC in spirit, without scipy.
    band_edges = np.geomspace(60.0, SR / 2 * 0.95, 17)
    freqs = np.fft.rfftfreq(FRAME, 1.0 / SR)
    idx = np.digitize(freqs, band_edges) - 1
    bands = np.stack(
        [
            beats[:, idx == k].mean(axis=1)
            if (idx == k).any()
            else np.zeros(len(beats))
            for k in range(16)
        ],
        axis=1,
    )
    dct = np.cos(np.pi / 16 * (np.arange(16) + 0.5) * np.arange(13)[:, None])
    timbre = bands @ dct.T
    timbre = (timbre - timbre.mean(axis=0)) / (timbre.std(axis=0) + 1e-9)

    feat = np.hstack([chroma * 4.0, timbre * 0.5])  # chroma-dominant
    feat /= np.maximum(np.linalg.norm(feat, axis=1, keepdims=True), 1e-9)
    return feat, period


def estimate_boundaries(sp: Spec, bpm: float = 0.0) -> list[float]:
    """Estimate section boundaries in seconds.

    With a known tempo this uses a self-similarity matrix over beat-synchronous
    features and a checkerboard novelty kernel, then snaps to the bar grid. The
    old flux-minus-moving-average approach fired on essentially any transient —
    it returned 38 boundaries for a 5-minute track, which is the 8-second
    minimum-gap filter talking, not musical structure.

    Falls back to the old method when tempo is unknown, so the function stays
    total.
    """
    if sp.n_frames < 10:
        return []
    if bpm > 0:
        bf = _beat_features(sp, bpm)
        if bf is not None:
            feat, period = bf
            ssm = feat @ feat.T
            m = 16  # 4 bars of lag each side
            pad = np.pad(ssm, m, mode="edge")
            nov = np.array(
                [
                    (pad[i : i + 2 * m, i : i + 2 * m] * _checkerboard(m)).sum()
                    for i in range(len(ssm))
                ]
            )
            nov = np.maximum(nov, 0.0)
            if nov.any():
                return _pick_boundaries(nov, period, sp.fps)
    flux = sp.flux

    # Smooth flux using a moving average window
    window_len = int(SR / HOP * 2.0)  # 2-second window
    if len(flux) < window_len:
        return []
    smoothed = np.convolve(flux, np.ones(window_len) / window_len, mode="same")
    novelty = flux - smoothed

    # Peak-picking: local maxima above threshold
    threshold = novelty.mean() + novelty.std() * 0.8
    peaks = []
    fps = SR / HOP
    for i in range(1, len(novelty) - 1):
        if (
            novelty[i] > novelty[i - 1]
            and novelty[i] > novelty[i + 1]
            and novelty[i] > threshold
        ):
            time_sec = round(i / fps, 1)
            peaks.append(time_sec)

    # Filter peaks closer than 8 seconds
    filtered = []
    for p in peaks:
        if not filtered or (p - filtered[-1]) >= 8.0:
            filtered.append(p)

    return filtered


def analyze(path: Path) -> tuple[float, str, list[float]]:
    sp = spectra(decode_mono(path, SR))
    bpm = detect_tempo(sp)
    return bpm, detect_key(sp), estimate_boundaries(sp, bpm)


def stem_track_dir(p: Path) -> dict[str, Path] | None:
    """Return the stem files if `p` is a separated track folder, else None.

    Gated on drums AND bass both being present. That admits htdemucs (4-stem)
    and htdemucs_6s (which adds guitar/piano), while excluding an acapella split
    — that produces only vocals.wav and no_vocals.wav, which is not a track
    folder and should keep fanning out per file.
    """
    if not p.is_dir():
        return None
    found = {n: p / f"{n}.wav" for n in STEM_NAMES if (p / f"{n}.wav").is_file()}
    return found if {"drums", "bass"} <= found.keys() else None


def analyze_stem_track(stems: dict[str, Path]) -> tuple[float, str, list[float]]:
    """Analyze a separated track as ONE track, using the best stem per metric.

    Previously a Stems folder was rglobbed into one line per stem, so the
    reported "key" could come from drums.wav — which is meaningless. Each metric
    now reads the stem that carries it: drums for tempo (cleanest onsets), the
    pitched stems for key, and `other` for boundaries (harmonic change marks
    sections better than percussion does).
    """
    bpm = detect_tempo(spectra(decode_mono(stems["drums"], SR)))

    # Bass pins the tonic but cannot distinguish major from minor -- the third
    # lives in the mid stems. Weight bass below them rather than above.
    key_parts = [(stems["bass"], 0.6)]
    key_parts += [(stems[n], 1.0) for n in ("other", "guitar", "piano") if n in stems]
    chroma = np.zeros(12)
    for path, weight in key_parts:
        sp = spectra(decode_mono(path, SR))
        c = _chroma_vector(sp)
        if c is not None:
            chroma += weight * c
    key = _key_from_chroma(chroma)

    bounds_src = stems.get("other") or stems["bass"]
    bounds = estimate_boundaries(spectra(decode_mono(bounds_src, SR)), bpm)
    return bpm, key, bounds


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: analyze_track.py <audio file | folder>")
        sys.exit(1)
    p = Path(sys.argv[1])

    stems = stem_track_dir(p)
    if stems is not None:
        try:
            bpm, key, bounds = analyze_stem_track(stems)
            print(f"{p.name}:  {bpm} BPM   key {key}   transitions {bounds}")
        except Exception as exc:  # noqa: BLE001
            print(f"{p.name}:  analysis failed — {exc}")
            sys.exit(1)
        return

    if p.is_dir():
        files = sorted(f for f in p.rglob("*") if f.suffix.lower() in AUDIO_EXT)
    else:
        files = [p]
    if not files:
        print("No audio files found.")
        sys.exit(1)
    failed = False
    for f in files:
        try:
            bpm, key, bounds = analyze(f)
            print(f"{f.name}:  {bpm} BPM   key {key}   transitions {bounds}")
        except Exception as exc:  # noqa: BLE001
            print(f"{f.name}:  analysis failed — {exc}")
            failed = True
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
