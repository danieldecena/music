"""Tests for the stem map generator.

Hand-rolled assertions, matching tests/test_regions.py.
Run: .venv/bin/python tests/test_build_stem_map.py

Both assertions exist because check 36 hashes the *generated* page. If a
rebuild that changed no data produced different bytes, every rebuild would read
as DRIFT and the check would train us to ignore it.
"""
import hashlib
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEN = ROOT / "Scripts" / "build_stem_map.py"
PY = ROOT / ".venv" / "bin" / "python"

_passed = 0
_failed = 0


def check(cond: bool, label: str) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"ok: {label}")
    else:
        _failed += 1
        print(f"FAIL: {label}")


def build(out: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(PY), str(GEN), "--out", str(out)],
                          capture_output=True, text=True)


def main() -> None:
    if not (ROOT / "catalog.sqlite").exists():
        print("no catalog.sqlite -- nothing to generate from")
        sys.exit(0)

    with tempfile.TemporaryDirectory() as d:
        a, b = pathlib.Path(d) / "a.html", pathlib.Path(d) / "b.html"
        r1, r2 = build(a), build(b)

        # A failing generator must not read as a passing test.
        check(r1.returncode == 0, f"generator exits 0 ({r1.stderr.strip()[:60]})")
        if r1.returncode != 0:
            print(f"\n{_passed} passed, {_failed} failed")
            sys.exit(1)
        check(r2.returncode == 0, "second run also exits 0")
        check(a.stat().st_size > 10_000, "output is a real page, not an empty shell")

        ha = hashlib.sha256(a.read_bytes()).hexdigest()
        hb = hashlib.sha256(b.read_bytes()).hexdigest()
        check(ha == hb,
              f"two builds of unchanged data are byte-identical ({ha[:12]} vs {hb[:12]})")

        text = a.read_text(encoding="utf-8")
        nonascii = sorted({c for c in text if ord(c) > 127})
        check(not nonascii,
              "page is pure ASCII, so it survives a missing charset declaration"
              + (f" (found {nonascii[:6]})" if nonascii else ""))

        # The data actually reached the page, rather than the template shipping
        # with its placeholder intact.
        check("__DATA__" not in text, "the data placeholder was substituted")
        check('"bars":' in text and '"loops":' in text, "the page carries track data")

    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
