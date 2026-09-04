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
import tempfile
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harmonic_mix  # noqa: E402  (local module, same Scripts/ dir)
import mix_preview  # noqa: E402
import mix_report  # noqa: E402

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

-- Per-track time series, one row per event, written by `ingest` from the JSON
-- Tools/mu-analyze produces. All times are seconds: MusicUnderstanding encodes
-- CMTime as {epoch, flags, timescale, value}, so ingest divides before storing.
CREATE TABLE IF NOT EXISTS beats (
  track TEXT, idx INTEGER, t REAL, bar INTEGER, beat_in_bar INTEGER
);
CREATE TABLE IF NOT EXISTS bars (track TEXT, idx INTEGER, t REAL);
CREATE TABLE IF NOT EXISTS sections (
  track TEXT, idx INTEGER, label TEXT, start_s REAL, end_s REAL
);
CREATE TABLE IF NOT EXISTS key_ranges (
  track TEXT, idx INTEGER, tonic TEXT, mode TEXT, start_s REAL, end_s REAL
);
-- momentary/short_term are NULL where the source reported a non-finite LUFS
-- (digital silence); mu-analyze emits those as the strings "inf"/"-inf"/"nan".
CREATE TABLE IF NOT EXISTS loudness (
  track TEXT, t REAL, momentary REAL, short_term REAL
);
CREATE TABLE IF NOT EXISTS instrument_activity (
  track TEXT, instrument TEXT, start_s REAL, end_s REAL, level REAL
);
CREATE TABLE IF NOT EXISTS lyrics (
  track TEXT, start_s REAL, end_s REAL, text TEXT
);

-- One table for every product. A loop candidate, a social-clip hook, a
-- vocal-free span and a safe cut point are all a scored, musically-aligned
-- span; `kind` discriminates. A new product is a new kind and a new scorer,
-- not a schema change.
CREATE TABLE IF NOT EXISTS regions (
  track TEXT, kind TEXT, start_s REAL, end_s REAL,
  start_bar INTEGER, n_bars INTEGER, score REAL, meta_json TEXT
);
-- Cross-track compatibility, populated from harmonic_mix.rank_pairs.
CREATE TABLE IF NOT EXISTS pairs (
  a TEXT, b TEXT, tempo_ok INTEGER, tempo_ratio REAL,
  key_relation TEXT, score REAL
);

