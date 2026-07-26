"""Strava bulk-export adapter.

The fixtures use Russian headers and dates on purpose. The real archive is
localized, and a parser written against the documented English names imports
zero rows from it without erroring — the failure mode these tests exist to
prevent.
"""

import io
import zipfile

import pytest

from fitness_mcp import db
from fitness_mcp.ingest.base import run_adapter
from fitness_mcp.ingest.strava_export import StravaExportAdapter, parse_started_at

RU_HEADER = (
    "ID физической активности,Дата тренировки,Название тренировки,Тип активности,"
    "Общее время,Расстояние,Макс. пульс,Время в движении,Дистанция,"
    "Средний пульс,Калории,Набор высоты"
)
EN_HEADER = (
    "Activity ID,Activity Date,Activity Name,Activity Type,Elapsed Time,"
    "Max Heart Rate,Moving Time,Distance,Average Heart Rate,Calories,Elevation Gain"
)


def make_archive(tmp_path, header, rows, name="export.zip", extra=None):
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("activities.csv", "\n".join([header, *rows]))
        for fname, content in (extra or {}).items():
            z.writestr(fname, content)
    return str(path)


def ingest(conn, path):
    adapter = StravaExportAdapter(archive_path=path)
    return adapter, run_adapter(conn, adapter)


# ── date parsing ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    # narrow no-break space before 'г.', as the real export emits
    ("26 июл. 2026 г., 12:12:51", "2026-07-26T12:12:51Z"),
    ("26 июл. 2026 г., 12:12:51", "2026-07-26T12:12:51Z"),
    ("1 янв. 2026\xa0г., 00:00:00", "2026-01-01T00:00:00Z"),
    ("3 мая 2026 г., 06:05:04", "2026-05-03T06:05:04Z"),
    ("15 сент. 2025 г., 23:59:59", "2025-09-15T23:59:59Z"),
    ("Jul 26, 2026, 12:12:51 PM", "2026-07-26T12:12:51Z"),
    ("2026-07-26 12:12:51", "2026-07-26T12:12:51Z"),
])
def test_localized_dates_parse_to_utc(raw, expected):
    assert parse_started_at(raw).strftime("%Y-%m-%dT%H:%M:%SZ") == expected


def test_unparseable_date_says_what_to_do():
    with pytest.raises(ValueError, match="localized"):
        parse_started_at("someday in the future")


def test_unknown_month_is_named_in_the_error():
    with pytest.raises(ValueError, match="brumaire"):
        parse_started_at("12 brumaire 2026 г., 10:00:00")


# ── column mapping ──────────────────────────────────────────────────────────

