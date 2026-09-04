"""Score MusicUnderstanding's output against this repo's existing labels.

Deliberately imports the established classifiers instead of writing new ones: a
second implementation of "is this an octave error" that disagreed with the first
would make the comparison meaningless.

Three columns per track:
  label  -- tests/fixtures-analysis.tsv, Echo Nest-derived and correlated
  ours   -- the LIVE analyzer, run per track. Deliberately not
            tests/baseline-analysis.tsv: that file is a frozen regression
            fixture predating the grid-lag tempo fix, and TASKS.md still
            carries "Re-record replay baseline" as open. Scoring against it
            would measure a past analyzer, not the current one.
  apple  -- Samples/Analysis/<stem>.json, written by Tools/mu-analyze

Run: .venv/bin/python tests/score_apple.py [analysis-dir]
"""
import collections
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Scripts"))

from catalog import apple_key_label  # noqa: E402
from harmonic_mix import key_compatible  # noqa: E402

# tests/test-analysis.py carries a hyphen and is not importable by name.
# Renaming it would break lib/music-core.sh callers, so load it by path.
_spec = importlib.util.spec_from_file_location(
    "_test_analysis", ROOT / "tests" / "test-analysis.py"
)
_ta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ta)

FIXTURES = ROOT / "tests" / "fixtures-analysis.tsv"
ANALYSIS = ROOT / "Samples" / "Analysis"


def bpm_class(got: float, want: float) -> str:
    return _ta._bpm_class(got, want)


def as_float(v) -> float:
    """mu-analyze encodes non-finite loudness as a string; JSON has no other
    way to carry -inf. Everything else arrives as a number."""
    return float(v)


def apple_key(value: dict) -> str:
    """Delegates to catalog.apple_key_label so the ingest path and the scoring
    path cannot drift apart."""
    return apple_key_label(value)


def key_class(ours: str, theirs: str) -> str:
    """Camelot relationship, so enharmonics collapse and a mode flip reads as
    'relative' rather than a miss."""
    if not ours or not theirs:
        return "no label"
    rel = key_compatible(ours, theirs)
    if rel == "perfect":
        return "exact"
    return rel or "unrelated"


def _num(s: str) -> float:
    """Fixture BPMs may carry a trailing '?' marking a suspect label."""
    s = re.sub(r"[^0-9.]", "", s or "")
    return float(s) if s else 0.0


def load_fixtures() -> dict:
    out = {}
    for line in FIXTURES.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        f = (line.split("\t") + ["", ""])[:3]
        out[pathlib.Path(f[0]).stem] = {
            "path": f[0],
            "bpm": _num(f[1]),
            "suspect": f[1].strip().endswith("?"),
            "key": f[2].strip(),
        }
    return out


def ours_live(rel_path: str) -> tuple[str, str]:
    """Run the current analyzer on one track. Lazy-imports analyze_track so the
    rest of this module stays usable without numpy."""
    p = ROOT / rel_path
    if not p.exists():
        return ("", "")
    try:
        import analyze_track as at

        sp = at.spectra(at.decode_mono(p, at.SR))
        return (f"{at.detect_tempo(sp):.1f}", at.detect_key(sp))
    except Exception:
        return ("", "")


def load_apple(d: pathlib.Path) -> dict:
    out = {}
    for p in sorted(d.glob("*.json")):
        r = json.loads(p.read_text())["result"]
        ranges = r.get("key", {}).get("ranges") or []
        out[p.stem] = {
            "bpm": float(r["rhythm"]["beatsPerMinute"]),
            "key": apple_key(ranges[0]["value"]) if ranges else "",
        }
    return out


def main() -> None:
    d = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ANALYSIS
    fx, apple = load_fixtures(), load_apple(d)
    if not apple:
        print(f"no analysis JSON in {d} -- run Tools/mu-analyze first")
        sys.exit(1)

    tb, sb, tk = collections.Counter(), collections.Counter(), collections.Counter()
    ob = collections.Counter()

    print(f"{'track':22} {'label':>6} {'ours':>7} {'apple':>7}  "
          f"{'apple bpm':<13}{'key l/a':<12} {'key':<9}")
    print("-" * 82)
    for stem in sorted(fx):
        f = fx[stem]
        a = apple.get(stem)
        if not a:
            print(f"{stem:22} {'':>6} {'':>7} {'':>7}  (not analyzed)")
            continue
        o_bpm, o_key = ours_live(f["path"])
        bc = bpm_class(a["bpm"], f["bpm"]) if f["bpm"] else "none"
        kc = key_class(a["key"], f["key"])
        mark = "?" if f["suspect"] else " "
        (sb if f["suspect"] else tb)[bc] += 1
        if not f["suspect"] and o_bpm not in ("", "ERROR"):
            ob[bpm_class(float(o_bpm), f["bpm"])] += 1
        tk[kc] += 1
        print(f"{stem:22} {f['bpm']:>5.0f}{mark}{o_bpm:>7} {a['bpm']:>7.1f}  "
              f"{bc:<13}{f['key'] + ' / ' + a['key']:<12} {kc:<9}")

    n_t = sum(tb.values())
    print(f"\nBPM, trusted labels (n={n_t}):")
    print(f"  apple: {dict(tb)}")
    print(f"  ours : {dict(ob)}")
    print(f"  apple octave errors: {tb['half'] + tb['double']}/{n_t}"
          f"   ours: {ob['half'] + ob['double']}/{sum(ob.values())}")
    print(f"\nBPM, suspect labels (excluded above): {dict(sb)}")
    n_k = sum(v for k, v in tk.items() if k != "no label")
    print(f"\nKEY, apple vs label (n={n_k}): {dict(tk)}")
    print(f"  exact {tk['exact']}/{n_k};"
          f" {tk['exact'] + tk['relative']}/{n_k} share the pitch-class set")


if __name__ == "__main__":
    main()
