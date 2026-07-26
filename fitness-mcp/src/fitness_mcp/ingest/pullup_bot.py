"""Phase 1 adapter: the pullup_bot SQLite database.

The bot is production and is used daily, so this adapter opens its database
strictly read-only (``file:...?mode=ro``) and never writes to it.

Shape mismatch worth understanding
----------------------------------
The bot stores one row per ``(user_id, date, exercise)`` with the sets for that
exercise as a JSON list of rep counts. fitness-mcp stores one row per *session*
with a ``sets`` child table carrying the exercise per set. So this adapter
collapses all of a day's exercise rows into a single workout, which is also
what makes "did I train that day" answerable.

The bot records no clock time, only a date. ``started_at`` is therefore
synthesized as local midnight of the training day converted to UTC — it marks
the day, not a real session start, and round-trips back to the correct
``local_date``. Do not read precision into it.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, time, timezone
from typing import Iterable

from ..config import LOCAL_TZ
from ..db import SetRow, WorkoutRow

log = logging.getLogger("fitness_mcp.ingest.pullup_bot")

# Rows tagged with this exercise are rest-day markers, not training sessions.
REST_EXERCISE = "rest"

SPORT_TYPE = "strength"


class PullupBotAdapter:
    """Reads one owner's training history out of the bot database."""

    name = "pullup_bot"

    def __init__(self, bot_db_path: str, owner_tg_id: int):
        self.bot_db_path = bot_db_path
        self.owner_tg_id = owner_tg_id
        self.warnings: list[str] = []

    def _connect(self) -> sqlite3.Connection:
        # Read-only URI mode. If the bot DB is missing this raises immediately
        # rather than creating an empty file, which is the behaviour we want.
        conn = sqlite3.connect(f"file:{self.bot_db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch(self) -> Iterable[WorkoutRow]:
        conn = self._connect()
        try:
            owner = conn.execute(
                "SELECT id, tg_id, username FROM users WHERE tg_id = ?", (self.owner_tg_id,)
            ).fetchone()
            if owner is None:
                raise LookupError(
                    f"No user with tg_id={self.owner_tg_id} in the bot database. "
                    "Set FITNESS_MCP_OWNER_TG_ID to your own Telegram id."
                )

            rows = conn.execute(
                """SELECT date, exercise, planned, completed, sets_json, rpe, day_type, notes
                   FROM workouts
                   WHERE user_id = ? AND exercise != ?
                   ORDER BY date, exercise""",
                (owner["id"], REST_EXERCISE),
            ).fetchall()
        finally:
            conn.close()

        by_date: dict[str, list[sqlite3.Row]] = {}
        for r in rows:
            by_date.setdefault(r["date"], []).append(r)

        for local_date, day_rows in sorted(by_date.items()):
            workout = self._build_workout(owner["tg_id"], local_date, day_rows)
            if workout is not None:
                yield workout

    def _build_workout(self, tg_id: int, local_date: str, day_rows) -> WorkoutRow | None:
        sets: list[SetRow] = []
        raw: list[dict] = []

        for r in day_rows:
            raw.append({k: r[k] for k in r.keys()})
            # The bot writes 0 when RPE was never entered; 0 is not a valid RPE.
            rpe = float(r["rpe"]) if r["rpe"] else None
            reps = self._parse_sets(r, local_date)

            if reps is None:
                # No per-set breakdown. Keep the session total as a single
                # inferred set so volume stays right, flagged so it can never
                # masquerade as a best single set.
                if r["completed"] and r["completed"] > 0:
                    sets.append(SetRow(
                        exercise=r["exercise"], reps=int(r["completed"]),
                        rpe=rpe, set_index=0, inferred=True,
                    ))
                # completed == 0 with no sets means planned but not performed.
                continue

            total = sum(reps)
            if r["completed"] and total != r["completed"]:
                self.warnings.append(
                    f"{local_date} {r['exercise']}: sets sum to {total} but "
                    f"completed={r['completed']}; using the per-set breakdown"
                )
            for i, rep in enumerate(reps):
                sets.append(SetRow(exercise=r["exercise"], reps=int(rep), rpe=rpe, set_index=i))

        if not sets:
            return None

        started_at = (
            datetime.combine(datetime.strptime(local_date, "%Y-%m-%d").date(), time(0, 0),
                             tzinfo=LOCAL_TZ)
            .astimezone(timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        )

        return WorkoutRow(
            source=self.name,
            source_id=f"{tg_id}:{local_date}",
            started_at=started_at,
            local_date=local_date,
            sport_type=SPORT_TYPE,
            # The bot tracks no duration, distance, heart rate, calories or
            # elevation. Leaving these NULL is honest; zero would not be.
            raw={"rows": raw, "day_type": day_rows[0]["day_type"]},
            sets=sets,
            # started_at marks the day, not a real session start, so these rows
            # must never take part in start-time-based cross-source dedup.
            time_precision="date_only",
        )

    def _parse_sets(self, row, local_date: str) -> list[int] | None:
        """Return the rep list, or None when there is no usable breakdown."""
        blob = row["sets_json"]
        if not blob or blob == "[]":
            return None
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError as exc:
            self.warnings.append(
                f"{local_date} {row['exercise']}: unparseable sets_json ({exc}); "
                "falling back to the session total"
            )
            return None
        if not isinstance(parsed, list) or not parsed:
            return None
        if not all(isinstance(v, int) and v >= 0 for v in parsed):
            self.warnings.append(
                f"{local_date} {row['exercise']}: unexpected sets_json contents "
                f"{parsed!r}; falling back to the session total"
            )
            return None
        return parsed
