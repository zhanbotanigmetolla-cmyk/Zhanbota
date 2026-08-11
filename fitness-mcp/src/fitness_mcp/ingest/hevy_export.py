"""Hevy CSV export adapter — weighted gym training.

Hevy exports one row per *set*, with the workout-level fields (title, start,
end, description) repeated on every row of that workout. So the first job here
is to put the sessions back together: rows are grouped by
``(title, start_time, end_time)`` and each group becomes one ``workouts`` row
with its sets attached, rather than 2,400 one-set "sessions".

How this differs from the data already in the database
------------------------------------------------------
This is a second training modality, not a replacement. The pullup bot records
unweighted bodyweight work, where ``weight_kg`` is empty *by design*. Hevy
records barbell/dumbbell/machine work, where it is populated throughout. Both
live side by side under their own ``source`` value, and every read function
takes a ``source`` filter so either can be reported on alone.

Exercise names are kept verbatim from Hevy (mostly Russian, e.g.
``подтягивания (с утяжелителем)``), only case-folded. They are deliberately
*not* mapped onto the bot's names: weighted pull-ups and bodyweight pull-ups
are different lifts and merging them would corrupt both rep records and 1RMs.

Things the format forces on us
------------------------------
* Dates are rendered in the exporting phone's locale — ``26 апр. 2026, 19:20``.
  A plain English-locale parser cannot read them, so month names are mapped
  explicitly. Both the abbreviated (``июн.``) and genitive (``июня``) forms
  appear in the same file.
* Times carry no zone. They are wall-clock local times, so they are read in
  ``LOCAL_TZ`` — which correctly applies Almaty's UTC+6 → UTC+5 change in 2024
  to the older sessions.
* ``set_index`` restarts at 0 when an exercise is performed twice in one
  session (treadmill as a warmup and again at the end is the common case), so
  the file's own index is not unique within a workout. Sets are renumbered per
  ``(workout, exercise)`` in file order instead.
* ``distance_km`` is kilometres; the schema stores metres.
* There is no heart-rate data anywhere in this export.
"""

from __future__ import annotations

import csv
import logging
import re
from datetime import datetime, timezone
from typing import Iterable, Iterator

from ..config import LOCAL_TZ
from ..db import SetRow, WorkoutRow

log = logging.getLogger("fitness_mcp.ingest.hevy_export")

# Every session in this export is gym strength work. Cardio machines appear as
# exercises *within* a session (a treadmill warm-up), never as the session.
SPORT_TYPE = "strength"

# Russian month names as Hevy renders them. Both the abbreviated form with a
# trailing dot and the genitive full form occur, sometimes in the same file.
_MONTHS = {
    "янв": 1, "января": 1,
    "февр": 2, "фев": 2, "февраля": 2,
    "мар": 3, "марта": 3,
    "апр": 4, "апреля": 4,
    "май": 5, "мая": 5,
    "июн": 6, "июня": 6,
    "июл": 7, "июля": 7,
    "авг": 8, "августа": 8,
    "сент": 9, "сен": 9, "сентября": 9,
    "окт": 10, "октября": 10,
    "нояб": 11, "ноя": 11, "ноября": 11,
    "дек": 12, "декабря": 12,
}

_DATE_RE = re.compile(r"^\s*(\d{1,2})\s+([^\s,]+?)\.?\s+(\d{4}),?\s+(\d{1,2}):(\d{2})\s*$")


class HevyDateError(ValueError):
    """A timestamp in the export could not be parsed."""


def parse_hevy_datetime(text: str) -> datetime:
    """``'26 апр. 2026, 19:20'`` -> an aware datetime in ``LOCAL_TZ``.

    Falls back to ISO-8601 first, so a future Hevy release that switches to a
    machine-readable format keeps working without a code change here.
    """
    text = (text or "").strip()
    if not text:
        raise HevyDateError("empty timestamp")

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    else:
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=LOCAL_TZ)

    m = _DATE_RE.match(text)
    if not m:
        raise HevyDateError(f"unrecognised timestamp {text!r}")
    day, month_name, year, hour, minute = m.groups()
    month = _MONTHS.get(month_name.lower().rstrip("."))
    if month is None:
        raise HevyDateError(f"unknown month {month_name!r} in {text!r}")
    return datetime(int(year), month, int(day), int(hour), int(minute), tzinfo=LOCAL_TZ)


