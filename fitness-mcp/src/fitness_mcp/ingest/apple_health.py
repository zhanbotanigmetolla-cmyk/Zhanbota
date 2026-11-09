"""Apple Health ingest — the live source, pushed from an iOS Shortcut.

Unlike every other adapter here, this one is *pushed* rather than pulled: the
phone POSTs to /ingest/health. HealthKit refuses to hand out data while the
device is locked, so arrival is irregular by design — whenever the phone is
unlocked and the Shortcut runs, not on a schedule. Everything here therefore
assumes overlapping, repeated, out-of-order deliveries.

Division of labour: the Shortcut stays as dumb as possible because Shortcuts is
a miserable place to write logic. It sends raw samples; all aggregation (summing
sleep stages into a night, mapping workout names, deriving durations) happens
here.

Idempotency
-----------
The Shortcut resends a rolling 7-day window on every run, so the same workout
arrives many times. ``source_id`` is ``{start_epoch}:{sport_type}``.

Duration is deliberately NOT part of the key. Apple revises workout durations
after a sync settles, so a resend carrying a corrected duration would create a
second row — precisely the duplication the key exists to prevent. A person
cannot begin two workouts of the same type in the same second, so start plus
type is already unique, and it is stable under revision.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from ..config import LOCAL_TZ
from ..db import DailyMetricRow, WorkoutRow

log = logging.getLogger("fitness_mcp.ingest.apple_health")

SOURCE = "apple_health"

# Apple workout names -> the sport vocabulary already in the database, so
# cycling does not appear twice under two spellings. Both English and Russian
# are accepted: the Health app is localized, and it is not knowable in advance
# which language Shortcuts will emit on a given device.
_TYPE_MAP = {
    # cycling
    "cycling": "cycling", "outdoor cycle": "cycling", "indoor cycle": "cycling",
    "велосипед": "cycling", "велозаезд": "cycling", "велотренажер": "cycling",
    "езда на велосипеде": "cycling",
    # running
    "running": "running", "outdoor run": "running", "indoor run": "running",
    "бег": "running", "бег на улице": "running", "бег в помещении": "running",
    # walking
    "walking": "walking", "outdoor walk": "walking", "indoor walk": "walking",
    "ходьба": "walking", "ходьба на улице": "walking",
    # strength
    "traditional strength training": "strength",
    "functional strength training": "strength",
    "strength training": "strength",
    "силовая тренировка": "strength",
    "традиционная силовая тренировка": "strength",
    "функциональная силовая тренировка": "strength",
    # swimming
    "swimming": "swimming", "pool swim": "swimming", "open water swim": "swimming",
    "плавание": "swimming", "плавание в бассейне": "swimming",
    "плавание на открытой воде": "swimming",
    # racquet
    "tennis": "tennis", "теннис": "tennis",
    "table tennis": "pingpong", "настольный теннис": "pingpong",
    # other named types already present or worth keeping distinct
    "equestrian sports": "horse_riding", "верховая езда": "horse_riding",
    "конный спорт": "horse_riding",
    "hiking": "hiking", "поход": "hiking", "пеший туризм": "hiking",
    "yoga": "yoga", "йога": "yoga",
    "rowing": "rowing", "гребля": "rowing",
    "elliptical": "elliptical", "эллиптический тренажер": "elliptical",
    "core training": "core", "тренировка кора": "core",
    "high intensity interval training": "hiit", "hiit": "hiit",
    "виит": "hiit", "интервальная тренировка высокой интенсивности": "hiit",
    # catch-alls Apple uses liberally
    "other": "workout", "другое": "workout", "другая тренировка": "workout",
    "mixed cardio": "workout", "смешанная кардиотренировка": "workout",
    "functional training": "workout", "функциональный тренинг": "workout",
}

# Sleep sample values that mean "in bed but not asleep". Everything else that
# Apple reports as a sleep sample is counted as asleep, which keeps unfamiliar
# or newly-added stage names from being silently dropped.
_NOT_ASLEEP = ("inbed", "in bed", "в постели", "awake", "бодрствование", "пробуждение")

_STAGES = (
    (("deep", "глубок"), "deep"),
    (("rem", "быстр"), "rem"),
    (("core", "light", "основн", "легк"), "light"),
)


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, and fold ё to е for Russian matching."""
    return re.sub(r"\s+", " ", (text or "").strip().lower()).replace("ё", "е")


