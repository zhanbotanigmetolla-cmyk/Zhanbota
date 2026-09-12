#!/usr/bin/env python3
"""Dated snapshots of the pullup bot's live databases.

Why this exists: the bot's database had no automated backup at all. Its most
recent copy was a hand-made one five weeks old, while fitness-mcp — which holds
data that could largely be re-imported from upstream archives — was being
snapshotted nightly. That is backwards. Every rep, streak and plan in
pullups.db exists nowhere else; if it is lost, no upstream can give it back.

Uses SQLite's online backup API rather than copying the file. The bot writes
continuously in WAL mode, and a plain `cp` of a live WAL database produces a
snapshot that looks fine until the day you actually need to open it.

Snapshots go in their own directory, deliberately. Hand-made checkpoints sit
beside the live database as `pullups.db.bak-<date>` — including deliberately
named milestones like `...-preweighted` — and an automated pruner that globbed
those would eventually delete the very snapshot someone took the trouble to
name. This one only ever prunes files it wrote itself.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import sqlite3
import sys
from pathlib import Path

log = logging.getLogger("backup_bot_db")

DATA_DIR = Path.home() / "data" / "pullup-bot"
DEST_DIR = DATA_DIR / "backups"
# Both databases matter. pullups.db is the training data; pullups_fsm.db holds
# in-flight conversation state, so restoring one without the other can leave a
# user mid-dialogue against a database that no longer knows about it.
DATABASES = ("pullups.db", "pullups_fsm.db")
KEEP = 14


def snapshot(db_path: Path, dest_dir: Path, keep: int) -> Path | None:
    if not db_path.exists():
        log.warning("no database at %s; skipping", db_path)
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.date.today().isoformat()
    dest = dest_dir / f"{db_path.name}.{stamp}"

    src = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=30)
    try:
        out = sqlite3.connect(dest)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()

    log.info("wrote %s (%.1f KB)", dest.name, dest.stat().st_size / 1024)
    _prune(db_path.name, dest_dir, keep)
    return dest


def _prune(db_name: str, dest_dir: Path, keep: int) -> None:
    """Keep the newest `keep` snapshots OF THIS DATABASE only.

    The glob is anchored to the database's own name so the two databases do not
    prune each other, and so nothing outside this directory is ever considered.
    """
    existing = sorted(dest_dir.glob(f"{db_name}.20*"))
    for old in existing[:-keep] if keep > 0 else []:
        old.unlink()
        log.info("pruned %s", old.name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot the pullup bot databases.")
    parser.add_argument("--keep", type=int, default=KEEP,
                        help=f"Dated snapshots to retain per database (default {KEEP}).")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--dest-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    dest_dir = args.dest_dir or (args.data_dir / "backups")

    failed = False
    for name in DATABASES:
        try:
            snapshot(args.data_dir / name, dest_dir, args.keep)
        except Exception as exc:  # noqa: BLE001 - one bad db must not skip the other
            log.error("backup of %s failed: %s: %s", name, type(exc).__name__, exc)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