def _num(value: str | None) -> float | None:
    """Parse a numeric cell. Empty means "not recorded", which is not zero."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    n = _num(value)
    return int(n) if n is not None else None


class HevyExportAdapter:
    """Workouts and sets from a Hevy CSV export.

    Re-importing a newer export that overlaps earlier dates is safe: a session
    keys on its UTC start time, and ``upsert_workout`` replaces that session's
    sets wholesale rather than appending, so volume is never double-counted and
    a set deleted upstream does not linger.
    """

    name = "hevy_export"

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.warnings: list[str] = []

    def _rows(self) -> Iterator[dict]:
        with open(self.csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            required = {"title", "start_time", "end_time", "exercise_title", "set_index"}
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise ValueError(
                    f"{self.csv_path} is missing column(s) {sorted(missing)}; "
                    "is this a Hevy CSV export?"
                )
            yield from reader

    def fetch(self) -> Iterable[WorkoutRow]:
        # Grouping key is the whole session identity, not just the start time:
        # it is what the file itself repeats on every row of a workout. Order is
        # preserved so set renumbering follows the order they were performed in.
        groups: dict[tuple[str, str, str], list[dict]] = {}
        for row in self._rows():
            key = (row.get("title") or "", row.get("start_time") or "",
                   row.get("end_time") or "")
            groups.setdefault(key, []).append(row)

        seen_ids: set[str] = set()
        for (title, start_text, end_text), rows in groups.items():
            try:
                start = parse_hevy_datetime(start_text)
            except HevyDateError as exc:
                self.warnings.append(f"workout {title!r}: {exc}; skipped")
                continue

            started_at = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            # The natural key is the start instant. Two different titles at the
            # same instant would be one session recorded twice; keep the first
            # and say so rather than letting the second silently overwrite it.
            if started_at in seen_ids:
                self.warnings.append(
                    f"{start:%Y-%m-%d %H:%M} {title!r}: another session already starts at this "
                    "time; kept the first"
                )
                continue
            seen_ids.add(started_at)

            duration_s = None
            try:
                end = parse_hevy_datetime(end_text)
            except HevyDateError as exc:
                self.warnings.append(f"{start:%Y-%m-%d} {title!r}: end time — {exc}")
            else:
                seconds = int((end - start).total_seconds())
                if seconds <= 0:
                    self.warnings.append(
                        f"{start:%Y-%m-%d} {title!r}: end is not after start; duration dropped"
                    )
                else:
                    # Elapsed wall-clock, including rest between sets. Hevy has
                    # no notion of "active" time the way the watch export does.
                    duration_s = seconds

            sets, distance_km = self._build_sets(rows, start, title)

            yield WorkoutRow(
                source=self.name,
                source_id=started_at,
                started_at=started_at,
                local_date=start.astimezone(LOCAL_TZ).strftime("%Y-%m-%d"),
                sport_type=SPORT_TYPE,
                duration_s=duration_s,
                # km -> m. Only cardio machines inside the session carry this.
                distance_m=distance_km * 1000 if distance_km else None,
                # No heart rate anywhere in a Hevy export, and no calories.
                avg_hr=None, max_hr=None, kcal=None, elevation_m=None,
                time_precision="exact",
                raw={
                    "title": title,
                    "description": (rows[0].get("description") or "").strip() or None,
                    # Per-set distance and duration have nowhere to live in the
                    # schema, so the original rows are kept verbatim and stay
                    # recoverable without another export.
                    "rows": rows,
                },
                sets=sets,
            )

    def _build_sets(
        self, rows: list[dict], start: datetime, title: str
    ) -> tuple[list[SetRow], float]:
        """Normalized sets for one session, plus its total cardio distance."""
        sets: list[SetRow] = []
        # Hevy restarts set_index per *occurrence* of an exercise, so the same
        # (exercise, set_index) recurs when a movement is done twice in a
        # session. A running counter per exercise restores uniqueness.
        next_index: dict[str, int] = {}
        distance_km = 0.0

        for row in rows:
            exercise = (row.get("exercise_title") or "").strip()
            if not exercise:
                self.warnings.append(f"{start:%Y-%m-%d} {title!r}: set with no exercise; skipped")
                continue
            # Lower-cased to match the storage convention the other adapters
            # use; otherwise "Присед (Штанга)" and "присед (штанга)" would be
            # two different lifts to exercise_history's exact match.
            exercise = exercise.lower()

            distance_km += _num(row.get("distance_km")) or 0.0

            index = next_index.get(exercise, 0)
            next_index[exercise] = index + 1
            sets.append(SetRow(
                exercise=exercise,
                reps=_int(row.get("reps")),
                # Empty means bodyweight/unloaded, which is an absent load
                # rather than a zero one — same convention as the bot's data.
                weight_kg=_num(row.get("weight_kg")),
                rpe=_num(row.get("rpe")),
                set_index=index,
                # These are individually logged sets, never reconstructed from
                # a session total, so none of them is inferred.
                inferred=False,
                # 'warmup' sets are excluded from personal records: a light
                # ramp-up set is not an attempt at a best effort.
                set_type=(row.get("set_type") or "").strip().lower() or None,
            ))

        return sets, distance_km
