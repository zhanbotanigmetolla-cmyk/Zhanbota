"""Apple Health push ingest: parsing, idempotency, auth, and dedup."""

import json

import pytest

from fitness_mcp import db
from fitness_mcp.ingest.apple_health import ApplePayload, parse_timestamp

from .conftest import add_workout

# 2026-07-27 06:00:00 UTC == 11:00 Almaty
START = "2026-07-27T06:00:00Z"


def apply(conn, payload):
    p = ApplePayload(payload)
    workouts = list(p.workouts())
    metrics = list(p.daily_metrics())
    with conn:
        created = 0
        for w in workouts:
            _, c = db.upsert_workout(conn, w)
            created += c
        for m in metrics:
            db.upsert_daily_metric(conn, m)
    return p, workouts, metrics, created


def workout(**kw):
    return {"type": "Cycling", "start": START, "end": "2026-07-27T06:30:00Z", **kw}


# ── timestamps ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("2026-07-27T06:00:00Z", "2026-07-27T06:00:00Z"),
    ("2026-07-27T06:00:00+00:00", "2026-07-27T06:00:00Z"),
    ("2026-07-27T11:00:00+05:00", "2026-07-27T06:00:00Z"),
    (1785132000, "2026-07-27T06:00:00Z"),
    ("1785132000", "2026-07-27T06:00:00Z"),
    ("1785132000000", "2026-07-27T06:00:00Z"),          # milliseconds
    ("2026-07-27 11:00:00", "2026-07-27T06:00:00Z"),    # naive -> local (Almaty)
    ("27.07.2026 11:00:00", "2026-07-27T06:00:00Z"),    # Russian locale format
])
def test_shortcut_timestamp_shapes_all_parse(value, expected):
    assert parse_timestamp(value).strftime("%Y-%m-%dT%H:%M:%SZ") == expected


def test_unparseable_timestamp_is_rejected():
    with pytest.raises(ValueError, match="unrecognized"):
        parse_timestamp("сегодня утром")


# ── workout mapping ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("apple_name,expected", [
    ("Cycling", "cycling"), ("Outdoor Cycle", "cycling"), ("Велосипед", "cycling"),
    ("Running", "running"), ("Бег", "running"),
    ("Walking", "walking"), ("Ходьба", "walking"),
    ("Traditional Strength Training", "strength"), ("Силовая тренировка", "strength"),
    ("Pool Swim", "swimming"), ("Плавание", "swimming"),
    ("Table Tennis", "pingpong"), ("Настольный теннис", "pingpong"),
    ("Йога", "yoga"), ("High Intensity Interval Training", "hiit"),
    ("Other", "workout"), ("Другое", "workout"),
])
def test_apple_names_map_onto_existing_sport_types(fitness_db, apple_name, expected):
    _, w, _, _ = apply(fitness_db, {"workouts": [workout(type=apple_name)]})
    assert w[0].sport_type == expected


