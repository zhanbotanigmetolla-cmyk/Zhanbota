"""Strava bulk export adapter — parses the GDPR archive, no API involved.

Requested from *Settings → My Account → Download or Delete Your Account*. The
archive is a zip containing ``activities.csv`` plus per-activity GPX/TCX/FIT
files. This reads only ``activities.csv``, and reads it straight out of the zip
without extracting: the archive also contains ``logins.csv``, ``contacts.csv``,
``mobile_device_identifiers.csv`` and similar, none of which belong anywhere
near this database.

Written against a real archive, which turned out to matter more than usual:

* **The export is localized.** The account's Strava language decides the column
  headers, so a parser hard-coded to ``Activity ID`` silently imports zero rows
  from a Russian export. Columns are resolved through an alias table and a
  missing required column is a loud error, never an empty import.
* **Dates are localized too** — ``26 июл. 2026 г., 12:12:51``, with a narrow
  no-break space (U+202F) before ``г.``. Month names are matched by prefix.
* **Two distance columns exist.** ``Расстояние`` is kilometres with a *comma*
  decimal separator; ``Дистанция`` is metres with a dot. Only the metres column
  is used.
* **Two duration columns exist**: elapsed and moving. ``duration_s`` is elapsed
  time; moving time is preserved in ``raw_json``.
* **Timestamps are UTC**, despite the localized formatting. Confirmed against
  the data: an activity Strava auto-named *Ночной заезд* ("night ride") is
  18:33 in the file, which is 23:33 in Asia/Almaty — night locally, evening if
  the value were already local.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import zipfile
from datetime import datetime, timezone
from typing import Iterable

from ..config import LOCAL_TZ
from ..db import WorkoutRow

log = logging.getLogger("fitness_mcp.ingest.strava_export")

ACTIVITIES_CSV = "activities.csv"

# Column aliases, by role. First match wins. Add a language by extending a list.
_COLUMNS: dict[str, list[str]] = {
    "activity_id": ["ID физической активности", "ID тренировки", "Activity ID"],
    "started_at":  ["Дата тренировки", "Activity Date"],
    "name":        ["Название тренировки", "Activity Name"],
    "sport_type":  ["Тип активности", "Тип тренировки", "Activity Type"],
    # metres, dot decimal — NOT 'Расстояние', which is km with a comma
    "distance_m":  ["Дистанция", "Distance"],
    "duration_s":  ["Общее время", "Elapsed Time"],
    "moving_s":    ["Время в движении", "Moving Time"],
    "avg_hr":      ["Средний пульс", "Average Heart Rate"],
    "max_hr":      ["Макс. пульс", "Max Heart Rate"],
    "kcal":        ["Калории", "Calories"],
    "elevation_m": ["Набор высоты", "Elevation Gain"],
}

_REQUIRED = ("activity_id", "started_at", "sport_type")

# Strava's own sport names, normalized to stable English identifiers so tool
# callers can filter without knowing the export's language.
_SPORT_TYPES = {
    "бег": "running",
    "ходьба": "walking",
    "велосипед": "cycling",
    "плавание": "swimming",
    "силовая тренировка": "strength",
    "тренировка": "workout",
    "поход": "hiking",
    "run": "running",
    "walk": "walking",
    "ride": "cycling",
    "swim": "swimming",
    "weight training": "strength",
    "workout": "workout",
    "hike": "hiking",
}

_RU_MONTHS = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "мая": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}

# '26 июл. 2026 г., 12:12:51'  (whitespace already normalized)
_RU_DATE = re.compile(
    r"(\d{1,2})\s+([^\s.]+)\.?\s+(\d{4})\s*(?:г\.?)?,?\s+(\d{1,2}):(\d{2}):(\d{2})"
)

_EN_FORMATS = (
    "%b %d, %Y, %I:%M:%S %p",
    "%d %b %Y, %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
)


def _normalize_spaces(value: str) -> str:
    """Collapse NBSP/narrow-NBSP, which localized exports use liberally."""
    return re.sub(r"[\s  ]+", " ", value).strip()


def parse_started_at(value: str) -> datetime:
    """Parse a localized Strava timestamp into an aware UTC datetime."""
    text = _normalize_spaces(value)

    m = _RU_DATE.match(text)
    if m:
        day, month_word, year, hh, mm, ss = m.groups()
        key = month_word.lower()[:3]
        if key not in _RU_MONTHS:
            raise ValueError(f"unrecognized month {month_word!r} in date {value!r}")
        return datetime(int(year), _RU_MONTHS[key], int(day),
                        int(hh), int(mm), int(ss), tzinfo=timezone.utc)

    for fmt in _EN_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    raise ValueError(
        f"could not parse activity date {value!r}. The export is localized; add "
        "the format to _EN_FORMATS or the month names to _RU_MONTHS."
    )


def _number(value: str | None) -> float | None:
    """Parse a numeric cell, tolerating comma decimals and blanks."""
    if value is None:
        return None
    text = _normalize_spaces(value).replace("−", "-")
    if not text or text.lower() in {"na", "n/a", "-"}:
        return None
    # Only treat a comma as a decimal point; thousands separators do not appear
    # in this export and guessing between the two would corrupt values.
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    n = _number(value)
    return int(round(n)) if n is not None else None


class StravaExportAdapter:
    """Reads activities.csv out of a Strava bulk-export zip."""

    name = "strava_export"

    def __init__(self, archive_path: str):
        self.archive_path = archive_path
        self.warnings: list[str] = []

    def _resolve_columns(self, header: list[str]) -> dict[str, str]:
        present = {h.strip(): h for h in header}
        resolved: dict[str, str] = {}
        for role, aliases in _COLUMNS.items():
            for alias in aliases:
                if alias in present:
                    resolved[role] = present[alias]
                    break

        missing = [r for r in _REQUIRED if r not in resolved]
        if missing:
            raise KeyError(
                f"activities.csv is missing required column(s) {missing}. Found headers: "
                f"{header[:8]}... The export is localized — add this language's names to "
                "_COLUMNS in strava_export.py rather than letting the import silently "
                "produce nothing."
            )
        for role in _COLUMNS:
            if role not in resolved:
                self.warnings.append(f"column for {role!r} not present; leaving it null")
        return resolved

    def fetch(self) -> Iterable[WorkoutRow]:
        with zipfile.ZipFile(self.archive_path) as z:
            try:
                raw = z.read(ACTIVITIES_CSV)
            except KeyError:
                raise KeyError(
                    f"{ACTIVITIES_CSV} not found in {self.archive_path}. Is this a Strava "
                    "bulk export archive?"
                ) from None

        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not reader.fieldnames:
            raise ValueError("activities.csv has no header row")
        cols = self._resolve_columns(list(reader.fieldnames))

        seen: set[str] = set()
        for row in reader:
            workout = self._build(row, cols, seen)
            if workout is not None:
                yield workout

    def _build(self, row: dict, cols: dict[str, str], seen: set[str]) -> WorkoutRow | None:
        activity_id = (row.get(cols["activity_id"]) or "").strip()
        if not activity_id:
            self.warnings.append("row without an activity id; skipped")
            return None
        if activity_id in seen:
            self.warnings.append(f"activity {activity_id} appears twice in the CSV; kept the first")
            return None
        seen.add(activity_id)

        raw_date = row.get(cols["started_at"]) or ""
        try:
            started = parse_started_at(raw_date)
        except ValueError as exc:
            self.warnings.append(f"activity {activity_id}: {exc}")
            return None

        sport_raw = _normalize_spaces(row.get(cols["sport_type"]) or "")
        sport_type = _SPORT_TYPES.get(sport_raw.lower())
        if sport_type is None:
            sport_type = sport_raw.lower().replace(" ", "_") or None
            self.warnings.append(
                f"unmapped sport type {sport_raw!r}; stored as {sport_type!r}"
            )

        def cell(role: str) -> str | None:
            col = cols.get(role)
            return row.get(col) if col else None

        # Preserve every non-empty field so a better parser can be re-run later.
        raw_payload = {k: v for k, v in row.items() if (v or "").strip()}

        return WorkoutRow(
            source=self.name,
            source_id=activity_id,
            started_at=started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            local_date=started.astimezone(LOCAL_TZ).strftime("%Y-%m-%d"),
            sport_type=sport_type,
            duration_s=_int(cell("duration_s")),
            distance_m=_number(cell("distance_m")),
            avg_hr=_int(cell("avg_hr")),
            max_hr=_int(cell("max_hr")),
            kcal=_int(cell("kcal")),
            elevation_m=_number(cell("elevation_m")),
            raw=raw_payload,
            # Strava records a real clock time, so these rows are eligible for
            # cross-source dedup against the Xiaomi export.
            time_precision="exact",
            # The bulk export has no set-level data; strength sessions arrive
            # without sets rather than with invented ones.
            sets=(),
        )