def parse_timestamp(value: Any) -> datetime:
    """Parse the several shapes an iOS Shortcut might produce.

    Always returns an aware datetime **in UTC**. Shortcuts' date formatting is
    inconsistent across locales and iOS versions, so epochs and a range of
    ISO-ish strings are all accepted rather than demanding one exact format the
    user would have to get right on a phone keyboard. A string carrying no
    offset is read as Almaty local time, which is what a phone here emits.
    """
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), timezone.utc)

    text = str(value or "").strip()
    if not text:
        raise ValueError("empty timestamp")

    # Bare epoch as a string
    if re.fullmatch(r"-?\d{9,13}(\.\d+)?", text):
        n = float(text)
        if n > 1e11:          # milliseconds
            n /= 1000.0
        return datetime.fromtimestamp(n, timezone.utc)

    cleaned = text.replace("Z", "+00:00").replace("z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
        dt = dt if dt.tzinfo else dt.replace(tzinfo=LOCAL_TZ)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M:%S",
                "%d.%m.%Y, %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d %b %Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
        except ValueError:
            continue

    raise ValueError(f"unrecognized timestamp {text!r}")


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        # Shortcuts can emit "5,23" in locales that use a decimal comma.
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _local_date(dt: datetime) -> str:
    return dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ApplePayload:
    """Parsed and normalized contents of one POST to /ingest/health."""

    def __init__(self, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        self.payload = payload
        self.warnings: list[str] = []

    # ── workouts ────────────────────────────────────────────────────────────

    def workouts(self) -> Iterable[WorkoutRow]:
        seen: set[str] = set()
        for item in self.payload.get("workouts") or []:
            row = self._workout(item, seen)
            if row is not None:
                yield row

    def _workout(self, item: dict, seen: set[str]) -> WorkoutRow | None:
        if not isinstance(item, dict):
            self.warnings.append("workout entry was not an object; skipped")
            return None

        raw_type = item.get("type") or item.get("workoutType") or ""
        sport_type = _TYPE_MAP.get(_normalize(raw_type))
        if sport_type is None:
            sport_type = _normalize(raw_type).replace(" ", "_") or "workout"
            self.warnings.append(
                f"unmapped Apple workout type {raw_type!r}; stored as {sport_type!r}"
            )

        try:
            start = parse_timestamp(item.get("start") or item.get("startDate"))
        except ValueError as exc:
            self.warnings.append(f"workout skipped: {exc}")
            return None

        end = None
        if item.get("end") or item.get("endDate"):
            try:
                end = parse_timestamp(item.get("end") or item.get("endDate"))
            except ValueError as exc:
                self.warnings.append(f"workout at {_local_date(start)}: bad end time ({exc})")

        duration = _num(item.get("duration_s") or item.get("duration"))
        if duration is None and end is not None:
            duration = (end - start).total_seconds()
        if duration is not None and duration < 0:
            self.warnings.append(f"workout at {_local_date(start)}: negative duration ignored")
            duration = None

        start = start.replace(microsecond=0)
        source_id = f"{int(start.timestamp())}:{sport_type}"
        if source_id in seen:
            self.warnings.append(
                f"two {sport_type} workouts share start {_utc(start)}; kept the first"
            )
            return None
        seen.add(source_id)

        return WorkoutRow(
            source=SOURCE,
            source_id=source_id,
            started_at=_utc(start),
            local_date=_local_date(start),
            sport_type=sport_type,
            duration_s=int(duration) if duration else None,
            distance_m=_num(item.get("distance_m") or item.get("distance")),
            avg_hr=int(_num(item.get("avg_hr")) or 0) or None,
            max_hr=int(_num(item.get("max_hr")) or 0) or None,
            kcal=int(_num(item.get("kcal") or item.get("calories")) or 0) or None,
            elevation_m=_num(item.get("elevation_m")),
            raw=item,
            time_precision="exact",
            sets=(),
        )

    # ── daily metrics ───────────────────────────────────────────────────────

    def daily_metrics(self) -> Iterable[DailyMetricRow]:
        sleep = self._sleep_by_day()
        resting = self._by_day("resting_hr", ("bpm", "value"))
        steps = self._by_day("steps", ("steps", "value"))

        for day in sorted(set(sleep) | set(resting) | set(steps)):
            s = sleep.get(day)
            yield DailyMetricRow(
                source=SOURCE,
                local_date=day,
                resting_hr=int(resting[day]) if day in resting else None,
                sleep_minutes=round(s["minutes"]) if s else None,
                sleep_stages={k: round(v) for k, v in s["stages"].items()} if s else None,
                steps=int(steps[day]) if day in steps else None,
                stress=None,          # Apple has no stress equivalent
                raw={"sleep_samples": s["samples"]} if s else None,
            )

    def _sleep_by_day(self) -> dict[str, dict]:
        """Sum asleep intervals into nights, attributed to the wake-up day."""
        days: dict[str, dict] = {}
        for item in self.payload.get("sleep_samples") or []:
            if not isinstance(item, dict):
                continue
            value = _normalize(item.get("value") or item.get("category") or "")
            try:
                start = parse_timestamp(item.get("start") or item.get("startDate"))
                end = parse_timestamp(item.get("end") or item.get("endDate"))
            except ValueError as exc:
                self.warnings.append(f"sleep sample skipped: {exc}")
                continue

            minutes = (end - start).total_seconds() / 60.0
            if minutes <= 0 or minutes > 24 * 60:
                self.warnings.append(f"sleep sample with implausible length ({minutes:.0f} min); skipped")
                continue
            # "In bed" and "awake" are time in bed, not sleep. Counting them
            # would inflate every night by the time spent falling asleep.
            if any(tok in value for tok in _NOT_ASLEEP):
                continue

            stage = "unspecified"
            for needles, name in _STAGES:
                if any(n in value for n in needles):
                    stage = name
                    break

            # Attributed to the day the sample ENDS, which is the day you woke.
            day = _local_date(end)
            acc = days.setdefault(day, {"minutes": 0.0, "stages": {}, "samples": 0})
            acc["minutes"] += minutes
            acc["stages"][stage] = acc["stages"].get(stage, 0.0) + minutes
            acc["samples"] += 1
        return days

    def _by_day(self, key: str, value_keys: tuple[str, ...]) -> dict[str, float]:
        out: dict[str, float] = {}
        for item in self.payload.get(key) or []:
            if not isinstance(item, dict):
                continue
            raw_when = item.get("date") or item.get("start") or item.get("startDate")
            try:
                when = parse_timestamp(raw_when)
            except ValueError:
                # A bare 'YYYY-MM-DD' is a date, not a timestamp.
                text = str(raw_when or "").strip()
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                    out_day = text
                    value = next((_num(item.get(k)) for k in value_keys
                                  if _num(item.get(k)) is not None), None)
                    if value is not None:
                        out[out_day] = value
                    continue
                self.warnings.append(f"{key} entry has an unreadable date {raw_when!r}; skipped")
                continue

            value = next((_num(item.get(k)) for k in value_keys
                          if _num(item.get(k)) is not None), None)
            if value is None:
                self.warnings.append(f"{key} entry at {_local_date(when)} had no value; skipped")
                continue
            out[_local_date(when)] = value
        return out
