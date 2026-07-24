#!/usr/bin/env python3
"""SQLite catalog + processing log for the music flip workspace.

Single source of truth over the filesystem: what source tracks exist, which have
been deconstructed (with BPM/key), every derived asset (stems, one-shots, kits,
loops, chops, vocals, MIDI, resynth), and a log of pipeline runs.

Stdlib only (sqlite3). DB lives at <MUSIC>/catalog.sqlite. Resolve <MUSIC> from
this file's location, or the LOGIC_STUDIO_MUSIC_ROOT env var.

Commands:
  init                              create/upgrade schema
  scan                              full rescan of the workspace
  index-track <name> [--bpm N --key K]
                                    refresh one track after deconstruct (used by
                                    the deconstruct hook); analyzes if bpm/key omitted
  set-analysis <name> --bpm N --key K
  record <action> <target> [--status ok] [--note ...]
  ready [--limit N] [--json]        deconstructed tracks + asset counts
  pending [--json]                  source tracks with no stems yet
  recent [--hours 24] [--json]      tracks deconstructed in the last N hours
  stats [--json]                    totals
"""

import argparse
import json
import os
import re
import subprocess
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harmonic_mix  # noqa: E402  (local module, same Scripts/ dir)

ROOT = Path(
    os.environ.get("LOGIC_STUDIO_MUSIC_ROOT", Path(__file__).resolve().parent.parent)
)
DB = ROOT / "catalog.sqlite"
AUDIO_EXT = {".m4a", ".mp3", ".wav", ".flac"}
SOURCE_DIRS = ["Apple Music", "SoundCloud", "Downloads"]
STEM_MODELS = ["htdemucs", "htdemucs_6s"]
ANALYZE_RE = re.compile(
    r"\b(\d{2,3}(?:\.\d+)?)\s*BPM\b.*?\bkey\s+([A-Ga-g][b#]?m?)", re.IGNORECASE
)


# Leading disc/track number on an Apple Music filename: "03 ", "1-01 ".
TRACK_NUM_RE = re.compile(r"^\d+(?:-\d+)?[ .\-_]+")


def song_title(name):
    """Display form of a catalog name: no path, no extension, no track number.

    Catalog names come from filenames, so they carry the numbering Apple Music
    writes ("1-01 SPEED DEMON"). That sorts a folder but reads badly in a mix
    listing. Strips one numeric prefix only, so a title that itself opens with a
    number ("10 502 Come Up") keeps it. Falls back to the input when stripping
    would leave nothing, so a track named "07" never renders blank.
    """
    if not name:
        return ""
    stem = Path(name).stem if Path(name).suffix.lower() in AUDIO_EXT else str(name)
    stem = Path(stem).name
    return TRACK_NUM_RE.sub("", stem).strip() or stem


def now():
    return datetime.now().isoformat(timespec="seconds")


