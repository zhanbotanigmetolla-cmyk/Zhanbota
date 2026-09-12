"""Apple Health bulk export ingest — the whole HealthKit archive, from a file.

This is the *archive* counterpart to :mod:`apple_health`, which receives a
rolling 7-day window pushed from an iOS Shortcut. Same underlying data, two very
different shapes, so they are two adapters and two sources:

    apple_health         live, pushed, last 7 days, whatever the phone could read
    apple_health_export  historical, complete, everything Health has ever stored

They are kept as separate sources rather than merged on write because the export
is richer per workout (it carries WorkoutStatistics — heart rate, distance and
energy that the Shortcut does not send) and because a later push must never be
able to overwrite an archive row with a thinner version of itself. Where both
hold the same session, ordinary cross-source deduplication merges them.

Getting the file
----------------
iPhone → Health → profile picture → Export All Health Data. That produces a zip
holding ``export.xml`` (or a localized name — this export's is ``экспорт.xml``),
plus ECG CSVs and GPX workout routes, neither of which is imported.

Scale, and why this streams
---------------------------
The archive is a single XML document; the one this was written against is 183 MB
with 417,000 records. The server it runs on has 1 GB of RAM, so a DOM parse is
out of the question. ``iterparse`` handles one element at a time and the root is
cleared as it goes, which keeps the resident set flat regardless of file size.

Everything is aggregated to daily figures. Storing 54,000 individual heart-rate
samples would grow the database by two orders of magnitude to answer questions
nobody asks — "what was my resting heart rate that week" needs a daily series,
not a sample stream.

Multi-device double counting
----------------------------
The single most dangerous thing about this file. HealthKit stores overlapping
samples from every device that recorded them: an iPhone in a pocket and an Apple
Watch on the wrist both log the same walk, and Mi Fitness syncs a third copy.
Health itself de-duplicates at query time, but the export is raw.

Naively summing a day's StepCount samples therefore roughly doubles it — on
2026-07-27 that is 28,104 steps instead of the 14,067 actually walked. So
cumulative metrics are totalled per device first, and the highest single device
wins the day. Discrete readings (heart rate, body mass) are pooled instead,
because two devices taking a reading is two genuine readings, not one twice.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from ..config import LOCAL_TZ
from ..db import DailyMetricRow, HealthDailyRow, WorkoutRow
from .apple_health import _NOT_ASLEEP, _STAGES, _TYPE_MAP, _normalize

log = logging.getLogger("fitness_mcp.ingest.apple_health_export")

SOURCE = "apple_health_export"

# Localized export filenames. Health names the file in the phone's language, so
# a fixed "export.xml" would fail on any non-English device — this archive's is
# Russian. Anything else *.xml at the top level is tried as a last resort.
_XML_NAMES = ("export.xml", "экспорт.xml", "Export.xml", "エクスポート.xml", "exportar.xml")

# Apple's clinical-records mirror of the same data, in a different schema. It
# holds nothing this adapter wants and parsing it would double the work.
_IGNORED_XML = {"export_cda.xml"}

_PREFIXES = (
    "HKQuantityTypeIdentifier",
    "HKCategoryTypeIdentifier",
    "HKDataType",
)

# Metrics where a day's meaningful figure is the TOTAL, so per-device sums are
# compared and the largest wins. Everything not listed here is treated as a
# discrete reading and pooled across devices — that default is the safe one,
# since wrongly pooling a cumulative metric inflates it while wrongly totalling
# a discrete one produces an obviously absurd number that gets noticed.
_CUMULATIVE = {
    "StepCount", "FlightsClimbed", "PushCount", "SwimmingStrokeCount",
    "ActiveEnergyBurned", "BasalEnergyBurned",
    "AppleExerciseTime", "AppleStandTime", "AppleMoveTime", "TimeInDaylight",
    "NumberOfTimesFallen", "MindfulSession", "AppleStandHour",
}

# Prefix rules covering the families Apple keeps extending: every Distance* is a
# length travelled and every Dietary* is an intake, both of which accumulate.
_CUMULATIVE_PREFIXES = ("Distance", "Dietary")

_DT_FMT = "%Y-%m-%d %H:%M:%S %z"

# Lengths normalize to metres; Apple varies the unit by locale and by metric.
_TO_METRES = {"km": 1000.0, "m": 1.0, "mi": 1609.344, "ft": 0.3048, "cm": 0.01, "yd": 0.9144}


def _scale(value: float, unit: str | None) -> float:
    """Convert HealthKit's fractional percentages to actual percentages.

    HKUnit.percent() is a fraction: body fat 27% is stored as 0.27 with the unit
    written as "%". Passing that through unchanged is worse than an obvious
    error, because "0.27% body fat" and "blood oxygen 1%" read as catastrophic
    medical readings rather than as a unit bug. Every percent metric in this
    archive — body fat, blood oxygen, walking steadiness, gait asymmetry and
    double support — is confirmed to be 0..1.
    """
    if (unit or "").strip() == "%":
        return value * 100.0
    return value


def _is_cumulative(kind_name: str) -> bool:
    return kind_name in _CUMULATIVE or kind_name.startswith(_CUMULATIVE_PREFIXES)


def _strip_prefix(raw_type: str) -> str:
    for prefix in _PREFIXES:
        if raw_type.startswith(prefix):
            return raw_type[len(prefix):]
    return raw_type


def _snake(name: str) -> str:
    """CamelCase to snake_case, keeping acronyms and digits readable.

    StepCount -> step_count, VO2Max -> vo2_max, HeartRateVariabilitySDNN ->
    heart_rate_variability_sdnn. These names are what Claude sees and types back
    into health_metrics, so they have to be guessable rather than merely unique.
    """
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


def _words(name: str) -> str:
    """CamelCase to spaced words, for matching against the shared type map."""
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name).strip()


def _parse_dt(text: str | None) -> datetime | None:
    """Parse an Apple export timestamp ('2026-06-30 21:36:35 +0500') to UTC."""
    if not text:
        return None
    try:
        return datetime.strptime(text, _DT_FMT).astimezone(timezone.utc)
    except ValueError:
        pass
    try:  # ISO-8601, in case a future export version switches format
        cleaned = text.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return (dt if dt.tzinfo else dt.replace(tzinfo=LOCAL_TZ)).astimezone(timezone.utc)
    except ValueError:
        return None


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _local_date(dt: datetime) -> str:
    return dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_metres(value: float, unit: str | None) -> float:
    return value * _TO_METRES.get((unit or "").strip().lower(), 1.0)


class AppleHealthExportAdapter:
    """Reads one Apple Health export directory (or a direct path to its XML).

    The file is parsed exactly once, on the first ``fetch*`` call, and the three
    output streams are served from the parsed result. A second pass over 183 MB
    to collect daily metrics after collecting workouts would double an already
    slow import for no gain.
    """

    name = SOURCE

    def __init__(self, export_dir: str | Path | None = None,
                 xml_path: str | Path | None = None) -> None:
        if not export_dir and not xml_path:
            raise ValueError("one of export_dir or xml_path is required")
        self.export_dir = Path(export_dir).expanduser() if export_dir else None
        self.xml_path = Path(xml_path).expanduser() if xml_path else None
        self.warnings: list[str] = []
        self._parsed = False
        self._workouts: dict[str, WorkoutRow] = {}
        self._daily: list[DailyMetricRow] = []
        self._health: list[HealthDailyRow] = []
        # Unmapped types are reported once each rather than once per sample —
        # 54,000 identical warnings would bury everything else.
        self._unmapped: set[str] = set()

    # ── file location ───────────────────────────────────────────────────────

    def _resolve_xml(self) -> Path:
        if self.xml_path:
            if not self.xml_path.is_file():
                raise FileNotFoundError(f"Apple Health XML not found: {self.xml_path}")
            return self.xml_path

        root = self.export_dir
        if not root.is_dir():
            raise FileNotFoundError(f"Apple Health export directory not found: {root}")

        # Health nests the payload one level down in some export versions.
        for base in (root, root / "apple_health_export"):
            for candidate in _XML_NAMES:
                if (base / candidate).is_file():
                    return base / candidate

        for base in (root, root / "apple_health_export"):
            if not base.is_dir():
                continue
            others = sorted(p for p in base.glob("*.xml") if p.name not in _IGNORED_XML)
            if others:
                self.warnings.append(
                    f"no recognized export filename in {base}; using {others[0].name}"
                )
                return others[0]

        raise FileNotFoundError(
            f"No Apple Health XML in {root}. Expected one of {', '.join(_XML_NAMES)} — "
            "unzip the archive from Health > Export All Health Data into this directory."
        )

    # ── parsing ─────────────────────────────────────────────────────────────

    def _parse(self) -> None:
        if self._parsed:
            return
        path = self._resolve_xml()
        log.info("parsing Apple Health export %s (%.0f MB)",
                 path.name, path.stat().st_size / 1e6)

        # (metric, day, device) -> [total, samples, unit]; the device dimension
        # exists purely so the multi-device comparison described in the module
        # docstring is possible.
        cumulative: dict[tuple[str, str, str], list] = {}
        # (metric, day) -> [samples, total, min, max, unit]
        discrete: dict[tuple[str, str], list] = {}
        # (day, device) -> {"minutes": float, "stages": {...}, "samples": int}
        sleep: dict[tuple[str, str], dict] = {}

        records = 0
        root = None
        for event, el in ET.iterparse(str(path), events=("start", "end")):
            if event == "start":
                if root is None:
                    root = el
                continue

            if el.tag == "Record":
                records += 1
                self._record(el, cumulative, discrete, sleep)
            elif el.tag == "Workout":
                self._workout(el)
            else:
                # Child elements (MetadataEntry, WorkoutStatistics) end before
                # their parent does. Clearing them here would wipe the
                # attributes the parent handler is about to read.
                continue

            # Clearing the element frees its children; clearing the root drops
            # the growing list of already-processed siblings. Without the second
            # call, memory climbs to roughly the size of the file.
            el.clear()
            if root is not None:
                root.clear()

        log.info("parsed %d records and %d workouts", records, len(self._workouts))
        self._build_health_daily(cumulative, discrete)
        self._build_daily_metrics(cumulative, discrete, sleep)
        self._parsed = True

    # ── records ─────────────────────────────────────────────────────────────

    def _record(self, el: ET.Element, cumulative: dict, discrete: dict, sleep: dict) -> None:
        raw_type = el.get("type") or ""
        kind_name = _strip_prefix(raw_type)
        start = _parse_dt(el.get("startDate"))
        if start is None:
            return
        device = el.get("sourceName") or "unknown"

        if kind_name == "SleepAnalysis":
            self._sleep_record(el, start, device, sleep)
            return

        value = _num(el.get("value"))
        if value is None:
            # A category record whose value is a state name, not a number.
            self._category_record(el, kind_name, start, device, cumulative)
            return

        metric = _snake(kind_name)
        unit = el.get("unit")
        value = _scale(value, unit)
        day = _local_date(start)

        if _is_cumulative(kind_name):
            slot = cumulative.setdefault((metric, day, device), [0.0, 0, unit])
            slot[0] += value
            slot[1] += 1
        else:
            slot = discrete.setdefault((metric, day), [0, 0.0, value, value, unit])
            slot[0] += 1
            slot[1] += value
            slot[2] = min(slot[2], value)
            slot[3] = max(slot[3], value)

    def _category_record(self, el: ET.Element, kind_name: str, start: datetime,
                         device: str, cumulative: dict) -> None:
        """Category records carry a state name instead of a number.

        Only the two that mean something quantitatively are converted. The rest
        are counted into a warning rather than dropped in silence, so a future
        version knows what it is leaving on the table.
        """
        day = _local_date(start)
        value = _normalize(el.get("value") or "")

        if kind_name == "MindfulSession":
            end = _parse_dt(el.get("endDate"))
            minutes = (end - start).total_seconds() / 60.0 if end else 0.0
            if minutes <= 0:
                return
            slot = cumulative.setdefault(("mindful_minutes", day, device), [0.0, 0, "min"])
            slot[0] += minutes
            slot[1] += 1
        elif kind_name == "AppleStandHour":
            # Two states: stood, or idle. Only the stood hours are the metric —
            # counting both would report a flat 24 every day.
            if "idle" in value:
                return
            slot = cumulative.setdefault(("stand_hours", day, device), [0.0, 0, "count"])
            slot[0] += 1
            slot[1] += 1
        elif kind_name not in self._unmapped:
            self._unmapped.add(kind_name)
            self.warnings.append(
                f"{kind_name} is a non-numeric category record and was not imported"
            )

    def _sleep_record(self, el: ET.Element, start: datetime, device: str, sleep: dict) -> None:
        end = _parse_dt(el.get("endDate"))
        if end is None:
            return
        minutes = (end - start).total_seconds() / 60.0
        if minutes <= 0 or minutes > 24 * 60:
            return

        value = _normalize(el.get("value") or "")
        # "In bed" and "awake" are time in bed, not sleep. Counting them inflates
        # every night by however long it took to fall asleep.
        if any(token in value for token in _NOT_ASLEEP):
            return

        stage = "unspecified"
        for needles, name in _STAGES:
            if any(n in value for n in needles):
                stage = name
                break

        # Attributed to the day the sample ENDS — the day you woke up, which is
        # the day a person means by "how did I sleep".
        key = (_local_date(end), device)
        acc = sleep.setdefault(key, {"minutes": 0.0, "stages": {}, "samples": 0})
        acc["minutes"] += minutes
        acc["stages"][stage] = acc["stages"].get(stage, 0.0) + minutes
        acc["samples"] += 1

    # ── workouts ────────────────────────────────────────────────────────────

    def _workout(self, el: ET.Element) -> None:
        start = _parse_dt(el.get("startDate"))
        if start is None:
            self.warnings.append(f"workout skipped: unreadable startDate {el.get('startDate')!r}")
            return
        start = start.replace(microsecond=0)

        raw_type = _strip_prefix_workout(el.get("workoutActivityType") or "")
        sport_type = _TYPE_MAP.get(_normalize(_words(raw_type)))
        if sport_type is None:
            sport_type = _snake(raw_type) or "workout"
            if raw_type not in self._unmapped:
                self._unmapped.add(raw_type)
                self.warnings.append(
                    f"unmapped Apple workout type {raw_type!r}; stored as {sport_type!r}"
                )

        end = _parse_dt(el.get("endDate"))
        duration = _num(el.get("duration"))
        if duration is not None and (el.get("durationUnit") or "min") == "min":
            duration *= 60.0
        if duration is None and end is not None:
            duration = (end - start).total_seconds()
        if duration is not None and duration < 0:
            duration = None

        # Recent export versions moved distance and energy out of the Workout
        # attributes and into WorkoutStatistics children; this archive has ONLY
        # the children, so reading the attributes alone would lose every
        # distance and calorie figure in the file.
        stats = self._workout_statistics(el)
        distance_m = stats.get("distance_m")
        kcal = stats.get("kcal")
        avg_hr = stats.get("avg_hr")
        max_hr = stats.get("max_hr")

        meta = {m.get("key"): m.get("value") for m in el.findall("MetadataEntry")}
        elevation_m = None
        raw_elevation = meta.get("HKElevationAscended")
        if raw_elevation:
            parts = str(raw_elevation).split()
            climbed = _num(parts[0])
            if climbed is not None:
                elevation_m = _to_metres(climbed, parts[1] if len(parts) > 1 else "cm")

        source_id = f"{int(start.timestamp())}:{sport_type}"
        row = WorkoutRow(
            source=SOURCE,
            source_id=source_id,
            started_at=_utc(start),
            local_date=_local_date(start),
            sport_type=sport_type,
            duration_s=int(duration) if duration else None,
            distance_m=distance_m,
            avg_hr=int(avg_hr) if avg_hr else None,
            max_hr=int(max_hr) if max_hr else None,
            kcal=int(kcal) if kcal else None,
            elevation_m=elevation_m,
            raw={
                "activity_type": el.get("workoutActivityType"),
                "recorded_by": el.get("sourceName"),
                "device": el.get("device"),
                "statistics": stats.get("_all"),
                "external_uuid": meta.get("HKExternalUUID"),
                "indoor": meta.get("HKIndoorWorkout"),
            },
            time_precision="exact",
            sets=(),
        )

        # The same ride reaches HealthKit from more than one app — Mi Fitness
        # and Strava both write the 07-27 commute, with the same start second.
        # They collapse onto one source_id, so the richer copy has to win rather
        # than whichever happened to be parsed last.
        previous = self._workouts.get(source_id)
        if previous is None or _richness(row) > _richness(previous):
            self._workouts[source_id] = row

    def _workout_statistics(self, el: ET.Element) -> dict:
        """Pull heart rate, distance and energy out of WorkoutStatistics."""
        out: dict[str, Any] = {}
        collected: dict[str, dict] = {}

        for stat in el.findall("WorkoutStatistics"):
            name = _strip_prefix(stat.get("type") or "")
            unit = stat.get("unit")
            total, avg = _num(stat.get("sum")), _num(stat.get("average"))
            low, high = _num(stat.get("minimum")), _num(stat.get("maximum"))
            collected[_snake(name)] = {
                k: v for k, v in
                (("sum", total), ("avg", avg), ("min", low), ("max", high), ("unit", unit))
                if v is not None
            }

            if name == "HeartRate":
                out["avg_hr"], out["max_hr"] = avg, high
            elif name == "ActiveEnergyBurned" and total is not None:
                out["kcal"] = total
            elif name.startswith("Distance") and total is not None:
                # A session can log two distance flavours (cycling plus walking
                # on a mixed commute); the longest is the session's distance.
                metres = _to_metres(total, unit)
                out["distance_m"] = max(metres, out.get("distance_m") or 0.0)

        out["_all"] = collected or None
        return out

    # ── aggregation into output rows ────────────────────────────────────────

    def _build_health_daily(self, cumulative: dict, discrete: dict) -> None:
        for (metric, day), best in _resolve_devices(cumulative).items():
            total, samples, unit = best
            self._health.append(HealthDailyRow(
                source=SOURCE, local_date=day, metric=metric, kind="cumulative",
                unit=unit, sample_count=samples,
                total=round(total, 4),
                # A daily total's "average" is the average sample, which is only
                # meaningful alongside the count; min/max per sample are noise
                # at day granularity and are left null rather than invented.
                avg=round(total / samples, 4) if samples else None,
            ))

        for (metric, day), (samples, total, low, high, unit) in discrete.items():
            self._health.append(HealthDailyRow(
                source=SOURCE, local_date=day, metric=metric, kind="discrete",
                unit=unit, sample_count=samples,
                total=None,        # summing readings is meaningless, so it stays null
                avg=round(total / samples, 4) if samples else None,
                min=round(low, 4), max=round(high, 4),
            ))

        self._health.sort(key=lambda r: (r.local_date, r.metric))

    def _build_daily_metrics(self, cumulative: dict, discrete: dict, sleep: dict) -> None:
        """Mirror the handful of curated metrics into daily_metrics.

        recovery_metrics reads that narrow table, so resting HR, sleep and steps
        are written to both places. The duplication is deliberate: it keeps the
        existing tool working across every source without teaching it the wide
        table's shape.
        """
        resolved = _resolve_devices(cumulative)
        steps = {day: slot[0] for (metric, day), slot in resolved.items() if metric == "step_count"}
        resting = {
            day: total / samples
            for (metric, day), (samples, total, _, _, _) in discrete.items()
            if metric == "resting_heart_rate" and samples
        }

        # One night can be recorded by the watch and by a second app. Pick the
        # device that saw the most sleep rather than adding them: the overlap is
        # the same night twice, and summing invents ten-hour nights.
        nights: dict[str, dict] = {}
        for (day, _device), acc in sleep.items():
            if day not in nights or acc["minutes"] > nights[day]["minutes"]:
                nights[day] = acc

        for day in sorted(set(steps) | set(resting) | set(nights)):
            night = nights.get(day)
            self._daily.append(DailyMetricRow(
                source=SOURCE,
                local_date=day,
                resting_hr=round(resting[day]) if day in resting else None,
                sleep_minutes=round(night["minutes"]) if night else None,
                sleep_stages={k: round(v) for k, v in night["stages"].items()} if night else None,
                steps=round(steps[day]) if day in steps else None,
                stress=None,          # Apple has no stress equivalent
                raw={"sleep_samples": night["samples"]} if night else None,
            ))

    # ── adapter protocol ────────────────────────────────────────────────────

    def fetch(self) -> Iterable[WorkoutRow]:
        self._parse()
        return sorted(self._workouts.values(), key=lambda w: w.started_at)

    def fetch_daily_metrics(self) -> Iterable[DailyMetricRow]:
        self._parse()
        return self._daily

    def fetch_health_daily(self) -> Iterable[HealthDailyRow]:
        self._parse()
        return self._health


def _strip_prefix_workout(raw: str) -> str:
    prefix = "HKWorkoutActivityType"
    return raw[len(prefix):] if raw.startswith(prefix) else raw


_RICHNESS_FIELDS = ("duration_s", "distance_m", "avg_hr", "max_hr", "kcal", "elevation_m")


def _richness(row: WorkoutRow) -> int:
    return sum(1 for f in _RICHNESS_FIELDS if getattr(row, f) is not None)


def _resolve_devices(cumulative: dict) -> dict[tuple[str, str], list]:
    """Collapse per-device daily totals to one figure per (metric, day).

    The device that recorded the most wins outright. Adding devices together is
    the wrong answer — see the module docstring — and averaging them would drag
    a full day's step count down toward whatever a phone left on a desk saw.
    """
    best: dict[tuple[str, str], list] = {}
    for (metric, day, _device), slot in cumulative.items():
        key = (metric, day)
        if key not in best or slot[0] > best[key][0]:
            best[key] = slot
    return best
