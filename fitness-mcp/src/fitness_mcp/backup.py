"""Dated snapshots of fitness-mcp's database: ``python -m fitness_mcp.backup``.

This database is the source of truth for imported data. The Xiaomi and Strava
archives could in principle be re-imported, but the merge decisions, the
deduplication state and anything pushed from the phone exist only here — so
losing it means losing work that no upstream can give back.

Uses SQLite's online backup API rather than copying the file, because the
server and the hourly sync may be mid-write. Copying a live WAL database
produces a corrupt snapshot that looks fine until you try to open it.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import sqlite3
import sys
from pathlib import Path

from . import config

log = logging.getLogger("fitness_mcp.backup")

KEEP = 7


def make_backup(db_path: Path, keep: int = KEEP) -> Path | None:
    if not db_path.exists():
        log.warning("no database at %s; nothing to back up", db_path)
        return None

    stamp = datetime.date.today().isoformat()
    dest = db_path.with_name(f"{db_path.name}.bak-{stamp}")

    src = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        out = sqlite3.connect(dest)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()

    log.info("wrote %s (%.1f KB)", dest.name, dest.stat().st_size / 1024)
    _prune(db_path, keep)
    return dest


def _prune(db_path: Path, keep: int) -> None:
    """Keep the newest `keep` snapshots; a disk full of them helps nobody."""
    backups = sorted(db_path.parent.glob(f"{db_path.name}.bak-*"))
    for old in backups[:-keep] if keep > 0 else []:
        old.unlink()
        log.info("pruned %s", old.name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot the fitness-mcp database.")
    parser.add_argument("--keep", type=int, default=KEEP,
                        help=f"How many dated snapshots to retain (default {KEEP}).")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        make_backup(Path(config.DB_PATH), args.keep)
    except Exception as exc:  # noqa: BLE001 - a failed backup must not page anyone at 3am
        log.error("backup failed: %s: %s", type(exc).__name__, exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
