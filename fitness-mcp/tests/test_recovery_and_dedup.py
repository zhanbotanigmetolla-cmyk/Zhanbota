"""Schema v2: daily wellness metrics, recovery trends, cross-source dedup."""

import sqlite3

import pytest

from fitness_mcp import db

from .conftest import add_workout


# ── migration ───────────────────────────────────────────────────────────────

def test_v1_database_upgrades_in_place(tmp_path):
    """An existing v1 database must gain v2 columns without being rebuilt."""
    path = tmp_path / "old.db"
    conn = db.connect(path)
    conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    conn.executescript(db._SCHEMA_V1)
    conn.execute("INSERT INTO schema_version(version) VALUES (1)")
    conn.execute(
        """INSERT INTO workouts (source, source_id, started_at, local_date)
           VALUES ('pullup_bot', '1:2026-01-05', '2026-01-04T19:00:00Z', '2026-01-05')"""
    )
    conn.commit()

    db.migrate(conn)

    assert conn.execute("SELECT version FROM schema_version").fetchone()["version"] == 2
    row = conn.execute("SELECT time_precision, superseded_by FROM workouts").fetchone()
    # Bot rows carry a synthesized start time and must be marked as such.
    assert row["time_precision"] == "date_only"
    assert row["superseded_by"] is None
    assert conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0] == 0


def test_migrate_is_idempotent(fitness_db):
    db.migrate(fitness_db)
    db.migrate(fitness_db)
    assert fitness_db.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 1
    assert fitness_db.execute("SELECT version FROM schema_version").fetchone()["version"] == 2


# ── daily_metrics ───────────────────────────────────────────────────────────

def test_daily_metrics_upsert_is_idempotent(fitness_db):
    m = db.DailyMetricRow(source="xiaomi", local_date="2026-01-01", resting_hr=60,
                          sleep_minutes=420, steps=8000, stress=30,
                          sleep_stages={"deep": 90, "rem": 100})
    with fitness_db:
        db.upsert_daily_metric(fitness_db, m)
        db.upsert_daily_metric(fitness_db, m)
    assert fitness_db.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0] == 1

    m.resting_hr = 55
    with fitness_db:
        db.upsert_daily_metric(fitness_db, m)
    row = fitness_db.execute("SELECT * FROM daily_metrics").fetchone()
    assert row["resting_hr"] == 55
    assert '"deep": 90' in row["sleep_stages_json"]


# ── recovery_metrics ────────────────────────────────────────────────────────

@pytest.fixture
def wellness(fitness_db):
    days = [("2026-01-01", 60, 420), ("2026-01-02", 58, 400),
            ("2026-01-03", 54, 460), ("2026-01-04", 52, 480)]
    with fitness_db:
        for d, rhr, sleep in days:
            db.upsert_daily_metric(fitness_db, db.DailyMetricRow(
                source="xiaomi", local_date=d, resting_hr=rhr, sleep_minutes=sleep))
    return fitness_db


def test_recovery_metrics_hand_computed(wellness):
    r = db.recovery_metrics(wellness, "2026-01-01", "2026-01-31")
    assert len(r["days"]) == 4
    # resting HR 60, 58, 54, 52 -> mean 56.0
    assert r["resting_hr"] == {"avg": 56.0, "min": 52, "max": 60, "days_with_data": 4}
    # sleep 420, 400, 460, 480 -> mean 440.0
    assert r["sleep"]["avg_minutes"] == 440.0
    # first half (60, 58) = 59.0 ; second half (54, 52) = 53.0 ; delta -6.0
    assert r["trend"] == {
        "resting_hr_first_half": 59.0,
        "resting_hr_second_half": 53.0,
        "resting_hr_change": -6.0,
        "direction": "improving",
    }


def test_rising_resting_hr_reads_as_worsening(fitness_db):
    with fitness_db:
        for d, rhr in [("2026-02-01", 50), ("2026-02-02", 51),
                       ("2026-02-03", 56), ("2026-02-04", 58)]:
            db.upsert_daily_metric(fitness_db, db.DailyMetricRow(
                source="xiaomi", local_date=d, resting_hr=rhr))
    r = db.recovery_metrics(fitness_db, "2026-02-01", "2026-02-28")
    assert r["trend"]["direction"] == "worsening"
    assert r["trend"]["resting_hr_change"] == 6.5


def test_no_wellness_data_explains_itself_rather_than_returning_zeros(fitness_db):
    r = db.recovery_metrics(fitness_db, "2026-01-01", "2026-12-31")
    assert r["days"] == []
    assert r["resting_hr"] is None and r["sleep"] is None and r["trend"] is None
    assert "no data source is connected" in r["note"].lower()


def test_recovery_metrics_respects_range(wellness):
    r = db.recovery_metrics(wellness, "2026-01-02", "2026-01-03")
    assert [d["local_date"] for d in r["days"]] == ["2026-01-02", "2026-01-03"]


# ── cross-source dedup ──────────────────────────────────────────────────────

