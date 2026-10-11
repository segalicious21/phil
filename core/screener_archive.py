#!/usr/bin/env python3
"""Move past months of journal/screener.jsonl into gzip archives.

PROTECTED CORE — the trading agent must not edit files under core/.

Why (operator, 2026-10-11): screener.jsonl reached 58 MB and 122k rows,
past GitHub's 50 MB warning, at about 300 rows (0.14 MB) per FULL cycle.
GitHub refuses a push carrying a file over 100 MB, which would strand every
later cycle's commit. Gzip shrinks the rows about 8x, and nothing is lost.

What moves: the longest PREFIX of screener.jsonl whose rows all carry a ts
before the start of the current UTC month. It goes, byte for byte, into
journal/screener-archive/screener-through-<YYYY-MM>.jsonl.gz, named for the
month before the current one. Rows are not regrouped by month because the
journal is not in ts order (two runners interleave; on 2026-10-11, 1800
September rows sat after the first October row). Cutting a prefix keeps the
file order exactly: reading every archive in name order and then the live
file (iter_lines below) yields the original lines in the original order, so
every reader sees the same journal it saw before. A late row from an old
month that sits after a newer one simply stays in the live file until the
next rotation.

Safety: the archive is written to a temp file and read back; the live file
is rewritten to a temp file; only when archive + remainder equal the
original lines byte for byte are both renamed into place, archive first.
If a run dies between the two renames, the next run finds an archive whose
lines are exactly the live file's head and finishes the cut; any other
mismatch refuses and changes nothing. Gzip output is deterministic (no name,
mtime 0), so re-running never makes a spurious git diff.

Writers are unchanged: core/screen.py and core/screen_rank.py append to
the live file. Readers use iter_lines() / load_rows() so they see archive
plus live. loop.sh runs this before each cycle; it is a no-op until the
month turns.

Usage: python3 core/screener_archive.py [--dry-run]
"""
import argparse
import datetime as dt
import gzip
import io
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIVE = ROOT / "journal" / "screener.jsonl"
ARCHIVE_DIR = ROOT / "journal" / "screener-archive"
PATTERN = "screener-through-*.jsonl.gz"


def archives():
    """Archive files, oldest first (the YYYY-MM in the name sorts in time)."""
    return sorted(ARCHIVE_DIR.glob(PATTERN)) if ARCHIVE_DIR.is_dir() else []


def iter_lines():
    """Every journal line as text: archives in name order, then the live file.

    The order is exactly the order the lines were appended in."""
    for path in archives():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            yield from f
    if LIVE.is_file():
        with open(LIVE, encoding="utf-8") as f:
            yield from f


def load_rows():
    """Every journal row parsed, archive plus live, blank lines skipped."""
    return [json.loads(line) for line in iter_lines() if line.strip()]


def exists():
    return LIVE.is_file() or bool(archives())


def _gzip_bytes(lines):
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0,
                       compresslevel=9) as gz:
        gz.writelines(lines)
    return buf.getvalue()


def _ts_of(line):
    try:
        return str(json.loads(line).get("ts") or "")
    except (ValueError, AttributeError):
        return ""


def rotate(now, dry_run=False):
    """Archive the pre-month prefix. Returns a one-line summary."""
    if not LIVE.is_file():
        return "screener_archive: no live journal - nothing to do"
    month_start = now.strftime("%Y-%m-01T00:00:00Z")
    prev = (now.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
    target = ARCHIVE_DIR / f"screener-through-{prev}.jsonl.gz"
    lines = LIVE.read_bytes().splitlines(keepends=True)
    if lines and not lines[-1].endswith(b"\n"):
        return ("screener_archive: last line of the live journal has no "
                "newline (a write in progress?) - skipped this run")

    if target.exists():
        # A previous run wrote the archive; finish its cut if it died before
        # truncating, otherwise this month is already done.
        with gzip.open(target, "rb") as f:
            done = f.read().splitlines(keepends=True)
        if done and lines[:len(done)] == done:
            cut = len(done)
            if dry_run:
                return (f"screener_archive: would finish an interrupted cut "
                        f"({cut} lines already in {target.name})")
            tmp = LIVE.with_name(LIVE.name + ".tmp")
            tmp.write_bytes(b"".join(lines[cut:]))
            os.replace(tmp, LIVE)
            return (f"screener_archive: finished interrupted cut, removed "
                    f"{cut} archived lines from the live journal")
        return f"screener_archive: {target.name} exists - nothing to do"

    cut = 0
    for line in lines:
        ts = _ts_of(line)
        if not ts or ts >= month_start:
            break
        cut += 1
    if cut == 0:
        return "screener_archive: no rows before this month at the head - nothing to do"

    head, rest = lines[:cut], lines[cut:]
    blob = _gzip_bytes(head)
    if gzip.decompress(blob).splitlines(keepends=True) != head:
        raise SystemExit("screener_archive: gzip round trip mismatch - nothing changed")
    summary = (f"screener_archive: {cut} lines ({sum(map(len, head)) / 1048576:.1f} MB) "
               f"-> {target.parent.name}/{target.name} ({len(blob) / 1048576:.1f} MB); "
               f"{len(rest)} lines stay live")
    if dry_run:
        return summary + " [dry run]"

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_archive = target.with_name(target.name + ".tmp")
    tmp_live = LIVE.with_name(LIVE.name + ".tmp")
    tmp_archive.write_bytes(blob)
    tmp_live.write_bytes(b"".join(rest))
    with gzip.open(tmp_archive, "rb") as f:
        back = f.read().splitlines(keepends=True)
    if back + tmp_live.read_bytes().splitlines(keepends=True) != lines:
        tmp_archive.unlink()
        tmp_live.unlink()
        raise SystemExit("screener_archive: read-back mismatch - nothing changed")
    os.replace(tmp_archive, target)
    os.replace(tmp_live, LIVE)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would move, write nothing")
    args = ap.parse_args()
    print(rotate(dt.datetime.now(dt.timezone.utc), dry_run=args.dry_run))


if __name__ == "__main__":
    main()
