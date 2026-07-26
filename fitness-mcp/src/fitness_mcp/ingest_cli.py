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

log = logging.getLogger("fitness_mcp.ingest_cli")

ADAPTERS = {"pullup_bot"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import workout data into fitness-mcp.")
    parser.add_argument(
        "--source", default="pullup_bot", choices=sorted(ADAPTERS),
        help="Which adapter to run (default: pullup_bot).",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print every data-quality warning.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.source == "pullup_bot":
        adapter = PullupBotAdapter(
            bot_db_path=str(config.PULLUP_BOT_DB), owner_tg_id=config.owner_tg_id()
        )
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
        "ingest from %s: %d created, %d updated (%d total)",
        result.source, result.created, result.updated, result.total,
    )
    if result.warnings:
        log.warning("%d data-quality warning(s) from the source", len(result.warnings))
        shown = result.warnings if args.verbose else result.warnings[:5]
        for w in shown:
            log.warning("  %s", w)
        if not args.verbose and len(result.warnings) > len(shown):
            log.warning("  ... %d more (use --verbose)", len(result.warnings) - len(shown))
    return 0


if __name__ == "__main__":
    sys.exit(main())