def test_cycling_does_not_split_across_two_names(fitness_db):
    """The whole point of the mapping: one sport, one label."""
    apply(fitness_db, {"workouts": [
        workout(type="Cycling", start="2026-07-27T06:00:00Z"),
        workout(type="Outdoor Cycle", start="2026-07-28T06:00:00Z"),
        workout(type="Велосипед", start="2026-07-29T06:00:00Z"),
    ]})
    types = {r["sport_type"] for r in db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")}
    assert types == {"cycling"}


def test_unknown_type_is_kept_and_warned(fitness_db):
    p, w, _, _ = apply(fitness_db, {"workouts": [workout(type="Curling")]})
    assert w[0].sport_type == "curling"
    assert any("unmapped" in x for x in p.warnings)


def test_duration_derived_from_start_and_end_when_absent(fitness_db):
    _, w, _, _ = apply(fitness_db, {"workouts": [workout()]})
    assert w[0].duration_s == 1800


def test_explicit_duration_wins_over_derived(fitness_db):
    _, w, _, _ = apply(fitness_db, {"workouts": [workout(duration_s=1500)]})
    assert w[0].duration_s == 1500


def test_metrics_and_localdate(fitness_db):
    _, w, _, _ = apply(fitness_db, {"workouts": [
        workout(distance_m="5230", kcal=305, avg_hr=142, max_hr=168)]})
    row = w[0]
    assert (row.distance_m, row.kcal, row.avg_hr, row.max_hr) == (5230.0, 305, 142, 168)
    assert row.local_date == "2026-07-27"        # 11:00 Almaty
    assert row.time_precision == "exact"


def test_decimal_comma_from_a_localized_shortcut(fitness_db):
    _, w, _, _ = apply(fitness_db, {"workouts": [workout(distance_m="5,23")]})
    assert w[0].distance_m == 5.23


# ── idempotency ─────────────────────────────────────────────────────────────

def test_rolling_window_resend_updates_rather_than_duplicates(fitness_db):
    payload = {"workouts": [workout(), workout(type="Running", start="2026-07-26T06:00:00Z")]}
    _, _, _, first = apply(fitness_db, payload)
    _, _, _, second = apply(fitness_db, payload)
    _, _, _, third = apply(fitness_db, payload)
    assert (first, second, third) == (2, 0, 0)
    assert fitness_db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 2


def test_revised_duration_does_not_create_a_second_row(fitness_db):
    """Apple revises durations after a sync; the key must survive that."""
    apply(fitness_db, {"workouts": [workout(duration_s=1800)]})
    apply(fitness_db, {"workouts": [workout(duration_s=1783)]})
    rows = db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")
    assert len(rows) == 1
    assert rows[0]["duration_s"] == 1783          # latest value wins


def test_source_id_is_start_plus_type(fitness_db):
    _, w, _, _ = apply(fitness_db, {"workouts": [workout()]})
    assert w[0].source_id == "1785132000:cycling"
    assert w[0].source == "apple_health"


def test_two_types_at_the_same_instant_are_distinct(fitness_db):
    apply(fitness_db, {"workouts": [workout(type="Cycling"), workout(type="Running")]})
    assert fitness_db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 2


def test_same_type_twice_at_one_instant_is_collapsed(fitness_db):
    p, _, _, _ = apply(fitness_db, {"workouts": [workout(), workout()]})
    assert fitness_db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 1
    assert any("share start" in x for x in p.warnings)


# ── sleep and wellness ──────────────────────────────────────────────────────

def sleep(start, end, value):
    return {"start": start, "end": end, "value": value}


def test_sleep_stages_sum_and_attribute_to_the_wake_day(fitness_db):
    _, _, m, _ = apply(fitness_db, {"sleep_samples": [
        sleep("2026-07-26T20:00:00Z", "2026-07-26T22:00:00Z", "AsleepCore"),   # 120
        sleep("2026-07-26T22:00:00Z", "2026-07-26T23:00:00Z", "AsleepDeep"),   # 60
        sleep("2026-07-26T23:00:00Z", "2026-07-27T00:00:00Z", "AsleepREM"),    # 60
    ]})
    assert len(m) == 1
    # all three end on 2026-07-27 in Almaty (UTC+5)
    assert m[0].local_date == "2026-07-27"
    assert m[0].sleep_minutes == 240
    assert m[0].sleep_stages == {"light": 120, "deep": 60, "rem": 60}


def test_in_bed_and_awake_are_not_counted_as_sleep(fitness_db):
    _, _, m, _ = apply(fitness_db, {"sleep_samples": [
        sleep("2026-07-26T20:00:00Z", "2026-07-26T21:00:00Z", "InBed"),
        sleep("2026-07-26T21:00:00Z", "2026-07-26T22:00:00Z", "Awake"),
        sleep("2026-07-26T22:00:00Z", "2026-07-26T23:00:00Z", "AsleepCore"),
    ]})
    assert m[0].sleep_minutes == 60


def test_russian_sleep_values_work_too(fitness_db):
    _, _, m, _ = apply(fitness_db, {"sleep_samples": [
        sleep("2026-07-26T20:00:00Z", "2026-07-26T21:00:00Z", "В постели"),
        sleep("2026-07-26T21:00:00Z", "2026-07-26T22:00:00Z", "Глубокий сон"),
    ]})
    assert m[0].sleep_minutes == 60
    assert m[0].sleep_stages == {"deep": 60}


def test_unknown_sleep_stage_still_counts_as_sleep(fitness_db):
    _, _, m, _ = apply(fitness_db, {"sleep_samples": [
        sleep("2026-07-26T21:00:00Z", "2026-07-26T22:00:00Z", "AsleepSomethingNew"),
    ]})
    assert m[0].sleep_minutes == 60
    assert m[0].sleep_stages == {"unspecified": 60}


def test_resting_hr_and_steps(fitness_db):
    _, _, m, _ = apply(fitness_db, {
        "resting_hr": [{"date": "2026-07-27", "bpm": 48}],
        "steps": [{"date": "2026-07-27", "steps": 11402}],
    })
    assert (m[0].resting_hr, m[0].steps) == (48, 11402)
    assert m[0].stress is None            # Apple has no stress equivalent


def test_daily_metrics_reingest_is_idempotent(fitness_db):
    payload = {"resting_hr": [{"date": "2026-07-27", "bpm": 48}]}
    apply(fitness_db, payload)
    apply(fitness_db, payload)
    assert fitness_db.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0] == 1