def _run_pair(conn, *, strava_time="2026-05-01T06:00:00Z",
              xiaomi_time="2026-05-01T06:01:00Z",
              strava_dur=1800, xiaomi_dur=1810):
    add_workout(conn, source="strava", source_id="s1", local_date="2026-05-01",
                started_at=strava_time, sport_type="running",
                duration_s=strava_dur, distance_m=5000.0)
    add_workout(conn, source="xiaomi", source_id="x1", local_date="2026-05-01",
                started_at=xiaomi_time, sport_type="running",
                duration_s=xiaomi_dur, distance_m=5000.0,
                avg_hr=150, max_hr=170, kcal=300)


def test_same_run_from_two_sources_collapses_to_the_richer_one(fitness_db):
    _run_pair(fitness_db)
    assert len(db.list_workouts(fitness_db, "2026-05-01", "2026-05-01")) == 2

    merged = db.deduplicate(fitness_db)
    assert len(merged) == 1
    assert merged[0]["keep_source"] == "xiaomi"      # has HR and calories
    assert merged[0]["supersede_source"] == "strava"
    assert merged[0]["start_gap_s"] == 60

    rows = db.list_workouts(fitness_db, "2026-05-01", "2026-05-01")
    assert len(rows) == 1
    assert rows[0]["source"] == "xiaomi"


def test_superseded_rows_disappear_from_every_aggregate(fitness_db):
    _run_pair(fitness_db)
    db.deduplicate(fitness_db)
    summary = db.training_summary(fitness_db, "2026-05-01", "2026-05-01", "day")
    assert summary[0]["sessions"] == 1
    assert summary[0]["duration_s"] == 1810          # the kept row's duration only
    hr = db.hr_distribution(fitness_db, "2026-05-01", "2026-05-01")
    assert hr["sessions_with_hr"] == 1


def test_dedup_keeps_the_losing_row_so_a_merge_is_reversible(fitness_db):
    _run_pair(fitness_db)
    db.deduplicate(fitness_db)
    assert fitness_db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 2

    with fitness_db:
        fitness_db.execute("UPDATE workouts SET superseded_by = NULL")
    assert len(db.list_workouts(fitness_db, "2026-05-01", "2026-05-01")) == 2


def test_dedup_is_idempotent(fitness_db):
    _run_pair(fitness_db)
    assert len(db.deduplicate(fitness_db)) == 1
    assert db.deduplicate(fitness_db) == []
    assert len(db.list_workouts(fitness_db, "2026-05-01", "2026-05-01")) == 1


def test_two_sessions_from_the_same_source_are_never_merged(fitness_db):
    """Back-to-back intervals in one source are distinct workouts, not duplicates."""
    add_workout(fitness_db, source="strava", source_id="a", local_date="2026-05-01",
                started_at="2026-05-01T06:00:00Z", duration_s=600)
    add_workout(fitness_db, source="strava", source_id="b", local_date="2026-05-01",
                started_at="2026-05-01T06:01:00Z", duration_s=600)
    assert db.deduplicate(fitness_db) == []
    assert len(db.list_workouts(fitness_db, "2026-05-01", "2026-05-01")) == 2


def test_date_only_rows_never_participate(fitness_db):
    """Bot sessions have a synthesized midnight start; time matching is meaningless."""
    add_workout(fitness_db, source="pullup_bot", source_id="p1", local_date="2026-05-01",
                time_precision="date_only",
                sets=[dict(exercise="pullups", reps=10, set_index=0)])
    add_workout(fitness_db, source="xiaomi", source_id="x1", local_date="2026-05-01",
                time_precision="date_only", duration_s=1800)
    assert db.deduplicate(fitness_db) == []
    assert len(db.list_workouts(fitness_db, "2026-05-01", "2026-05-01")) == 2


def test_start_times_outside_the_tolerance_are_separate_workouts(fitness_db):
    _run_pair(fitness_db, xiaomi_time="2026-05-01T06:10:00Z")   # 600s gap
    assert db.deduplicate(fitness_db) == []


def test_very_different_durations_are_not_merged(fitness_db):
    """Same start, wildly different length: a warm-up jog is not the long run."""
    _run_pair(fitness_db, strava_dur=600, xiaomi_dur=3600)
    assert db.deduplicate(fitness_db) == []


def test_tolerances_are_configurable(fitness_db):
    _run_pair(fitness_db, xiaomi_time="2026-05-01T06:10:00Z")
    assert db.deduplicate(fitness_db, time_tolerance_s=900) != []


def test_dedup_prefers_richer_regardless_of_insert_order(fitness_db):
    """The poorer row inserted second must still lose."""
    add_workout(fitness_db, source="xiaomi", source_id="x1", local_date="2026-05-01",
                started_at="2026-05-01T06:00:00Z", duration_s=1800, distance_m=5000.0,
                avg_hr=150, max_hr=170, kcal=300)
    add_workout(fitness_db, source="strava", source_id="s1", local_date="2026-05-01",
                started_at="2026-05-01T06:00:30Z", duration_s=1800)
    merged = db.deduplicate(fitness_db)
    assert merged[0]["keep_source"] == "xiaomi"