def test_russian_export_imports(fitness_db, tmp_path):
    path = make_archive(tmp_path, RU_HEADER, [
        "19472991497,\"26 июл. 2026 г., 12:12:51\",Дневной велозаезд,Велосипед,"
        "1357.0,\"6,89\",162.0,1233.0,6890.0,137.0,198.0,4.1",
    ])
    _, res = ingest(fitness_db, path)
    assert res.created == 1 and not res.failed

    w = db.get_workout(fitness_db, db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")[0]["id"])
    assert w["sport_type"] == "cycling"
    assert w["duration_s"] == 1357          # elapsed, not the 1233 moving time
    assert w["distance_m"] == 6890.0        # metres column, not the "6,89" km one
    assert (w["avg_hr"], w["max_hr"], w["kcal"]) == (137, 162, 198)
    assert w["elevation_m"] == 4.1
    # 12:12 UTC is 17:12 in Almaty — same calendar day here
    assert w["local_date"] == "2026-07-26"


def test_english_export_imports_too(fitness_db, tmp_path):
    path = make_archive(tmp_path, EN_HEADER, [
        "123,\"Jul 26, 2026, 12:12:51 PM\",Morning Run,Run,1800,170,1700,5000.0,150,300,12.5",
    ])
    _, res = ingest(fitness_db, path)
    assert res.created == 1
    rows = db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")
    assert rows[0]["sport_type"] == "running"


def test_missing_required_column_fails_loudly_rather_than_importing_nothing(
        fitness_db, tmp_path):
    """The whole point: a silent zero-row import must be impossible."""
    path = make_archive(tmp_path, "foo,bar", ["1,2"])
    _, res = ingest(fitness_db, path)
    assert res.failed
    assert "missing required column" in res.error
    assert fitness_db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 0


def test_not_a_strava_archive_is_reported_clearly(fitness_db, tmp_path):
    path = tmp_path / "wrong.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("readme.txt", "not strava")
    _, res = ingest(fitness_db, str(path))
    assert res.failed and "activities.csv not found" in res.error


# ── value handling ──────────────────────────────────────────────────────────

def test_comma_decimals_and_blanks(fitness_db, tmp_path):
    path = make_archive(tmp_path, RU_HEADER, [
        # no HR, no calories, no elevation; distance uses a comma
        "1,\"5 мар. 2026 г., 07:00:00\",Пробежка,Бег,1800.0,\"3,50\",,1750.0,\"3500,5\",,,",
    ])
    ingest(fitness_db, path)
    w = db.get_workout(fitness_db, db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")[0]["id"])
    assert w["distance_m"] == 3500.5
    assert w["avg_hr"] is None and w["max_hr"] is None
    assert w["kcal"] is None and w["elevation_m"] is None


def test_utc_to_almaty_can_shift_the_calendar_day(fitness_db, tmp_path):
    """21:00 UTC is 02:00 the NEXT day in Almaty — local_date must follow."""
    path = make_archive(tmp_path, RU_HEADER, [
        "1,\"5 мар. 2026 г., 21:00:00\",Ночной заезд,Велосипед,600.0,\"1,0\",,600.0,1000.0,,,",
    ])
    ingest(fitness_db, path)
    row = fitness_db.execute("SELECT started_at, local_date FROM workouts").fetchone()
    assert row["started_at"] == "2026-03-05T21:00:00Z"
    assert row["local_date"] == "2026-03-06"


def test_unmapped_sport_type_is_kept_and_warned_about(fitness_db, tmp_path):
    path = make_archive(tmp_path, RU_HEADER, [
        "1,\"5 мар. 2026 г., 07:00:00\",Скалолазание,Альпинизм,600.0,\"0\",,600.0,0.0,,,",
    ])
    _, res = ingest(fitness_db, path)
    assert any("unmapped sport type" in w for w in res.warnings)
    assert db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")[0]["sport_type"] == "альпинизм"


def test_raw_payload_is_preserved(fitness_db, tmp_path):
    path = make_archive(tmp_path, RU_HEADER, [
        "1,\"5 мар. 2026 г., 07:00:00\",Утренняя пробежка,Бег,1800.0,\"3,5\",160.0,1750.0,3500.0,140.0,250.0,10.0",
    ])
    ingest(fitness_db, path)
    raw = fitness_db.execute("SELECT raw_json FROM workouts").fetchone()["raw_json"]
    assert "Утренняя пробежка" in raw
    assert "Время в движении" in raw          # moving time kept even though unused


def test_strength_activities_arrive_without_invented_sets(fitness_db, tmp_path):
    path = make_archive(tmp_path, RU_HEADER, [
        "1,\"5 мар. 2026 г., 07:00:00\",Силовая,Силовая тренировка,3600.0,\"0\",150.0,3600.0,0.0,120.0,400.0,0.0",
    ])
    ingest(fitness_db, path)
    w = db.get_workout(fitness_db, db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")[0]["id"])
    assert w["sport_type"] == "strength"
    assert w["sets"] == [] and w["total_reps"] == 0


# ── idempotency & privacy ───────────────────────────────────────────────────

def test_reimporting_the_same_archive_changes_nothing(fitness_db, tmp_path):
    path = make_archive(tmp_path, RU_HEADER, [
        "1,\"5 мар. 2026 г., 07:00:00\",Пробежка,Бег,1800.0,\"3,5\",160.0,1750.0,3500.0,140.0,250.0,10.0",
        "2,\"6 мар. 2026 г., 07:00:00\",Пробежка,Бег,1900.0,\"3,6\",161.0,1850.0,3600.0,141.0,260.0,11.0",
    ])
    _, first = ingest(fitness_db, path)
    _, second = ingest(fitness_db, path)
    assert (first.created, first.updated) == (2, 0)
    assert (second.created, second.updated) == (0, 2)
    assert fitness_db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 2


def test_duplicate_activity_id_within_one_csv_is_kept_once(fitness_db, tmp_path):
    path = make_archive(tmp_path, RU_HEADER, [
        "7,\"5 мар. 2026 г., 07:00:00\",A,Бег,1800.0,\"3,5\",,1750.0,3500.0,,,",
        "7,\"5 мар. 2026 г., 09:00:00\",B,Бег,1800.0,\"3,5\",,1750.0,3500.0,,,",
    ])
    _, res = ingest(fitness_db, path)
    assert res.created == 1
    assert any("appears twice" in w for w in res.warnings)


def test_only_activities_csv_is_read(fitness_db, tmp_path):
    """The archive carries logins, contacts and device ids. None may be touched."""
    path = make_archive(tmp_path, RU_HEADER, [
        "1,\"5 мар. 2026 г., 07:00:00\",Пробежка,Бег,1800.0,\"3,5\",,1750.0,3500.0,,,",
    ], extra={
        "logins.csv": "ip,date\n203.0.113.7,2026-01-01",
        "contacts.csv": "name,email\nSomeone,someone@example.com",
        "mobile_device_identifiers.csv": "device\nSECRET-DEVICE-ID",
    })
    ingest(fitness_db, path)
    dump = " ".join(
        str(r["raw_json"]) for r in fitness_db.execute("SELECT raw_json FROM workouts")
    )
    for leak in ("203.0.113.7", "someone@example.com", "SECRET-DEVICE-ID"):
        assert leak not in dump
