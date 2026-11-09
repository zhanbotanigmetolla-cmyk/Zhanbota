"""Mi Fitness / Xiaomi official export adapter.

Requested from account.xiaomi.com -> Privacy -> Manage. Produces a directory of
CSVs, all prefixed with a per-request stamp (``20260726_1889373230_MiFitness_``),
so files are located by suffix rather than by full name.

Three files matter:

``hlth_center_sport_record.csv``
    One row per workout. ``Value`` is JSON. The human-readable sport name is in
    the CSV's own ``Key``/``Category`` columns, NOT in the JSON — the JSON's
    ``sport_type`` is an opaque integer.

``hlth_center_fitness_data.csv`` (~133 MB)
    Per-reading metrics, one row each, discriminated by ``Key``. Streamed, never
    loaded whole. Only ``sleep``, ``resting_heart_rate`` and ``stress`` are read;
    ``heart_rate`` alone is half a million rows and is deliberately skipped.

``hlth_center_aggregated_fitness_data.csv``
    Daily rollups. Only ``Tag='daily_report'`` carries values — ``daily_mark``
    rows are just ``{"has_data": true}`` and are ignored.

Things learned from the real archive
------------------------------------
* ``duration`` is **active** time, not elapsed: it disagrees with
  ``end_time - start_time`` on 47 of 238 records. Strava reports elapsed time,
  so cross-source duration comparisons need a loose tolerance.
* ``start_time`` in the JSON disagrees with the CSV ``Time`` column on 6 of 238
  records. The JSON is treated as authoritative and the disagreement is warned about.
* ``timezone`` is in 15-minute units — ``20`` means UTC+5, which matches Almaty.
* Sleep durations are **minutes**, and ``duration`` equals deep+light+rem.
"""

from __future__ import annotations

import collections
import csv
import glob
import json
import logging
import os
from datetime import datetime, timezone
from typing import Iterable, Iterator

from ..config import LOCAL_TZ
from ..db import DailyMetricRow, WorkoutRow

log = logging.getLogger("fitness_mcp.ingest.xiaomi_export")

# Sleep JSON and sport payloads are large; the default 128 KB field cap trips.
csv.field_size_limit(10_000_000)

SPORT_RECORD = "hlth_center_sport_record.csv"
FITNESS_DATA = "hlth_center_fitness_data.csv"
AGGREGATED = "hlth_center_aggregated_fitness_data.csv"

# Xiaomi sport names -> the same canonical vocabulary the Strava adapter emits,
# so a sport_type filter behaves identically across sources. Granularity is kept
# where it carries real meaning: high_bar is pull-up bar work, not generic
# strength training, and collapsing it would lose that.
SPORT_TYPES = {
    "strength_training": "strength",
    "high_bar": "high_bar",
    "outdoor_running": "running",
    "indoor_running": "running",
    "outdoor_riding": "cycling",
    "indoor_riding": "cycling",
    "outdoor_walking": "walking",
    "open_swimming": "swimming",
    "pool_swimming": "swimming",
    "free_training": "workout",
    "pingpong": "pingpong",
    "tennis": "tennis",
    "horse_riding": "horse_riding",
}


def _find(directory: str, suffix: str) -> str:
    matches = sorted(glob.glob(os.path.join(directory, f"*{suffix}")))
    if not matches:
        raise FileNotFoundError(
            f"{suffix} not found in {directory}. Is this a Mi Fitness export directory?"
        )
    return matches[0]


