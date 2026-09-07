"""Apple Health bulk export adapter.

The fixtures reproduce the quirks of a real archive rather than an idealized
one, because those quirks are where the import can quietly go wrong:

* the XML file is named in the phone's language, not always ``export.xml``
* distance and energy live in ``WorkoutStatistics``, not Workout attributes
* the same day's steps are recorded by the iPhone AND the Watch AND Mi Fitness,
  so a naive sum roughly doubles them
* the same ride is written to HealthKit by two apps with the same start second
* sleep is a run of stage samples that has to be folded into one night
"""

import pytest

from fitness_mcp import db
from fitness_mcp.ingest.apple_health_export import AppleHealthExportAdapter, _snake
from fitness_mcp.ingest.base import run_adapter

from .conftest import add_workout

HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="ru_KZ">\n'
FOOTER = "</HealthData>\n"


def record(type_, value, start, end=None, source="iPhone (Zhanbota)", unit="count"):
    unit_attr = f' unit="{unit}"' if unit else ""
    return (
        f'<Record type="{type_}"{unit_attr} value="{value}" sourceName="{source}" '
        f'startDate="{start}" endDate="{end or start}"/>\n'
    )


def workout(activity, start, end, duration_min, source="Apple Watch", stats=(), meta=()):
    body = "".join(
        f'<WorkoutStatistics type="{t}" startDate="{start}" endDate="{end}" '
        + " ".join(f'{k}="{v}"' for k, v in fields.items())
        + "/>\n"
        for t, fields in stats
    ) + "".join(f'<MetadataEntry key="{k}" value="{v}"/>\n' for k, v in meta)
    return (
        f'<Workout workoutActivityType="{activity}" duration="{duration_min}" '
        f'durationUnit="min" sourceName="{source}" startDate="{start}" endDate="{end}">\n'
        f"{body}</Workout>\n"
    )


def write_export(tmp_path, body, name="экспорт.xml"):
    d = tmp_path / "apple"
    d.mkdir(exist_ok=True)
    (d / name).write_text(HEADER + body + FOOTER, encoding="utf-8")
    # The clinical-records twin sits beside it in every real export and must be
    # ignored rather than parsed as a second copy of the data.
    (d / "export_cda.xml").write_text("<ClinicalDocument/>", encoding="utf-8")
    return str(d)


def health_rows(conn, metric):
    return {
        r["local_date"]: dict(r)
        for r in conn.execute(
            "SELECT * FROM health_daily WHERE metric = ? ORDER BY local_date", (metric,)
        )
    }


# ── file location ───────────────────────────────────────────────────────────

def test_finds_localized_xml_and_ignores_the_cda_twin(tmp_path):
    """Health names the file in the phone's language; ru_KZ gives экспорт.xml."""
    path = write_export(tmp_path, record("HKQuantityTypeIdentifierStepCount", "1000",
                                         "2026-08-01 09:00:00 +0500"))
    adapter = AppleHealthExportAdapter(export_dir=path)
    assert list(adapter.fetch_health_daily())