CREATE INDEX IF NOT EXISTS idx_beats_track ON beats(track);
CREATE INDEX IF NOT EXISTS idx_sections_track ON sections(track);
CREATE INDEX IF NOT EXISTS idx_activity_track ON instrument_activity(track);
CREATE INDEX IF NOT EXISTS idx_regions_track_kind ON regions(track, kind);
"""

# Added to `tracks` after the fact. SQLite has no ADD COLUMN IF NOT EXISTS, so
# init diffs against PRAGMA table_info rather than catching an error. The
# original bpm/key columns stay alongside apple_bpm/apple_key on purpose:
# tests/score_apple.py compares the two, and nothing is replaced before that
# comparison says so.
TRACK_ANALYSIS_COLUMNS = {
    "duration_s": "REAL",
    "apple_bpm": "REAL",
    "apple_key": "TEXT",
    "pace": "REAL",
    "lufs_integrated": "REAL",
    "true_peak": "REAL",
    "analyzed_at": "TEXT",
    "analysis_version": "TEXT",
}


def init(con):
    con.executescript(SCHEMA)
    have = {r[1] for r in con.execute("PRAGMA table_info(tracks)")}
    for col, decl in TRACK_ANALYSIS_COLUMNS.items():
        if col not in have:
            con.execute(f"ALTER TABLE tracks ADD COLUMN {col} {decl}")
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


def _playable(rel_path):
    """True if ffprobe can read a duration out of the file."""
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(ROOT / rel_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
        return float(out) > 0
    except Exception:
        return False


def pick_source(candidates, probe=_playable):
    """Choose one source file for a track name; return (winner, shadowed).

    Two files collide when they share a filename stem -- the same song on two
    albums, or a stray duplicate. The name has to stay the key: Stems/ and
    Samples/ folders on disk are named for the bare stem, so keying tracks by
    album instead would orphan every derived asset from its track. The choice
    is only which file the name points at.

    Decodability decides, and nothing else does. File size looks like the
    obvious proxy and is measurably an anti-signal: the corrupt copy of
    "03 Exchange" is the BIGGER one (12.0 MB against the good file's 6.7 MB),
    so a size rule picks exactly wrong on the only real collision in the
    library. Path breaks ties so a rescan never reshuffles the catalog.

    Only ever called on a collision, so the ffprobe cost is rare. `probe` is
    injected so the choice stays testable without ffmpeg.
    """
    if len(candidates) == 1:
        return candidates[0], []
    ordered = sorted(candidates, key=lambda c: (not probe(c["path"]), c["path"]))
    return ordered[0], ordered[1:]


def scan(con):
    """Full rescan. Returns the list of filename-stem collisions it resolved."""
    init(con)
    con.execute("DELETE FROM assets")

    # --- source tracks ---
    by_name = {}
    for d in SOURCE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if f.is_file() and f.suffix.lower() in AUDIO_EXT:
                parts = f.relative_to(base).parts
                try:
                    size = f.stat().st_size
                except OSError:
                    size = 0
                by_name.setdefault(f.stem, []).append(
                    {
                        "path": _rel(f),
                        "size": size,
                        "artist": parts[0] if len(parts) >= 2 else None,
                        "album": parts[1] if len(parts) >= 3 else None,
                    }
                )

    conflicts = []
    for name in sorted(by_name):
        win, shadowed = pick_source(by_name[name])
        if shadowed:
            conflicts.append(
                {
                    "name": name,
                    "chosen": win["path"],
                    "shadowed": [s["path"] for s in shadowed],
                }
            )
        _upsert_track(
            con,
            name,
            source_path=win["path"],
            artist=win["artist"],
            album=win["album"],
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
    return conflicts


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


def resolve_seed(con, query):
    """Find the one analyzed track a seed query names: (row, status).

    status is 'ok', 'nomatch', or 'ambiguous'. Only tracks carrying both bpm and
    key can seed a mix -- an unanalyzed track has nothing to match against, so it
    reads as nomatch rather than a match that returns no pairs.

    An exact title hit wins over a longer substring match, so seeding "Solo" is
    not blocked by "Solo (Reprise)". Anything still ambiguous refuses to guess.
    """
    rows = [r for r in _search_rows(con, query) if r["bpm"] and r["key"]]
    if not rows:
        return None, "nomatch"
    if len(rows) == 1:
        return rows[0], "ok"
    q = (query or "").strip().lower()
    exact = [r for r in rows if song_title(r["name"]).lower() == q]
    if len(exact) == 1:
        return exact[0], "ok"
    return None, "ambiguous"


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


def _source_path(con, name):
    row = con.execute("SELECT source_path FROM tracks WHERE name=?", (name,)).fetchone()
    return row["source_path"] if row else None


def _seeded_mix(con, tracks, seed_query, tol, limit, as_json, use_lyrics, preview):
    """Rank one track against the rest, render, and optionally play the top pair."""
    row, status = resolve_seed(con, seed_query)
    if status == "nomatch":
        print(
            f"no analyzed track matches {seed_query!r} — "
            f"try: catalog.py search {seed_query!r}"
        )
        return 1
    if status == "ambiguous":
        print(f"{seed_query!r} matches more than one analyzed track:")
        for r in _search_rows(con, seed_query):
            if r["bpm"] and r["key"]:
                print(f"  {song_title(r['name'])}")
        return 1

    seed_name = row["name"]
    pairs = [
        p
        for p in harmonic_mix.rank_pairs(tracks, tol)
        if p["a"]["name"] == seed_name or p["b"]["name"] == seed_name
    ]
    # Orient every pair seed-first so the report reads "seed x partner".
    for p in pairs:
        if p["b"]["name"] == seed_name:
            p["a"], p["b"] = p["b"], p["a"]

    words_by_pair = {}
    if use_lyrics:
        import lyrics as _lyrics

        texts = {
            t["name"]: _lyrics.fetch_lyrics(
                t.get("artist"),
                song_title(t["name"]),
                source_path=_source_path(con, t["name"]),
            )
            for t in tracks
        }
        df, n = _lyrics.word_index(texts.values())
        for p in pairs:
            ta, tb = texts.get(p["a"]["name"]), texts.get(p["b"]["name"])
            p["lyric_sim"] = _lyrics.lyric_similarity(ta, tb, df, n)
            words_by_pair[id(p)] = _lyrics.shared_words(ta, tb, df)
        harmonic_mix.sort_pairs(pairs)

    seed_track = {
        "name": row["name"],
        "artist": row["artist"],
        "bpm": row["bpm"],
        "key": row["key"],
    }
    misses = mix_report.near_misses(seed_track, tracks, tol)
    shown = pairs[:limit] if limit else pairs
    report = mix_report.build_report(seed_track, shown, words_by_pair, misses)

    if as_json:
        print(json.dumps(report, ensure_ascii=False, default=str))
    else:
        print(mix_report.render_text(report))

    if preview and shown:
        _play_preview(con, shown[0])
    elif preview:
        print("\nnothing to preview — no compatible pair")
    return 0


def _excerpt_start(path: Path, bpm: float) -> float:
    """Where mix_preview should start this track — the first section boundary,
    not an arbitrary offset. Falls back to mix_preview's own duration*0.25
    guess if analysis fails, so a bad decode never blocks the preview."""
    try:
        import analyze_track as A

        sp = A.spectra(A.decode_mono(path, A.SR))
        duration = sp.n_frames / sp.fps
        transitions = A.estimate_boundaries(sp, bpm or 0.0)
    except Exception as e:
        print(
            f"  ({path.name}: boundary estimate failed, using a fallback start — {e})"
        )
        return mix_preview.excerpt_start([], 0.0)
    return mix_preview.excerpt_start(transitions, duration)


def _play_preview(con, pair):
    """Render the pair to a temp wav and play it. Never fails the whole report."""
    paths = {}
    for side in ("a", "b"):
        src = _source_path(con, pair[side]["name"])
        if not src:
            print(f"\nno source file for {pair[side]['name']} — cannot preview")
            return
        paths[side] = ROOT / src

    ratio = mix_preview.atempo_ratio(pair["a"]["bpm"], pair["b"]["bpm"])
    a_start = _excerpt_start(paths["a"], pair["a"]["bpm"])
    b_start = _excerpt_start(paths["b"], pair["b"]["bpm"])
    out = Path(tempfile.gettempdir()) / "music-mix-preview.wav"
    args = mix_preview.preview_args(
        paths["a"], paths["b"], ratio, out, a_start, b_start
    )
    print(f"\nrendering preview -> {out}")
    if mix_preview.render(args):
        mix_preview.play(out)


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


def cmd_mix(con, tol, limit, as_json, use_lyrics=False, seed=None, preview=False):
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

    if preview and not seed:
        print("--preview needs --seed (there is no single pair to preview otherwise)")
        return 1

    if seed:
        return _seeded_mix(con, tracks, seed, tol, limit, as_json, use_lyrics, preview)

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
    p.add_argument(
        "--seed", help="rank partners for one track instead of the whole library"
    )
    p.add_argument(
        "--preview",
        action="store_true",
        help="render and play a tempo-matched crossfade of the top pair (implies --seed)",
    )
    ns = ap.parse_args(argv)

    con = connect()
    try:
        if ns.cmd == "init":
            init(con)
            print(f"initialized {DB}")
        elif ns.cmd == "scan":
            conflicts = scan(con)
            for c in conflicts:
                print(f"note: two files are named {song_title(c['name'])!r}")
                print(f"      indexed  {c['chosen']}")
                for s in c["shadowed"]:
                    print(f"      shadowed {s}")
            con.execute(
                "INSERT INTO runs(ts,action,target,status,note) VALUES(?,?,?,?,?)",
                (
                    now(),
                    "scan",
                    "workspace",
                    "ok",
                    f"{len(conflicts)} name collisions" if conflicts else "",
                ),
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
            return cmd_mix(
                con, ns.tempo_tol, ns.limit, ns.json, ns.lyrics, ns.seed, ns.preview
            )
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