def test_recovery_metrics_sees_pushed_data(fitness_db):
    apply(fitness_db, {"resting_hr": [{"date": f"2026-07-{d}", "bpm": bpm}
                                      for d, bpm in [("20", 52), ("21", 51),
                                                     ("22", 47), ("23", 46)]]})
    r = db.recovery_metrics(fitness_db, "2026-07-01", "2026-07-31")
    assert r["resting_hr"]["days_with_data"] == 4
    assert r["trend"]["direction"] == "improving"


# ── robustness ──────────────────────────────────────────────────────────────

def test_empty_payload_is_accepted(fitness_db):
    _, w, m, _ = apply(fitness_db, {})
    assert w == [] and m == []


def test_non_object_payload_rejected():
    with pytest.raises(ValueError, match="JSON object"):
        ApplePayload([1, 2, 3])


def test_one_bad_entry_does_not_lose_the_good_ones(fitness_db):
    p, w, _, _ = apply(fitness_db, {"workouts": [
        workout(),
        {"type": "Running", "start": "not a date"},
        workout(type="Running", start="2026-07-28T06:00:00Z"),
    ]})
    assert len(w) == 2
    assert any("skipped" in x for x in p.warnings)


def test_implausible_sleep_sample_is_dropped(fitness_db):
    p, _, m, _ = apply(fitness_db, {"sleep_samples": [
        sleep("2026-07-01T00:00:00Z", "2026-07-05T00:00:00Z", "AsleepCore"),
    ]})
    assert m == []
    assert any("implausible" in x for x in p.warnings)


# ── dedup against Xiaomi ────────────────────────────────────────────────────

def test_overlapping_xiaomi_record_wins(fitness_db):
    """Rare, but the watch record is richer where both exist."""
    apply(fitness_db, {"workouts": [workout(type="Running", duration_s=1800)]})
    add_workout(fitness_db, source="xiaomi_export", source_id="x1", local_date="2026-07-27",
                started_at="2026-07-27T06:00:30Z", sport_type="running",
                duration_s=1790, avg_hr=150, max_hr=170, kcal=300)

    merged = db.deduplicate(fitness_db)
    assert len(merged) == 1
    assert merged[0]["keep_source"] == "xiaomi_export"
    assert merged[0]["supersede_source"] == "apple_health"
    rows = db.list_workouts(fitness_db, "2026-07-27", "2026-07-27")
    assert [r["source"] for r in rows] == ["xiaomi_export"]


def test_apple_beats_strava(fitness_db):
    apply(fitness_db, {"workouts": [workout(type="Running", duration_s=1800)]})
    add_workout(fitness_db, source="strava_export", source_id="s1", local_date="2026-07-27",
                started_at="2026-07-27T06:00:10Z", sport_type="running", duration_s=1800)
    merged = db.deduplicate(fitness_db)
    assert merged[0]["keep_source"] == "apple_health"


def test_no_xiaomi_overlap_leaves_apple_alone(fitness_db):
    apply(fitness_db, {"workouts": [workout()]})
    assert db.deduplicate(fitness_db) == []
    assert len(db.list_workouts(fitness_db, "2026-07-27", "2026-07-27")) == 1