def test_missing_export_names_the_fix(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    adapter = AppleHealthExportAdapter(export_dir=str(d))
    with pytest.raises(FileNotFoundError, match="Export All Health Data"):
        list(adapter.fetch())


# ── the double-counting trap ────────────────────────────────────────────────

def test_steps_take_the_busiest_device_not_the_sum(tmp_path, fitness_db):
    """The single most important behaviour in this adapter.

    HealthKit keeps the iPhone's, the Watch's and Mi Fitness's copies of the
    same walk. Summing them reports roughly double the steps actually taken.
    """
    body = (
        record("HKQuantityTypeIdentifierStepCount", "9000", "2026-07-27 09:00:00 +0500")
        + record("HKQuantityTypeIdentifierStepCount", "5067", "2026-07-27 18:00:00 +0500")
        + record("HKQuantityTypeIdentifierStepCount", "14037", "2026-07-27 20:00:00 +0500",
                 source="Mi Fitness")
    )
    result = run_adapter(fitness_db, AppleHealthExportAdapter(export_dir=write_export(tmp_path, body)))
    assert not result.failed

    day = health_rows(fitness_db, "step_count")["2026-07-27"]
    # iPhone 9000 + 5067 = 14067 beats Mi Fitness's 14037. The sum, 28104, is
    # the wrong answer and the one a naive import produces.
    assert day["total"] == 14067
    assert day["kind"] == "cumulative"

    steps = fitness_db.execute(
        "SELECT steps FROM daily_metrics WHERE local_date = '2026-07-27'"
    ).fetchone()["steps"]
    assert steps == 14067


def test_discrete_readings_pool_across_devices_instead(tmp_path, fitness_db):
    """Two devices measuring heart rate is two real readings, not one twice."""
    body = (
        record("HKQuantityTypeIdentifierHeartRate", "60", "2026-08-02 09:00:00 +0500",
               unit="count/min")
        + record("HKQuantityTypeIdentifierHeartRate", "180", "2026-08-02 10:00:00 +0500",
                 unit="count/min", source="Apple Watch")
    )
    run_adapter(fitness_db, AppleHealthExportAdapter(export_dir=write_export(tmp_path, body)))

    day = health_rows(fitness_db, "heart_rate")["2026-08-02"]
    assert day["kind"] == "discrete"
    assert day["avg"] == 120
    assert (day["min"], day["max"]) == (60, 180)
    assert day["sample_count"] == 2
    # Summing heart-rate readings is meaningless, so it is deliberately absent
    # rather than present and wrong.
    assert day["total"] is None


# ── workouts ────────────────────────────────────────────────────────────────

def test_distance_and_hr_come_from_workout_statistics(tmp_path, fitness_db):
    """Current exports put these in child elements, not Workout attributes.

    Reading only the attributes silently loses every distance and calorie in
    the file, which looks like a training gap rather than a parse failure.
    """
    body = workout(
        "HKWorkoutActivityTypeRunning",
        "2026-07-02 20:53:54 +0500", "2026-07-02 22:44:45 +0500", "110.85",
        stats=[
            ("HKQuantityTypeIdentifierActiveEnergyBurned", {"sum": "783", "unit": "kcal"}),
            ("HKQuantityTypeIdentifierDistanceWalkingRunning",
             {"sum": "15.1045", "unit": "km"}),
            ("HKQuantityTypeIdentifierHeartRate",
             {"average": "148.5", "minimum": "92", "maximum": "176", "unit": "count/min"}),
        ],
    )
    run_adapter(fitness_db, AppleHealthExportAdapter(export_dir=write_export(tmp_path, body)))

    row = fitness_db.execute("SELECT * FROM workouts").fetchone()
    assert row["sport_type"] == "running"
    assert row["distance_m"] == pytest.approx(15104.5)   # km converted to metres
    assert row["kcal"] == 783
    assert (row["avg_hr"], row["max_hr"]) == (148, 176)
    assert row["duration_s"] == 6651                     # 110.85 min
    assert row["source"] == "apple_health_export"


def test_camel_case_activity_types_map_to_the_shared_vocabulary(tmp_path, fitness_db):
    """HKWorkoutActivityTypeTraditionalStrengthTraining is one word in the XML.

    The shared map is keyed on spaced words, so without splitting the CamelCase
    every multi-word Apple type would fall through to an invented sport name.
    """
    body = (
        workout("HKWorkoutActivityTypeTraditionalStrengthTraining",
                "2026-08-03 10:00:00 +0500", "2026-08-03 11:00:00 +0500", "60")
        + workout("HKWorkoutActivityTypeHighIntensityIntervalTraining",
                  "2026-08-04 10:00:00 +0500", "2026-08-04 10:30:00 +0500", "30")
        + workout("HKWorkoutActivityTypeOther",
                  "2026-08-05 10:00:00 +0500", "2026-08-05 10:30:00 +0500", "30")
    )
    run_adapter(fitness_db, AppleHealthExportAdapter(export_dir=write_export(tmp_path, body)))

    types = [r["sport_type"] for r in
             fitness_db.execute("SELECT sport_type FROM workouts ORDER BY local_date")]
    assert types == ["strength", "hiit", "workout"]


def test_two_apps_writing_one_ride_keep_the_richer_copy(tmp_path, fitness_db):
    """Mi Fitness and Strava both push the same commute into HealthKit.

    They share a start second, so they collapse onto one source_id. The copy
    carrying heart rate has to win regardless of which was parsed last.
    """
    start, end = "2026-07-27 01:38:26 +0500", "2026-07-27 02:10:00 +0500"
    body = (
        workout("HKWorkoutActivityTypeCycling", start, end, "31.5", source="Mi Fitness",
                stats=[("HKQuantityTypeIdentifierActiveEnergyBurned",
                        {"sum": "300", "unit": "kcal"})])
        + workout("HKWorkoutActivityTypeCycling", start, end, "31.5", source="Strava",
                  stats=[("HKQuantityTypeIdentifierActiveEnergyBurned",
                          {"sum": "300", "unit": "kcal"}),
                         ("HKQuantityTypeIdentifierDistanceCycling",
                          {"sum": "14.5", "unit": "km"}),
                         ("HKQuantityTypeIdentifierHeartRate",
                          {"average": "130", "maximum": "160", "unit": "count/min"})])
    )
    run_adapter(fitness_db, AppleHealthExportAdapter(export_dir=write_export(tmp_path, body)))

    rows = fitness_db.execute("SELECT * FROM workouts").fetchall()
    assert len(rows) == 1
    assert rows[0]["avg_hr"] == 130
    assert rows[0]["distance_m"] == pytest.approx(14500)


def test_reingest_is_idempotent(tmp_path, fitness_db):
    """Re-exports overlap almost entirely; a second run must not duplicate."""
    body = (
        workout("HKWorkoutActivityTypeCycling", "2026-08-10 07:00:00 +0500",
                "2026-08-10 07:40:00 +0500", "40")
        + record("HKQuantityTypeIdentifierStepCount", "8000", "2026-08-10 09:00:00 +0500")
    )
    path = write_export(tmp_path, body)

    first = run_adapter(fitness_db, AppleHealthExportAdapter(export_dir=path))
    second = run_adapter(fitness_db, AppleHealthExportAdapter(export_dir=path))

    assert (first.created, first.updated) == (1, 0)
    assert (second.created, second.updated) == (0, 1)
    assert fitness_db.execute("SELECT COUNT(*) c FROM workouts").fetchone()["c"] == 1
    assert fitness_db.execute("SELECT COUNT(*) c FROM health_daily").fetchone()["c"] == 1


# ── sleep ───────────────────────────────────────────────────────────────────

def test_sleep_stages_fold_into_one_night_on_the_waking_day(tmp_path, fitness_db):
    """In-bed and awake samples are time in bed, not sleep.

    Counting them inflates every night by however long it took to fall asleep.
    The night is attributed to the day of waking, which is the day a person
    means when they ask how they slept.
    """
    sleep = "HKCategoryTypeIdentifierSleepAnalysis"
    body = (
        record(sleep, "HKCategoryValueSleepAnalysisInBed",
               "2026-08-04 23:00:00 +0500", "2026-08-05 07:00:00 +0500", unit=None)
        + record(sleep, "HKCategoryValueSleepAnalysisAsleepDeep",
                 "2026-08-04 23:30:00 +0500", "2026-08-05 01:00:00 +0500", unit=None)
        + record(sleep, "HKCategoryValueSleepAnalysisAsleepREM",
                 "2026-08-05 01:00:00 +0500", "2026-08-05 02:00:00 +0500", unit=None)
        + record(sleep, "HKCategoryValueSleepAnalysisAsleepCore",
                 "2026-08-05 02:00:00 +0500", "2026-08-05 06:00:00 +0500", unit=None)
        + record(sleep, "HKCategoryValueSleepAnalysisAwake",
                 "2026-08-05 06:00:00 +0500", "2026-08-05 06:30:00 +0500", unit=None)
    )
    run_adapter(fitness_db, AppleHealthExportAdapter(export_dir=write_export(tmp_path, body)))

    row = fitness_db.execute(
        "SELECT * FROM daily_metrics WHERE local_date = '2026-08-05'"
    ).fetchone()
    # 90 deep + 60 REM + 240 core = 390. The 8h in bed and the 30min awake are
    # excluded; counting in-bed alone would report 480.
    assert row["sleep_minutes"] == 390
    import json
    assert json.loads(row["sleep_stages_json"]) == {"deep": 90, "rem": 60, "light": 240}


# ── the wide table's read path ──────────────────────────────────────────────

def test_health_metrics_separates_missing_from_misspelled(tmp_path, fitness_db):
    """An empty result must never be indistinguishable from a wrong name."""
    body = (
        record("HKQuantityTypeIdentifierBodyMass", "74.5", "2026-08-01 08:00:00 +0500", unit="kg")
        + record("HKQuantityTypeIdentifierBodyMass", "73.1", "2026-08-20 08:00:00 +0500", unit="kg")
    )
    run_adapter(fitness_db, AppleHealthExportAdapter(export_dir=write_export(tmp_path, body)))

    out = db.health_metrics(fitness_db, ["body_mass", "vo2_max"], "2026-08-01", "2026-08-31")
    assert out["metrics"]["body_mass"]["unit"] == "kg"
    assert out["metrics"]["body_mass"]["summary"]["min_day"] == 73.1
    assert out["metrics"]["body_mass"]["summary"]["range_total"] is None  # discrete
    assert "not stored" in out["unavailable"]["vo2_max"]

    out = db.health_metrics(fitness_db, ["body_mass"], "2026-09-01", "2026-09-30")
    assert "no readings fall in this date range" in out["unavailable"]["body_mass"]


def test_list_health_metrics_reports_coverage(tmp_path, fitness_db):
    body = (
        record("HKQuantityTypeIdentifierStepCount", "8000", "2026-08-01 09:00:00 +0500")
        + record("HKQuantityTypeIdentifierStepCount", "9000", "2026-08-09 09:00:00 +0500")
    )
    run_adapter(fitness_db, AppleHealthExportAdapter(export_dir=write_export(tmp_path, body)))

    listed = {r["metric"]: r for r in db.list_health_metrics(fitness_db)}
    assert listed["step_count"]["kind"] == "cumulative"
    assert listed["step_count"]["days"] == 2
    assert (listed["step_count"]["first_date"], listed["step_count"]["last_date"]) == (
        "2026-08-01", "2026-08-09")


# ── the daily_metrics collapse ──────────────────────────────────────────────

def test_two_wearables_on_one_day_collapse_to_a_single_row(fitness_db):
    """Xiaomi and Apple both cover late July 2026.

    Without the collapse, recovery_metrics returns two rows for the day and
    averages the same night's sleep in twice.
    """
    with fitness_db:
        db.upsert_daily_metric(fitness_db, db.DailyMetricRow(
            source="xiaomi_export", local_date="2026-07-27", resting_hr=52, sleep_minutes=400))
        db.upsert_daily_metric(fitness_db, db.DailyMetricRow(
            source="apple_health_export", local_date="2026-07-27",
            resting_hr=55, sleep_minutes=390, steps=14067))

    out = db.recovery_metrics(fitness_db, "2026-07-01", "2026-07-31")
    assert len(out["days"]) == 1
    day = out["days"][0]
    # xiaomi_export outranks apple_health_export, so its figures win...
    assert (day["resting_hr"], day["sleep_minutes"]) == (52, 400)
    # ...but steps, which only Apple recorded, are still filled in rather than
    # lost to a tidier "one source per day" rule.
    assert day["steps"] == 14067
    assert day["sources"] == ["xiaomi_export", "apple_health_export"]


def test_dedup_prefers_the_native_export_over_apples_copy(fitness_db):
    """Apple's re-export of a Strava ride is a lossy round trip of it."""
    add_workout(fitness_db, source="strava_export", source_id="s1",
                local_date="2026-07-02", started_at="2026-07-02T15:53:54Z",
                sport_type="running", duration_s=6651, distance_m=15104.0,
                elevation_m=120.0)
    add_workout(fitness_db, source="apple_health_export", source_id="a1",
                local_date="2026-07-02", started_at="2026-07-02T15:53:54Z",
                sport_type="running", duration_s=6651, distance_m=15104.5)

    merged = db.deduplicate(fitness_db)
    assert len(merged) == 1
    assert merged[0]["keep_source"] == "strava_export"
    assert merged[0]["supersede_source"] == "apple_health_export"


# ── naming ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("StepCount", "step_count"),
    ("HeartRate", "heart_rate"),
    ("VO2Max", "vo2_max"),
    ("HeartRateVariabilitySDNN", "heart_rate_variability_sdnn"),
    ("AppleExerciseTime", "apple_exercise_time"),
    ("WalkingDoubleSupportPercentage", "walking_double_support_percentage"),
    ("SixMinuteWalkTestDistance", "six_minute_walk_test_distance"),
])
def test_metric_names_are_guessable(raw, expected):
    """Claude types these names back into health_metrics, so they must read
    the way a person would guess them."""
    assert _snake(raw) == expected