def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
  name TEXT PRIMARY KEY,
  source_path TEXT,
  artist TEXT,
  album TEXT,
  bpm INTEGER,
  key TEXT,
  model TEXT,
  deconstructed_at TEXT,
  first_seen TEXT
);
CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  track TEXT,
  kind TEXT,
  subtype TEXT,
  path TEXT UNIQUE,
  mtime REAL
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, action TEXT, target TEXT, status TEXT, note TEXT
);
CREATE INDEX IF NOT EXISTS idx_assets_track ON assets(track);
CREATE INDEX IF NOT EXISTS idx_assets_kind ON assets(kind);
"""


def init(con):
    con.executescript(SCHEMA)
    con.commit()


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _upsert_track(con, name, **fields):
    con.execute(
        "INSERT INTO tracks(name, first_seen) VALUES(?,?) ON CONFLICT(name) DO NOTHING",
        (name, now()),
    )
    for k, v in fields.items():
        if v is None:
            continue
        if k == "deconstructed_at":
            con.execute(
                "UPDATE tracks SET deconstructed_at=? WHERE name=? AND (deconstructed_at IS NULL OR deconstructed_at='')",
                (v, name),
            )
        else:
            con.execute(f"UPDATE tracks SET {k}=? WHERE name=?", (v, name))


def _add_asset(con, track, kind, subtype, path: Path):
    try:
        mt = path.stat().st_mtime
    except OSError:
        mt = 0.0
    con.execute(
        "INSERT OR REPLACE INTO assets(track, kind, subtype, path, mtime) VALUES(?,?,?,?,?)",
        (track, kind, subtype, _rel(path), mt),
    )


def scan(con):
    init(con)
    con.execute("DELETE FROM assets")

    # --- source tracks ---
    for d in SOURCE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if f.is_file() and f.suffix.lower() in AUDIO_EXT:
                parts = f.relative_to(base).parts
                artist = parts[0] if len(parts) >= 2 else None
                album = parts[1] if len(parts) >= 3 else None
                _upsert_track(
                    con, f.stem, source_path=_rel(f), artist=artist, album=album
                )

    # --- stems ---
    for model in STEM_MODELS:
        base = ROOT / "Stems" / model
        if not base.exists():
            continue
        for track_dir in base.iterdir():
            if not track_dir.is_dir():
                continue
            name = track_dir.name
            _upsert_track(con, name, model=model, deconstructed_at=now())
            for wav in track_dir.glob("*.wav"):
                _add_asset(con, name, "stem", wav.stem, wav)

    # --- samples ---
    def scan_track_folders(root, kind):
        base = ROOT / "Samples" / root
        if not base.exists():
            return
        for track_dir in base.iterdir():
            if not track_dir.is_dir():
                continue
            name = track_dir.name
            _upsert_track(con, name)
            for f in track_dir.rglob("*"):
                if f.is_file() and f.suffix.lower() in {".wav", ".aif", ".aiff"}:
                    rel = f.relative_to(track_dir).parts
                    sub = rel[0] if len(rel) > 1 else re.sub(r"[_-]?\d+$", "", f.stem)
                    k = (
                        "kit"
                        if (
                            kind == "oneshot"
                            and len(rel) > 1
                            and rel[0] in ("kick", "snare", "hat")
                        )
                        else kind
                    )
                    _add_asset(con, name, k, sub, f)

    scan_track_folders("One-Shots", "oneshot")
    scan_track_folders("Chops", "chop")
    scan_track_folders("Vocals", "vocal")
    scan_track_folders("Resynth", "resynth")
    scan_track_folders("Mangled", "mangled")

    loops = ROOT / "Samples" / "Loops"
    if loops.exists():
        for f in loops.rglob("*.wav"):
            _add_asset(con, f.stem, "loop", None, f)
    midi = ROOT / "Samples" / "MIDI"
    if midi.exists():
        for f in midi.rglob("*.mid"):
            _add_asset(con, f.stem, "midi", None, f)

    con.commit()


def _analyze(source_rel):
    """Run analyze_track.py on a source file; return (bpm, key) or (None, None)."""
    src = ROOT / source_rel
    py = ROOT / ".venv" / "bin" / "python"
    script = ROOT / "Scripts" / "analyze_track.py"
    if not (src.exists() and py.exists() and script.exists()):
        return None, None
    try:
        out = subprocess.run(
            [str(py), str(script), str(src)],
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout
    except Exception:
        return None, None
    m = ANALYZE_RE.search(out)
    if m:
        return round(float(m.group(1))), m.group(2)
    return None, None


def index_track(con, name, bpm=None, key=None):
    init(con)
    if bpm is None or key is None:
        row = con.execute(
            "SELECT source_path FROM tracks WHERE name=?", (name,)
        ).fetchone()
        src = row["source_path"] if row else None
        if src:
            abpm, akey = _analyze(src)
            bpm = bpm or abpm
            key = key or akey
    _upsert_track(con, name, bpm=bpm, key=key)
    con.commit()
    scan(con)  # refresh assets + model/deconstructed_at
    con.execute(
        "INSERT INTO runs(ts, action, target, status, note) VALUES(?,?,?,?,?)",
        (now(), "index-track", name, "ok", f"bpm={bpm} key={key}"),
    )
    con.commit()


def backfill(con, limit=None, refresh=False):
    """Fill BPM/key for already-deconstructed tracks that predate the index hook.

    `refresh` re-analyzes every track with a source file instead, overwriting
    values that are already there. Needed because the default only fills NULLs,
    which cannot repair rows analyzed by a superseded estimator.
    """
    init(con)
    where = (
        "source_path IS NOT NULL"
        if refresh
        else "model IS NOT NULL AND (bpm IS NULL OR key IS NULL) AND source_path IS NOT NULL"
    )
    rows = con.execute(
        f"SELECT name, source_path FROM tracks WHERE {where} "
        "ORDER BY deconstructed_at DESC"
    ).fetchall()
    if limit:
        rows = rows[:limit]
    done = 0
    for r in rows:
        bpm, key = _analyze(r["source_path"])
        if bpm or key:
            _upsert_track(con, r["name"], bpm=bpm, key=key)
            con.commit()
            done += 1
            print(f"{r['name']}: {bpm} BPM  key {key}", flush=True)
        else:
            print(f"{r['name']}: analysis failed", flush=True)
    con.execute(
        "INSERT INTO runs(ts,action,target,status,note) VALUES(?,?,?,?,?)",
        (now(), "backfill", "tracks", "ok", f"{done}/{len(rows)}"),
    )
    con.commit()
    print(f"backfilled {done}/{len(rows)}")


def _counts_for(con, name):
    rows = con.execute(
        "SELECT kind, COUNT(*) c FROM assets WHERE track=? GROUP BY kind", (name,)
    ).fetchall()
    return {r["kind"]: r["c"] for r in rows}


def cmd_ready(con, limit, as_json):
    init(con)
    rows = con.execute(
        "SELECT * FROM tracks WHERE model IS NOT NULL ORDER BY deconstructed_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    out = []
    for r in rows:
        c = _counts_for(con, r["name"])
        out.append(
            {
                "track": r["name"],
                "bpm": r["bpm"],
                "key": r["key"],
                "model": r["model"],
                "deconstructed_at": r["deconstructed_at"],
                "stems": c.get("stem", 0),
                "oneshots": c.get("oneshot", 0),
                "kit": c.get("kit", 0),
                "chops": c.get("chop", 0),
                "vocals": c.get("vocal", 0),
            }
        )
    if as_json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        for o in out:
            print(
                f"{song_title(o['track'])}  —  {o['bpm'] or '?'} BPM  key {o['key'] or '?'}  "
                f"[{o['stems']} stems, {o['kit']} kit, {o['oneshots']} one-shots, {o['chops']} chops, {o['vocals']} vocals]"
            )
        if not out:
            print("(nothing deconstructed yet)")


def cmd_pending(con, as_json):
    init(con)
    rows = con.execute(
        "SELECT name, source_path FROM tracks WHERE model IS NULL AND source_path IS NOT NULL ORDER BY first_seen"
    ).fetchall()
    data = [{"track": r["name"], "source_path": r["source_path"]} for r in rows]
    print(
        json.dumps(data, ensure_ascii=False)
        if as_json
        else "\n".join(d["source_path"] for d in data) or "(none)"
    )


def cmd_recent(con, hours, as_json):
    init(con)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    rows = con.execute(
        "SELECT * FROM tracks WHERE deconstructed_at >= ? ORDER BY deconstructed_at DESC",
        (cutoff,),
    ).fetchall()
    out = [
        {
            "track": r["name"],
            "bpm": r["bpm"],
            "key": r["key"],
            "counts": _counts_for(con, r["name"]),
        }
        for r in rows
    ]
    if as_json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        for o in out:
            print(f"{o['track']}  {o['bpm'] or '?'} BPM key {o['key'] or '?'}")
        if not out:
            print(f"(no tracks deconstructed in the last {hours}h)")


def cmd_stats(con, as_json):
    init(con)
    t = con.execute("SELECT COUNT(*) c FROM tracks").fetchone()["c"]
    d = con.execute("SELECT COUNT(*) c FROM tracks WHERE model IS NOT NULL").fetchone()[
        "c"
    ]
    kinds = {
        r["kind"]: r["c"]
        for r in con.execute(
            "SELECT kind, COUNT(*) c FROM assets GROUP BY kind"
        ).fetchall()
    }
    stats = {"tracks": t, "deconstructed": d, "pending": t - d, "assets": kinds}
    if as_json:
        print(json.dumps(stats, ensure_ascii=False))
    else:
        print(f"tracks: {t}  (deconstructed {d}, pending {t - d})")
        print(
            "assets: "
            + (", ".join(f"{k}={v}" for k, v in sorted(kinds.items())) or "none")
        )


def _search_rows(con, query):
    init(con)
    params = []
    where = ""
    if query:
        like = f"%{query.lower()}%"
        where = (
            "WHERE lower(name) LIKE ? OR lower(coalesce(artist,'')) LIKE ? "
            "OR lower(coalesce(album,'')) LIKE ? "
        )
        params = [like, like, like]
    sql = (
        "SELECT name, source_path, artist, album, bpm, key, model, deconstructed_at "
        f"FROM tracks {where}"
        "ORDER BY (model IS NULL), deconstructed_at DESC, name"
    )
    out = []
    for r in con.execute(sql, params).fetchall():
        c = _counts_for(con, r["name"])
        out.append(
            {
                "name": r["name"],
                "source_path": r["source_path"],
                "artist": r["artist"],
                "album": r["album"],
                "bpm": r["bpm"],
                "key": r["key"],
                "model": r["model"],
                "deconstructed_at": r["deconstructed_at"],
                "stems": c.get("stem", 0),
                "kit": c.get("kit", 0),
                "oneshots": c.get("oneshot", 0),
                "chops": c.get("chop", 0),
                "vocals": c.get("vocal", 0),
            }
        )
    return out


def _label(row):
    title = song_title(row["name"])
    who = f"{row['artist']} / {title}" if row["artist"] else title
    bpm = f"{row['bpm']} BPM" if row["bpm"] else "? BPM"
    key = row["key"] or "?"
    if row["model"]:
        segs = []
        if row["stems"]:
            segs.append(f"{row['stems']} stems")
        if row["kit"]:
            segs.append("kit")
        if row["oneshots"]:
            segs.append(f"{row['oneshots']} shots")
        badge = "deconstructed" + (": " + ", ".join(segs) if segs else "")
    else:
        badge = "source only"
    return f"{who}  {bpm}  {key}  [{badge}]"


def cmd_search(con, query, as_json, menu):
    rows = _search_rows(con, query)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False))
    elif menu:
        for r in rows:
            print(f"{r['name']}\t{r['source_path'] or ''}\t{_label(r)}")
    else:
        for i, r in enumerate(rows, 1):
            print(f"{i:3d}) {_label(r)}")
        if not rows:
            print("(no matches)")


def _mix_track_label(t):
    who = f"{t['artist']} — " if t.get("artist") else ""
    return f"{who}{song_title(t['name'])} ({t['key']}/{t['bpm']})"


def _lyric_rerank(pairs):
    """Fetch lyrics for the strong pairs, set lyric_sim, re-sort. Returns True if
    any lyrics were missing. Fully degrade-safe -- lyrics.py never raises, and a
    missing lyric just leaves that pair scored by audio (lyric_sim 0)."""
    import re as _re

    import lyrics as _lyrics

    cache: dict = {}
    missing = False

    def _get(t):
        nonlocal missing
        name = t["name"]
        if name not in cache:
            title = _re.sub(r"^\d+\s+", "", name)  # drop a leading track number
            cache[name] = _lyrics.fetch_lyrics(t.get("artist"), title)
            if cache[name] is None:
                missing = True
        return cache[name]

    for p in pairs:
        if p["tier"] == "strong":
            p["lyric_sim"] = _lyrics.lyric_similarity(_get(p["a"]), _get(p["b"]))
    harmonic_mix.sort_pairs(pairs)
    return missing


def cmd_mix(con, tol, limit, as_json, use_lyrics=False):
    """Rank catalog track pairs that mix well (Camelot key + tempo). Returns an
    exit code: 1 when there are too few analyzed tracks, else 0."""
    init(con)
    rows = con.execute(
        "SELECT name, artist, bpm, key FROM tracks "
        "WHERE bpm IS NOT NULL AND key IS NOT NULL AND key != '' AND key != 'unknown'"
    ).fetchall()
    tracks = [
        {"name": r["name"], "artist": r["artist"], "bpm": r["bpm"], "key": r["key"]}
        for r in rows
    ]
    if len(tracks) < 2:
        print(
            f"need at least 2 analyzed tracks to find mixes (have {len(tracks)}) — "
            "download + deconstruct more first"
        )
        return 1

    pairs = harmonic_mix.rank_pairs(tracks, tol)
    lyrics_missing = _lyric_rerank(pairs) if use_lyrics else False
    if limit:
        pairs = pairs[:limit]

    if as_json:
        flat = [
            {
                "a": p["a"]["name"],
                "b": p["b"]["name"],
                "tier": p["tier"],
                "key_rel": p["key_rel"],
                "a_key": p["a"]["key"],
                "a_bpm": p["a"]["bpm"],
                "b_key": p["b"]["key"],
                "b_bpm": p["b"]["bpm"],
                "tempo_gap": p["tempo_gap"],
                "half_double": p["half_double"],
                "lyric_sim": p["lyric_sim"],
            }
            for p in pairs
        ]
        print(json.dumps(flat, ensure_ascii=False))
        return 0

    print(
        f"{len(pairs)} compatible pair(s) from {len(tracks)} analyzed tracks "
        f"(tempo tol ±{tol * 100:.0f}%)"
    )
    if use_lyrics and lyrics_missing:
        print("  (some lyrics unavailable — those pairs ranked by audio only)")
    print()
    for p in pairs:
        note = p["key_rel"] or "—"
        if p["half_double"]:
            note += ", ½/2x tempo"
        elif p["tier"] != "key-only":
            note += f", Δ{p['tempo_gap']} BPM"
        if p["lyric_sim"]:
            note += f", lyric {p['lyric_sim']:.2f}"
        print(
            f"[{p['tier']:^10}] {_mix_track_label(p['a'])}  x  "
            f"{_mix_track_label(p['b'])}   ({note})"
        )
    if not pairs:
        print("(no compatible pairs — keys/tempos are all too far apart)")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="catalog.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("scan")
    p = sub.add_parser("index-track")
    p.add_argument("name")
    p.add_argument("--bpm", type=int)
    p.add_argument("--key")
    p = sub.add_parser("set-analysis")
    p.add_argument("name")
    p.add_argument("--bpm", type=int, required=True)
    p.add_argument("--key", required=True)
    p = sub.add_parser("record")
    p.add_argument("action")
    p.add_argument("target")
    p.add_argument("--status", default="ok")
    p.add_argument("--note", default="")
    p = sub.add_parser("ready")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("pending")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("recent")
    p.add_argument("--hours", type=int, default=24)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("stats")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("backfill")
    p.add_argument("--limit", type=int)
    p.add_argument(
        "--refresh",
        action="store_true",
        help="re-analyze every track with a source file, overwriting existing bpm/key",
    )
    p = sub.add_parser("search")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--json", action="store_true")
    p.add_argument("--menu", action="store_true")
    p = sub.add_parser("mix")
    p.add_argument("--tempo-tol", type=float, default=0.06)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--json", action="store_true")
    p.add_argument("--lyrics", action="store_true")
    ns = ap.parse_args(argv)

    con = connect()
    try:
        if ns.cmd == "init":
            init(con)
            print(f"initialized {DB}")
        elif ns.cmd == "scan":
            scan(con)
            con.execute(
                "INSERT INTO runs(ts,action,target,status,note) VALUES(?,?,?,?,?)",
                (now(), "scan", "workspace", "ok", ""),
            )
            con.commit()
            cmd_stats(con, False)
        elif ns.cmd == "index-track":
            index_track(con, ns.name, ns.bpm, ns.key)
            print(f"indexed {ns.name}")
        elif ns.cmd == "set-analysis":
            init(con)
            _upsert_track(con, ns.name, bpm=ns.bpm, key=ns.key)
            con.commit()
            print("ok")
        elif ns.cmd == "record":
            init(con)
            con.execute(
                "INSERT INTO runs(ts,action,target,status,note) VALUES(?,?,?,?,?)",
                (now(), ns.action, ns.target, ns.status, ns.note),
            )
            con.commit()
            print("logged")
        elif ns.cmd == "ready":
            cmd_ready(con, ns.limit, ns.json)
        elif ns.cmd == "pending":
            cmd_pending(con, ns.json)
        elif ns.cmd == "recent":
            cmd_recent(con, ns.hours, ns.json)
        elif ns.cmd == "stats":
            cmd_stats(con, ns.json)
        elif ns.cmd == "backfill":
            backfill(con, ns.limit, ns.refresh)
        elif ns.cmd == "search":
            cmd_search(con, ns.query, ns.json, ns.menu)
        elif ns.cmd == "mix":
            return cmd_mix(con, ns.tempo_tol, ns.limit, ns.json, ns.lyrics)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
