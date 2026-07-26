"""Aggregation arithmetic, against a fixture with hand-computed totals.

The fixture calendar (2026-01-01 is a Thursday, so 2026-01-05 is a Monday):

  date         weekday  exercise         sets              reps
  2026-01-05   Mon      pullups          [10, 8, 7]          25
  2026-01-07   Wed      pullups          [12, 10]            22
  2026-01-07   Wed      pushups          [20]                20
  2026-01-11   Sun      pullups          [5]                  5
  2026-01-12   Mon      pullups          [15]                15
  2026-01-13   Tue      pullups          [100] inferred     100
  2026-02-01   Sun      pullups          [9]                  9

2026-02-01 is a Sunday, so it belongs to the week beginning Monday 2026-01-26 —
a week that straddles the month boundary, which is where naive bucketing breaks.

Weeks:  2026-01-05 -> 25 + 42 + 5 = 72 over 3 sessions
        2026-01-12 -> 15 + 100    = 115 over 2 sessions
        2026-01-26 -> 9           = 9 over 1 session
Months: 2026-01    -> 187 over 5 sessions
        2026-02    -> 9 over 1 session
Total:  196 reps over 6 sessions
"""

import pytest

from fitness_mcp import db

from .conftest import add_workout

TOTAL_REPS = 196
TOTAL_SESSIONS = 6
RANGE = ("2026-01-01", "2026-02-28")


@pytest.fixture
def seeded(fitness_db):
    conn = fitness_db
    add_workout(conn, source_id="w1", local_date="2026-01-05",
                sets=[dict(exercise="pullups", reps=r, set_index=i, rpe=7.0)
                      for i, r in enumerate([10, 8, 7])])
    # duration lives on the session, not the set: three sets must not multiply it.
    add_workout(conn, source_id="w2", local_date="2026-01-07", duration_s=1800,
                distance_m=500.0,
                sets=[dict(exercise="pullups", reps=12, set_index=0),
                      dict(exercise="pullups", reps=10, set_index=1),
                      dict(exercise="pushups", reps=20, set_index=0)])
    add_workout(conn, source_id="w3", local_date="2026-01-11",
                sets=[dict(exercise="pullups", reps=5, set_index=0)])
    add_workout(conn, source_id="w4", local_date="2026-01-12",
                sets=[dict(exercise="pullups", reps=15, set_index=0)])
    add_workout(conn, source_id="w5", local_date="2026-01-13",
                sets=[dict(exercise="pullups", reps=100, set_index=0, inferred=True)])
    add_workout(conn, source_id="w6", local_date="2026-02-01",
                sets=[dict(exercise="pullups", reps=9, set_index=0)])
    return conn


# ── training_summary ────────────────────────────────────────────────────────

def test_day_buckets_match_hand_computed(seeded):
    got = {r["bucket"]: (r["sessions"], r["total_reps"])
           for r in db.training_summary(seeded, *RANGE, "day")}
    assert got == {
        "2026-01-05": (1, 25),
        "2026-01-07": (1, 42),
        "2026-01-11": (1, 5),
        "2026-01-12": (1, 15),
        "2026-01-13": (1, 100),
        "2026-02-01": (1, 9),
    }


def test_week_buckets_are_mondays_and_straddle_month_boundary(seeded):
    got = {r["bucket"]: (r["sessions"], r["total_reps"])
           for r in db.training_summary(seeded, *RANGE, "week")}
    assert got == {
        "2026-01-05": (3, 72),
        "2026-01-12": (2, 115),
        "2026-01-26": (1, 9),   # Sunday 2026-02-01 belongs to the previous Monday
    }


def test_month_buckets(seeded):
    got = {r["bucket"]: (r["sessions"], r["total_reps"])
           for r in db.training_summary(seeded, *RANGE, "month")}
    assert got == {"2026-01": (5, 187), "2026-02": (1, 9)}


@pytest.mark.parametrize("group_by", ["day", "week", "month"])
def test_every_grouping_is_a_partition(seeded, group_by):
    """No bucketing may lose or duplicate volume."""
    rows = db.training_summary(seeded, *RANGE, group_by)
    assert sum(r["total_reps"] for r in rows) == TOTAL_REPS
    assert sum(r["sessions"] for r in rows) == TOTAL_SESSIONS


def test_duration_is_not_multiplied_by_set_count(seeded):
    """Regression guard: joining sets to workouts directly fans out the rows."""
    week = next(r for r in db.training_summary(seeded, *RANGE, "week")
                if r["bucket"] == "2026-01-05")
    assert week["duration_s"] == 1800      # not 1800 * 3
    assert week["distance_m"] == 500.0     # not 1500.0


def test_range_bounds_are_inclusive(seeded):
    rows = db.training_summary(seeded, "2026-01-05", "2026-01-05", "day")
    assert [r["bucket"] for r in rows] == ["2026-01-05"]


def test_empty_range_returns_no_buckets(seeded):
    assert db.training_summary(seeded, "2025-01-01", "2025-12-31", "day") == []


def test_invalid_group_by_rejected(seeded):
    with pytest.raises(ValueError):
        db.training_summary(seeded, *RANGE, "quarter")


