"""Command-line ingest runner: ``python -m fitness_mcp.ingest_cli``.

Ingest is deliberately separate from the server. The server only reads; nothing
a Claude conversation can do triggers an import.
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import config, db
from .ingest.base import run_adapter
from .ingest.pullup_bot import PullupBotAdapter
from .ingest.strava_export import StravaExportAdapter
from .ingest.xiaomi_export import XiaomiExportAdapter

log = logging.getLogger("fitness_mcp.ingest_cli")

ADAPTERS = {"pullup_bot", "strava_export", "xiaomi_export"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import workout data into fitness-mcp.")
    parser.add_argument(
        "--source", default="pullup_bot", choices=sorted(ADAPTERS),
        help="Which adapter to run (default: pullup_bot).",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print every data-quality warning.",
    )
    parser.add_argument(
        "--dedupe", action="store_true",
        help="After importing, merge activities recorded by two sources. Never "
             "automatic: merging is the one step here that can lose information "
             "if the heuristics are wrong.",
    )
    parser.add_argument(
        "--dedupe-only", action="store_true", help="Run deduplication without importing.",
    )
    parser.add_argument(
        "--archive", help="Path to the Strava bulk-export zip (source: strava_export).",
    )
    parser.add_argument(
        "--export-dir", help="Path to the Mi Fitness export directory (source: xiaomi_export).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.dedupe_only:
        conn = db.connect(config.DB_PATH)
        db.migrate(conn)
        return _dedupe(conn)

    if args.source == "pullup_bot":
        adapter = PullupBotAdapter(
            bot_db_path=str(config.PULLUP_BOT_DB), owner_tg_id=config.owner_tg_id()
        )
    elif args.source == "strava_export":
        adapter = StravaExportAdapter(archive_path=args.archive or str(config.STRAVA_ARCHIVE))
    elif args.source == "xiaomi_export":
        adapter = XiaomiExportAdapter(export_dir=args.export_dir or str(config.XIAOMI_EXPORT_DIR))
    else:  # pragma: no cover - argparse restricts this
        raise SystemExit(f"unknown source {args.source}")

    conn = db.connect(config.DB_PATH)
    db.migrate(conn)
    result = run_adapter(conn, adapter)

    if result.failed:
        log.error("ingest from %s FAILED: %s", result.source, result.error)
        log.error("database left unchanged")
        return 1

    log.info(
        "ingest from %s: %d created, %d updated (%d total), %d daily metrics",
        result.source, result.created, result.updated, result.total, result.daily_metrics,
    )
    if result.warnings:
        log.warning("%d data-quality warning(s) from the source", len(result.warnings))
        shown = result.warnings if args.verbose else result.warnings[:5]
        for w in shown:
            log.warning("  %s", w)
        if not args.verbose and len(result.warnings) > len(shown):
            log.warning("  ... %d more (use --verbose)", len(result.warnings) - len(shown))

    if args.dedupe:
        return _dedupe(conn)
    return 0


def _dedupe(conn) -> int:
    merged = db.deduplicate(conn)
    if not merged:
        log.info("deduplication: nothing to merge")
        return 0
    log.info("deduplication: merged %d activity/activities", len(merged))
    for m in merged:
        log.info(
            "  kept #%d (%s), superseded #%d (%s), %ds apart",
            m["keep_id"], m["keep_source"], m["supersede_id"],
            m["supersede_source"], m["start_gap_s"],
        )
    log.info("superseded rows are kept; clear superseded_by to undo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
