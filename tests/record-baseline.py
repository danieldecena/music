#!/usr/bin/env python3
"""
Record the current analyze_track.py output over the whole local corpus into
tests/baseline-analysis.tsv.

This is the frozen "before" snapshot. The algorithm is deterministic, so
test-analysis.py can replay it and prove that a refactor changed nothing and
that an algorithm change moved only what it claimed to move.

The corpus is local audio that is gitignored, so the recorded TSV is committed
but is only reproducible on this machine. Rows are sorted by path; paths are
stored relative to the repo root.

Usage:
    .venv/bin/python tests/record-baseline.py [--out tests/baseline-analysis.tsv]
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "Scripts"))

import analyze_track  # noqa: E402

AUDIO_EXT = (".m4a", ".mp3", ".wav", ".flac")
SOURCE_DIRS = ("Apple Music", "SoundCloud", "Downloads")
STEM_ROOT = "Stems"
HEADER = ("path", "bpm", "key", "n_boundaries", "first_3_boundaries")


def corpus() -> list[Path]:
    """Every source track, plus every individual stem .wav.

    Stems are recorded per file, not per folder, because that is what main()
    does today when handed a Stems/<model>/<track> directory — it rglobs and
    prints one line per stem. Recording folders instead would compare against
    behaviour that does not currently exist.
    """
    items: list[Path] = []
    for d in (*SOURCE_DIRS, STEM_ROOT):
        root = REPO / d
        if root.is_dir():
            items += [f for f in root.rglob("*") if f.suffix.lower() in AUDIO_EXT]
    return sorted(items)


def row(path: Path) -> tuple[str, ...]:
    rel = path.relative_to(REPO).as_posix()
    try:
        bpm, key, bounds = analyze_track.analyze(path)
    except Exception as exc:  # noqa: BLE001
        return (rel, "ERROR", type(exc).__name__, "", "")
    first3 = ",".join(str(b) for b in bounds[:3])
    return (rel, str(bpm), key, str(len(bounds)), first3)


def main() -> None:
    out = REPO / "tests" / "baseline-analysis.tsv"
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    files = corpus()
    if not files:
        print("No corpus found — nothing to record.", file=sys.stderr)
        sys.exit(1)
    lines = ["\t".join(HEADER)]
    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {f.name}", file=sys.stderr)
        lines.append("\t".join(row(f)))
    out.write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(files)} rows to {out.relative_to(REPO)}", file=sys.stderr)


if __name__ == "__main__":
    main()