# ── list / get ──────────────────────────────────────────────────────────────

def test_list_workouts_newest_first_and_summarised(seeded):
    rows = db.list_workouts(seeded, *RANGE)
    assert [r["local_date"] for r in rows][:2] == ["2026-02-01", "2026-01-13"]
    multi = next(r for r in rows if r["local_date"] == "2026-01-07")
    assert multi["total_reps"] == 42
    assert multi["set_count"] == 3
    assert sorted(multi["exercises"].split(",")) == ["pullups", "pushups"]


def test_list_workouts_respects_limit_and_sport_filter(seeded):
    assert len(db.list_workouts(seeded, *RANGE, limit=2)) == 2
    assert db.list_workouts(seeded, *RANGE, sport_type="running") == []


def test_get_workout_includes_sets_and_total(seeded):
    wid = db.list_workouts(seeded, "2026-01-07", "2026-01-07")[0]["id"]
    w = db.get_workout(seeded, wid)
    assert w["total_reps"] == 42
    assert len(w["sets"]) == 3
    assert {s["exercise"] for s in w["sets"]} == {"pullups", "pushups"}


def test_get_workout_missing_returns_none(seeded):
    assert db.get_workout(seeded, 99999) is None


# ── exercise_history ────────────────────────────────────────────────────────

def test_exercise_history_is_chronological_and_scoped(seeded):
    hist = db.exercise_history(seeded, "pullups")
    assert [h["local_date"] for h in hist] == sorted(h["local_date"] for h in hist)
    assert all("pushups" not in str(h) for h in hist)
    assert sum(h["reps"] for h in hist) == 176      # 196 total minus 20 pushups


def test_exercise_history_date_filters(seeded):
    hist = db.exercise_history(seeded, "pullups", "2026-01-07", "2026-01-12")
    assert {h["local_date"] for h in hist} == {"2026-01-07", "2026-01-11", "2026-01-12"}


# ── personal_records ────────────────────────────────────────────────────────

def test_inferred_sets_count_as_volume_but_never_as_a_record(seeded):
    """The 100-rep inferred set is real volume but was never a single set."""
    pr = next(p for p in db.personal_records(seeded, "pullups"))
    assert pr["best_set_by_reps"]["reps"] == 15
    assert pr["best_set_by_reps"]["local_date"] == "2026-01-12"
    # ...while still contributing its reps to the session total
    assert pr["best_session_total_reps"]["reps"] == 100


def test_bodyweight_records_report_null_rather_than_a_fabricated_1rm(seeded):
    for pr in db.personal_records(seeded):
        assert pr["best_set_by_weight"] is None
        assert pr["estimated_1rm"] is None


def test_weighted_work_does_produce_a_1rm(seeded):
    add_workout(seeded, source_id="w7", local_date="2026-01-20",
                sets=[dict(exercise="weighted_pullups", reps=5,
                           weight_kg=20.0, set_index=0)])
    pr = db.personal_records(seeded, "weighted_pullups")[0]
    assert pr["best_set_by_weight"]["weight_kg"] == 20.0
    # Epley: 20 * (1 + 5/30) = 23.333...
    assert pr["estimated_1rm"]["est_1rm"] == pytest.approx(23.3333, abs=1e-3)
    assert pr["estimated_1rm"]["formula"] == "Epley"


def test_personal_records_filters_by_exercise(seeded):
    assert [p["exercise"] for p in db.personal_records(seeded, "pushups")] == ["pushups"]
    assert {p["exercise"] for p in db.personal_records(seeded)} == {"pullups", "pushups"}


# ── hr_distribution ─────────────────────────────────────────────────────────

def test_hr_distribution_reports_absence_instead_of_empty_zeros(seeded):
    hr = db.hr_distribution(seeded, *RANGE)
    assert hr["sessions_with_hr"] == 0
    assert hr["sessions_without_hr"] == TOTAL_SESSIONS
    assert hr["reference_max_hr"] is None
    assert all(z["sessions"] == 0 for z in hr["zones"])


def test_hr_distribution_buckets_sessions_by_average(fitness_db):
    conn = fitness_db
    # reference max becomes 200, so the zone edges are 120/140/160/180.
    add_workout(conn, source_id="z1", local_date="2026-03-02",
                avg_hr=110, max_hr=200, duration_s=600)   # 55% -> Z1
    add_workout(conn, source_id="z3", local_date="2026-03-03",
                avg_hr=150, max_hr=190, duration_s=1200)  # 75% -> Z3
    add_workout(conn, source_id="z5", local_date="2026-03-04",
                avg_hr=185, max_hr=195, duration_s=300)   # 92.5% -> Z5
    hr = db.hr_distribution(conn, "2026-03-01", "2026-03-31")
    zones = {z["zone"]: z for z in hr["zones"]}
    assert hr["reference_max_hr"] == 200
    assert hr["sessions_with_hr"] == 3
    assert zones["Z1 recovery"]["duration_s"] == 600
    assert zones["Z3 tempo"]["duration_s"] == 1200
    assert zones["Z5 max"]["duration_s"] == 300
    assert zones["Z2 aerobic"]["sessions"] == 0