def _rows(path: str) -> Iterator[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def _local_date(epoch: int | float) -> str:
    return datetime.fromtimestamp(int(epoch), timezone.utc).astimezone(LOCAL_TZ).strftime("%Y-%m-%d")


def _utc(epoch: int | float) -> str:
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(value):
    """Return a number, or None for absent/zero-as-missing sentinels."""
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n


class XiaomiExportAdapter:
    """Workouts and daily wellness metrics from the official Xiaomi export."""

    name = "xiaomi_export"

    def __init__(self, export_dir: str):
        self.export_dir = export_dir
        self.warnings: list[str] = []

    # ── workouts ────────────────────────────────────────────────────────────

    def fetch(self) -> Iterable[WorkoutRow]:
        path = _find(self.export_dir, SPORT_RECORD)
        seen: set[str] = set()

        for row in _rows(path):
            raw_value = row.get("Value") or ""
            try:
                v = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                self.warnings.append(f"sport_record at Time={row.get('Time')}: bad JSON ({exc})")
                continue
            if not isinstance(v, dict):
                continue

            start = v.get("start_time") or row.get("Time")
            if not start:
                self.warnings.append("sport_record row without a start time; skipped")
                continue
            start = int(start)

            # The JSON and the CSV disagree on 6 of 238 records in the reference
            # archive. The JSON is the richer record, so it wins — but say so.
            csv_time = int(row.get("Time") or 0)
            if csv_time and csv_time != start:
                self.warnings.append(
                    f"{_local_date(start)}: JSON start_time {start} != CSV Time {csv_time}; "
                    "using the JSON value"
                )

            source_id = str(start)
            if source_id in seen:
                self.warnings.append(f"duplicate workout at {_local_date(start)}; kept the first")
                continue
            seen.add(source_id)

            key = (row.get("Key") or "").strip()
            sport_type = SPORT_TYPES.get(key)
            if sport_type is None:
                sport_type = key.lower() or None
                self.warnings.append(f"unmapped sport type {key!r}; stored as {sport_type!r}")

            duration = _num(v.get("duration"))
            yield WorkoutRow(
                source=self.name,
                source_id=source_id,
                started_at=_utc(start),
                local_date=_local_date(start),
                sport_type=sport_type,
                # Active duration, not elapsed. Xiaomi excludes paused time.
                duration_s=int(duration) if duration else None,
                distance_m=_num(v.get("distance")),
                avg_hr=int(_num(v.get("avg_hrm")) or 0) or None,
                max_hr=int(_num(v.get("max_hrm")) or 0) or None,
                # total_cal is the gross figure; calories is the active burn.
                kcal=int(_num(v.get("calories")) or 0) or None,
                elevation_m=_num(v.get("rise_height")),
                raw={"csv_key": key, "category": row.get("Category"), "value": v},
                time_precision="exact",
                sets=(),
            )

    # ── daily wellness metrics ──────────────────────────────────────────────

    def fetch_daily_metrics(self) -> Iterable[DailyMetricRow]:
        sleep: dict[str, dict] = {}
        resting: dict[str, int] = {}
        stress_readings: dict[str, list[int]] = collections.defaultdict(list)

        # Single streaming pass over the large file. Only three Keys are read;
        # heart_rate alone is ~518k rows and is not needed here.
        for row in _rows(_find(self.export_dir, FITNESS_DATA)):
            key = row.get("Key")
            if key not in ("sleep", "resting_heart_rate", "stress"):
                continue
            try:
                v = json.loads(row.get("Value") or "")
            except json.JSONDecodeError:
                self.warnings.append(f"{key} row at Time={row.get('Time')}: bad JSON")
                continue
            if not isinstance(v, dict):
                continue

            if key == "resting_heart_rate":
                bpm = _num(v.get("bpm"))
                when = v.get("date_time") or row.get("Time")
                if bpm and when:
                    resting[_local_date(when)] = int(bpm)

            elif key == "stress":
                s = _num(v.get("stress"))
                when = v.get("time") or row.get("Time")
                if s and when:
                    stress_readings[_local_date(when)].append(int(s))

            elif key == "sleep":
                # Attributed to the day you woke up, which is the convention
                # every sleep tracker uses and what "last night's sleep" means.
                wake = v.get("wake_up_time") or v.get("device_wake_up_time") or row.get("Time")
                if not wake:
                    continue
                day = _local_date(wake)
                acc = sleep.setdefault(day, {"minutes": 0, "deep": 0, "light": 0,
                                             "rem": 0, "awake": 0, "segments": 0})
                # Durations are in MINUTES, and duration == deep + light + rem.
                acc["minutes"] += int(_num(v.get("duration")) or 0)
                acc["deep"] += int(_num(v.get("sleep_deep_duration")) or 0)
                acc["light"] += int(_num(v.get("sleep_light_duration")) or 0)
                acc["rem"] += int(_num(v.get("sleep_rem_duration")) or 0)
                acc["awake"] += int(_num(v.get("sleep_awake_duration")) or 0)
                acc["segments"] += 1

        steps = self._daily_steps()

        for day in sorted(set(sleep) | set(resting) | set(stress_readings) | set(steps)):
            s = sleep.get(day)
            readings = stress_readings.get(day) or []
            yield DailyMetricRow(
                source=self.name,
                local_date=day,
                resting_hr=resting.get(day),
                sleep_minutes=s["minutes"] if s else None,
                sleep_stages={"deep": s["deep"], "light": s["light"], "rem": s["rem"],
                              "awake": s["awake"], "segments": s["segments"]} if s else None,
                steps=steps.get(day),
                # Mean of that day's readings. Xiaomi also publishes its own
                # daily stress rollup; both cover exactly the same 69 days in
                # the reference archive (8,761 readings at ~127/day), so this
                # is chosen for being one consistent method, not for coverage.
                # Stress is by far the sparsest metric here — 69 days out of
                # 390 — because the band only samples it in specific modes.
                stress=round(sum(readings) / len(readings)) if readings else None,
                raw={"stress_readings": len(readings)} if readings else None,
            )

    def _daily_steps(self) -> dict[str, int]:
        """Daily step totals from the rollup file."""
        out: dict[str, int] = {}
        try:
            path = _find(self.export_dir, AGGREGATED)
        except FileNotFoundError:
            self.warnings.append("aggregated file missing; steps will be null")
            return out

        for row in _rows(path):
            # daily_mark rows are just {"has_data": true} and carry no values.
            if row.get("Tag") != "daily_report" or row.get("Key") != "steps":
                continue
            try:
                v = json.loads(row.get("Value") or "")
            except json.JSONDecodeError:
                continue
            n = _num(v.get("steps"))
            when = row.get("Time")
            if n and when:
                out[_local_date(when)] = int(n)
        return out
