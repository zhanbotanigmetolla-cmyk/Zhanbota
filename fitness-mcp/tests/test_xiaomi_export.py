"""Mi Fitness export adapter, and the source-priority rule dedup now uses.

Fixtures mirror the real archive's quirks: the sport name lives in the CSV's
`Key` column while the JSON carries an opaque integer `sport_type`, durations
are active rather than elapsed, and sleep figures are minutes.
"""

import csv
import json
import os

import pytest

from fitness_mcp import db
from fitness_mcp.ingest.base import run_adapter
from fitness_mcp.ingest.xiaomi_export import XiaomiExportAdapter

from .conftest import add_workout

PREFIX = "20260726_1889373230_MiFitness_"

# 2026-07-26 12:00:00 UTC == 17:00 Almaty (UTC+5)
T = 1785067200


def write_export(tmp_path, *, sport_rows=(), fitness_rows=(), aggregated_rows=()):
    d = tmp_path / "xiaomi"
    d.mkdir(exist_ok=True)

    def dump(name, header, rows):
        with open(d / f"{PREFIX}{name}", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    dump("hlth_center_sport_record.csv",
         ["Uid", "Sid", "Key", "Time", "Category", "Value", "UpdateTime"], sport_rows)
    dump("hlth_center_fitness_data.csv",
         ["Uid", "Sid", "Key", "Time", "Value", "UpdateTime"], fitness_rows)
    dump("hlth_center_aggregated_fitness_data.csv",
         ["Uid", "Sid", "Tag", "Key", "Time", "Value", "UpdateTime"], aggregated_rows)
    return str(d)


def sport(key, start, category=None, **extra):
    v = {"start_time": start, "end_time": start + 1800, "duration": 1800,
         "sport_type": 8, "calories": 200, **extra}
    return ["1", "2", key, str(start), category or key, json.dumps(v), str(start)]


def ingest(conn, path):
    a = XiaomiExportAdapter(export_dir=path)
    return a, run_adapter(conn, a)


# ── workouts ────────────────────────────────────────────────────────────────

def test_sport_type_comes_from_the_csv_key_not_the_json_integer(fitness_db, tmp_path):
    """The JSON's sport_type is an opaque int; the readable name is in Key."""
    p = write_export(tmp_path, sport_rows=[
        sport("outdoor_running", T),
        sport("strength_training", T + 7200),
        sport("high_bar", T + 14400),
        sport("indoor_riding", T + 21600),
    ])
    _, res = ingest(fitness_db, p)
    assert res.created == 4
    got = {r["local_date"] + ":" + r["sport_type"]
           for r in db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")}
    assert {g.split(":")[1] for g in got} == {"running", "strength", "high_bar", "cycling"}


def test_high_bar_keeps_its_own_type(fitness_db, tmp_path):
    """Pull-up bar work is distinct from generic strength training."""
    p = write_export(tmp_path, sport_rows=[sport("high_bar", T)])
    ingest(fitness_db, p)
    assert db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")[0]["sport_type"] == "high_bar"


def test_epoch_converts_to_utc_and_almaty_local_date(fitness_db, tmp_path):
    p = write_export(tmp_path, sport_rows=[sport("outdoor_running", T)])
    ingest(fitness_db, p)
    row = fitness_db.execute("SELECT started_at, local_date, time_precision FROM workouts").fetchone()
    assert row["started_at"] == "2026-07-26T12:00:00Z"
    assert row["local_date"] == "2026-07-26"          # 17:00 Almaty, same day
    assert row["time_precision"] == "exact"


def test_late_utc_evening_rolls_into_the_next_almaty_day(fitness_db, tmp_path):
    # 2026-07-26 20:00 UTC == 2026-07-27 01:00 Almaty
    p = write_export(tmp_path, sport_rows=[sport("outdoor_running", T + 8 * 3600)])
    ingest(fitness_db, p)
    row = fitness_db.execute("SELECT started_at, local_date FROM workouts").fetchone()
    assert row["started_at"] == "2026-07-26T20:00:00Z"
    assert row["local_date"] == "2026-07-27"


def test_metrics_are_mapped_including_rise_height_as_elevation(fitness_db, tmp_path):
    p = write_export(tmp_path, sport_rows=[
        sport("outdoor_running", T, distance=5000, avg_hrm=150, max_hrm=178,
              calories=320, rise_height=42.5),
    ])
    ingest(fitness_db, p)
    w = db.get_workout(fitness_db, db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")[0]["id"])
    assert (w["distance_m"], w["avg_hr"], w["max_hr"], w["kcal"]) == (5000, 150, 178, 320)
    assert w["elevation_m"] == 42.5


def test_duration_uses_the_reported_active_time_not_elapsed(fitness_db, tmp_path):
    """Xiaomi excludes paused time, so duration != end - start on many records."""
    p = write_export(tmp_path, sport_rows=[
        sport("strength_training", T, end_time=T + 5958, duration=5877),
    ])
    _, res = ingest(fitness_db, p)
    assert not res.failed
    assert db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")[0]["duration_s"] == 5877


def test_json_and_csv_start_disagreement_is_warned_about(fitness_db, tmp_path):
    row = sport("outdoor_running", T)
    row[3] = str(T - 1)                       # CSV Time one second behind the JSON
    p = write_export(tmp_path, sport_rows=[row])
    _, res = ingest(fitness_db, p)
    assert any("!= CSV Time" in w for w in res.warnings)
    assert fitness_db.execute("SELECT source_id FROM workouts").fetchone()["source_id"] == str(T)


def test_unmapped_sport_is_kept_and_warned(fitness_db, tmp_path):
    p = write_export(tmp_path, sport_rows=[sport("wingsuit_flying", T)])
    _, res = ingest(fitness_db, p)
    assert any("unmapped sport type" in w for w in res.warnings)
    assert db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")[0]["sport_type"] == "wingsuit_flying"


def test_bad_json_is_skipped_not_fatal(fitness_db, tmp_path):
    good = sport("outdoor_running", T)
    bad = ["1", "2", "outdoor_running", str(T + 100), "running", "{not json", "0"]
    p = write_export(tmp_path, sport_rows=[good, bad])
    _, res = ingest(fitness_db, p)
    assert res.created == 1
    assert any("bad JSON" in w for w in res.warnings)


def test_missing_directory_fails_loudly(fitness_db, tmp_path):
    _, res = ingest(fitness_db, str(tmp_path / "nope"))
    assert res.failed and "sport_record" in res.error


# ── daily metrics ───────────────────────────────────────────────────────────

def fitness_row(key, time, value):
    return ["1", "2", key, str(time), json.dumps(value), str(time)]


def test_daily_metrics_from_sleep_resting_hr_stress_and_steps(fitness_db, tmp_path):
    wake = T                                   # 2026-07-26 17:00 Almaty
    p = write_export(
        tmp_path,
        fitness_rows=[
            fitness_row("sleep", wake, {"wake_up_time": wake, "bedtime": wake - 36000,
                                        "duration": 604, "sleep_deep_duration": 181,
                                        "sleep_light_duration": 296, "sleep_rem_duration": 127,
                                        "sleep_awake_duration": 17}),
            fitness_row("resting_heart_rate", T, {"bpm": 46, "date_time": T}),
            fitness_row("stress", T, {"stress": 30, "time": T}),
            fitness_row("stress", T + 60, {"stress": 40, "time": T + 60}),
            # must be ignored: half a million of these exist in the real file
            fitness_row("heart_rate", T, {"bpm": 75, "time": T}),
        ],
        aggregated_rows=[
            ["1", "2", "daily_report", "steps", str(T), json.dumps({"steps": 11461}), "0"],
            ["1", "2", "daily_mark", "steps", str(T), json.dumps({"has_data": True}), "0"],
        ],
    )
    _, res = ingest(fitness_db, p)
    assert res.daily_metrics == 1

    m = fitness_db.execute("SELECT * FROM daily_metrics").fetchone()
    assert m["local_date"] == "2026-07-26"
    assert m["sleep_minutes"] == 604
    assert m["resting_hr"] == 46
    assert m["stress"] == 35                   # mean of 30 and 40
    assert m["steps"] == 11461                 # daily_report, not daily_mark
    assert json.loads(m["sleep_stages_json"]) == {
        "deep": 181, "light": 296, "rem": 127, "awake": 17, "segments": 1}


def test_sleep_is_attributed_to_the_day_you_woke_up(fitness_db, tmp_path):
    # bed 2026-07-25 23:00 Almaty, wake 2026-07-26 07:00 Almaty
    wake = 1785038400                          # 2026-07-26 02:00 UTC = 07:00 Almaty
    p = write_export(tmp_path, fitness_rows=[
        fitness_row("sleep", wake, {"wake_up_time": wake, "duration": 480,
                                    "sleep_deep_duration": 120, "sleep_light_duration": 240,
                                    "sleep_rem_duration": 120}),
    ])
    ingest(fitness_db, p)
    assert fitness_db.execute("SELECT local_date FROM daily_metrics").fetchone()[0] == "2026-07-26"


def test_multiple_sleep_segments_in_a_day_are_summed(fitness_db, tmp_path):
    p = write_export(tmp_path, fitness_rows=[
        fitness_row("sleep", T, {"wake_up_time": T, "duration": 400,
                                 "sleep_deep_duration": 100, "sleep_light_duration": 200,
                                 "sleep_rem_duration": 100}),
        fitness_row("sleep", T + 3600, {"wake_up_time": T + 3600, "duration": 60,
                                        "sleep_deep_duration": 10, "sleep_light_duration": 40,
                                        "sleep_rem_duration": 10}),
    ])
    ingest(fitness_db, p)
    m = fitness_db.execute("SELECT sleep_minutes, sleep_stages_json FROM daily_metrics").fetchone()
    assert m["sleep_minutes"] == 460
    assert json.loads(m["sleep_stages_json"])["segments"] == 2


def test_recovery_metrics_reads_the_imported_days(fitness_db, tmp_path):
    rows = []
    for i, (rhr, mins) in enumerate([(60, 400), (58, 410), (52, 470), (50, 480)]):
        t = T + i * 86400
        rows.append(fitness_row("resting_heart_rate", t, {"bpm": rhr, "date_time": t}))
        rows.append(fitness_row("sleep", t, {"wake_up_time": t, "duration": mins,
                                             "sleep_deep_duration": 1, "sleep_light_duration": 1,
                                             "sleep_rem_duration": 1}))
    ingest(fitness_db, write_export(tmp_path, fitness_rows=rows))
    r = db.recovery_metrics(fitness_db, "2026-07-01", "2026-08-31")
    assert len(r["days"]) == 4
    assert r["resting_hr"]["avg"] == 55.0      # (60+58+52+50)/4
    assert r["trend"]["direction"] == "improving"


def test_reimport_is_idempotent(fitness_db, tmp_path):
    p = write_export(tmp_path,
                     sport_rows=[sport("outdoor_running", T)],
                     fitness_rows=[fitness_row("resting_heart_rate", T, {"bpm": 46, "date_time": T})])
    _, first = ingest(fitness_db, p)
    _, second = ingest(fitness_db, p)
    assert (first.created, second.created, second.updated) == (1, 0, 1)
    assert fitness_db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 1
    assert fitness_db.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0] == 1


# ── source priority in dedup ────────────────────────────────────────────────

def test_xiaomi_wins_over_strava_even_when_strava_has_more_fields(fitness_db):
    """Explicit preference, not a field count: the watch is the better record."""
    add_workout(fitness_db, source="strava_export", source_id="s1", local_date="2026-05-01",
                started_at="2026-05-01T06:00:00Z", sport_type="running", duration_s=1800,
                distance_m=5000.0, avg_hr=150, max_hr=170, kcal=300, elevation_m=20.0)
    add_workout(fitness_db, source="xiaomi_export", source_id="x1", local_date="2026-05-01",
                started_at="2026-05-01T06:00:01Z", sport_type="running", duration_s=1800)

    merged = db.deduplicate(fitness_db)
    assert len(merged) == 1
    assert merged[0]["keep_source"] == "xiaomi_export"
    rows = db.list_workouts(fitness_db, "2026-05-01", "2026-05-01")
    assert [r["source"] for r in rows] == ["xiaomi_export"]


def test_active_vs_elapsed_duration_still_matches(fitness_db):
    """Xiaomi reports active time, Strava elapsed; a paused session must merge."""
    add_workout(fitness_db, source="strava_export", source_id="s1", local_date="2026-05-01",
                started_at="2026-05-01T06:00:00Z", duration_s=5958)
    add_workout(fitness_db, source="xiaomi_export", source_id="x1", local_date="2026-05-01",
                started_at="2026-05-01T06:00:00Z", duration_s=5877)
    assert len(db.deduplicate(fitness_db)) == 1


def test_wildly_different_durations_still_do_not_merge(fitness_db):
    add_workout(fitness_db, source="strava_export", source_id="s1", local_date="2026-05-01",
                started_at="2026-05-01T06:00:00Z", duration_s=600)
    add_workout(fitness_db, source="xiaomi_export", source_id="x1", local_date="2026-05-01",
                started_at="2026-05-01T06:00:00Z", duration_s=7200)
    assert db.deduplicate(fitness_db) == []


def test_bot_sessions_are_never_absorbed_by_xiaomi(fitness_db):
    """Bot rows are date_only and hold reps nothing else has."""
    add_workout(fitness_db, source="pullup_bot", source_id="p1", local_date="2026-05-01",
                time_precision="date_only",
                sets=[dict(exercise="pullups", reps=12, set_index=0)])
    add_workout(fitness_db, source="xiaomi_export", source_id="x1", local_date="2026-05-01",
                started_at="2026-05-01T00:00:00Z", sport_type="high_bar", duration_s=1800)
    assert db.deduplicate(fitness_db) == []
    assert len(db.list_workouts(fitness_db, "2026-05-01", "2026-05-01")) == 2
