"""Adapter protocol and the ingest runner.

The point of this layer is that a broken upstream never costs history. Adapters
only *produce* normalized rows; they never touch the database themselves. The
runner owns the transaction, so an adapter that raises halfway through leaves
the database exactly as it was.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Iterable, Protocol, runtime_checkable

from ..db import WorkoutRow, upsert_workout

log = logging.getLogger("fitness_mcp.ingest")


@runtime_checkable
class Adapter(Protocol):
    """A source of workout data.

    ``name`` becomes the ``source`` column and is the first half of the
    ``(source, source_id)`` uniqueness key, so it must be stable across
    releases — renaming it orphans every row the adapter previously wrote.
    """

    name: str

    def fetch(self) -> Iterable[WorkoutRow]:
        """Yield normalized workouts. May raise; the runner handles it."""
        ...


@dataclass
class IngestResult:
    source: str
    created: int = 0
    updated: int = 0
    failed: bool = False
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.updated


def run_adapter(conn: sqlite3.Connection, adapter: Adapter) -> IngestResult:
    """Run one adapter inside a single transaction. Never raises.

    Either every row from this adapter lands, or none of it does. A failure is
    reported in the result rather than propagating, so one fragile source can
    never take down the server or corrupt data from a healthy one.
    """
    result = IngestResult(source=adapter.name)
    try:
        rows = list(adapter.fetch())
    except Exception as exc:  # noqa: BLE001 - fail soft is the whole point
        log.exception("adapter %s failed during fetch", adapter.name)
        result.failed = True
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    try:
        with conn:  # commits on success, rolls back on exception
            for row in rows:
                _, created = upsert_workout(conn, row)
                if created:
                    result.created += 1
                else:
                    result.updated += 1
    except Exception as exc:  # noqa: BLE001
        log.exception("adapter %s failed during write", adapter.name)
        result.failed = True
        result.error = f"{type(exc).__name__}: {exc}"
        result.created = result.updated = 0

    warnings = getattr(adapter, "warnings", None)
    if warnings:
        result.warnings = list(warnings)
    return result
