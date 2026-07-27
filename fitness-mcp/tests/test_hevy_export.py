"""Hevy CSV adapter: locale parsing, session reconstruction, idempotency."""

from __future__ import annotations

import pytest

from fitness_mcp import db
from fitness_mcp.ingest.base import run_adapter
from fitness_mcp.ingest.hevy_export import (
    HevyDateError,
    HevyExportAdapter,
    parse_hevy_datetime,
)

HEADER = (
    "title,start_time,end_time,description,exercise_title,superset_id,"
    "exercise_notes,set_index,set_type,weight_kg,reps,distance_km,"
    "duration_seconds,rpe\n"
)


def write_csv(tmp_path, body, name="hevy.csv"):
    path = tmp_path / name
    path.write_text(HEADER + body, encoding="utf-8")
    return str(path)


# One session: a treadmill warm-up, three squat sets (one of them a warm-up),
# then the treadmill again — which is what makes set_index collide in the file.
SESSION = """\
"Legs","26 апр. 2026, 19:20","26 апр. 2026, 20:53","felt good","Беговая дорожка",,"",0,"normal",,,0.8,300,
"Legs","26 апр. 2026, 19:20","26 апр. 2026, 20:53","felt good","Присед (Штанга)",,"",0,"warmup",20,10,,,
"Legs","26 апр. 2026, 19:20","26 апр. 2026, 20:53","felt good","Присед (Штанга)",,"",1,"normal",90,8,,,
"Legs","26 апр. 2026, 19:20","26 апр. 2026, 20:53","felt good","Присед (Штанга)",,"",2,"normal",100,5,,,
"Legs","26 апр. 2026, 19:20","26 апр. 2026, 20:53","felt good","Беговая дорожка",,"",0,"normal",,,1.2,600,
"""


def test_russian_dates_parse_in_local_time():
    dt = parse_hevy_datetime("26 апр. 2026, 19:20")
    assert (dt.year, dt.month, dt.day, dt.hour, dt.minute) == (2026, 4, 26, 19, 20)
    # Almaty is UTC+5 in 2026, so 19:20 local is 14:20 UTC.
    assert dt.utcoffset().total_seconds() == 5 * 3600


def test_genitive_and_abbreviated_month_forms_both_parse():
    assert parse_hevy_datetime("3 июля 2024, 08:05").month == 7
    assert parse_hevy_datetime("3 июн. 2024, 08:05").month == 6


def test_historic_dates_use_the_offset_in_force_then():
    """Almaty moved from UTC+6 to UTC+5 in 2024; old sessions must not shift."""
    assert parse_hevy_datetime("12 дек. 2022, 22:27").utcoffset().total_seconds() == 6 * 3600


def test_unparseable_date_raises():
    with pytest.raises(HevyDateError):
        parse_hevy_datetime("26 Foo. 2026, 19:20")


def test_flat_rows_become_one_session(tmp_path):
    rows = list(HevyExportAdapter(write_csv(tmp_path, SESSION)).fetch())
    assert len(rows) == 1, "five set-rows must reconstitute into one workout"

    w = rows[0]
    assert w.source == "hevy_export"
    assert w.local_date == "2026-04-26"
    assert w.started_at == "2026-04-26T14:20:00Z"
    assert w.sport_type == "strength"
    assert w.duration_s == 93 * 60          # 19:20 -> 20:53 elapsed
    assert w.distance_m == 2000.0           # 0.8 km + 1.2 km, stored in metres
    assert w.avg_hr is None and w.max_hr is None  # Hevy carries no HR at all


def test_repeated_exercise_gets_unique_set_indexes(tmp_path):
    """Hevy restarts set_index per occurrence; storage needs it unique."""
    w = next(iter(HevyExportAdapter(write_csv(tmp_path, SESSION)).fetch()))
    treadmill = [s for s in w.sets if s.exercise == "беговая дорожка"]
    assert [s.set_index for s in treadmill] == [0, 1]
    assert len({(s.exercise, s.set_index) for s in w.sets}) == len(w.sets)


def test_set_fields_normalize(tmp_path):
    w = next(iter(HevyExportAdapter(write_csv(tmp_path, SESSION)).fetch()))
    squats = [s for s in w.sets if s.exercise == "присед (штанга)"]
    assert [(s.weight_kg, s.reps) for s in squats] == [(20.0, 10), (90.0, 8), (100.0, 5)]
    assert [s.set_type for s in squats] == ["warmup", "normal", "normal"]
    assert all(not s.inferred for s in squats), "every Hevy set is individually logged"

    # Cardio machines have no reps and no load — absent, not zero.
    treadmill = next(s for s in w.sets if s.exercise == "беговая дорожка")
    assert treadmill.reps is None and treadmill.weight_kg is None


def test_reimport_of_an_overlapping_export_is_idempotent(tmp_path, fitness_db):
    """The weekly re-export must not duplicate sets or double-count volume."""
    first = run_adapter(fitness_db, HevyExportAdapter(write_csv(tmp_path, SESSION)))
    assert (first.created, first.updated) == (1, 0)

    def totals():
        return fitness_db.execute(
            "SELECT COUNT(*) AS workouts, "
            "(SELECT COUNT(*) FROM sets) AS sets, "
            "(SELECT COALESCE(SUM(reps), 0) FROM sets) AS reps FROM workouts"
        ).fetchone()

    before = tuple(totals())
    assert before == (1, 5, 23)

    # A newer export: same session again, plus one later session.
    newer = SESSION + (
        '"Push","28 апр. 2026, 18:00","28 апр. 2026, 19:00","","Жим лежа (Штанга)",'
        ',"",0,"normal",60,10,,,\n'
    )
    second = run_adapter(fitness_db, HevyExportAdapter(write_csv(tmp_path, newer, "hevy2.csv")))
    assert (second.created, second.updated) == (1, 1)
    assert tuple(totals()) == (2, 6, 33)


def test_removing_a_set_upstream_removes_it_here(tmp_path, fitness_db):
    """Sets are replaced per session, so an edit upstream cannot leave stale rows."""
    run_adapter(fitness_db, HevyExportAdapter(write_csv(tmp_path, SESSION)))
    trimmed = "\n".join(SESSION.splitlines()[:3]) + "\n"
    run_adapter(fitness_db, HevyExportAdapter(write_csv(tmp_path, trimmed, "hevy2.csv")))
    assert fitness_db.execute("SELECT COUNT(*) FROM sets").fetchone()[0] == 3


def test_warmup_sets_do_not_set_records(tmp_path, fitness_db):
    """A 10-rep ramp-up set must not become the best-by-reps record."""
    run_adapter(fitness_db, HevyExportAdapter(write_csv(tmp_path, SESSION)))
    (pr,) = [r for r in db.personal_records(fitness_db) if r["exercise"] == "присед (штанга)"]
    assert pr["best_set_by_reps"]["reps"] == 8, "the 10-rep warm-up is excluded"
    assert pr["best_set_by_weight"]["weight_kg"] == 100.0
    assert pr["estimated_1rm"]["est_1rm"] == pytest.approx(100 * (1 + 5 / 30))


def test_cardio_machines_are_not_listed_as_records(tmp_path, fitness_db):
    """An exercise with neither reps nor load has no records to report."""
    run_adapter(fitness_db, HevyExportAdapter(write_csv(tmp_path, SESSION)))
    assert not [r for r in db.personal_records(fitness_db) if r["exercise"] == "беговая дорожка"]


def test_source_filter_separates_the_two_modalities(tmp_path, fitness_db):
    from tests.conftest import add_workout

    run_adapter(fitness_db, HevyExportAdapter(write_csv(tmp_path, SESSION)))
    add_workout(
        fitness_db, source="pullup_bot", source_id="bw-1", local_date="2026-04-26",
        sets=[{"exercise": "pullups", "reps": 12, "set_index": 0}],
    )

    both = db.list_workouts(fitness_db, "2026-04-26", "2026-04-26")
    hevy = db.list_workouts(fitness_db, "2026-04-26", "2026-04-26", source="hevy_export")
    bot = db.list_workouts(fitness_db, "2026-04-26", "2026-04-26", source="pullup_bot")
    assert (len(both), len(hevy), len(bot)) == (2, 1, 1)
    assert hevy[0]["source"] == "hevy_export"

    # Bodyweight semantics survive the merge: pullups still has no load.
    (bw,) = db.personal_records(fitness_db, source="pullup_bot")
    assert bw["exercise"] == "pullups"
    assert bw["best_set_by_weight"] is None and bw["estimated_1rm"] is None

    summary = db.training_summary(fitness_db, "2026-04-26", "2026-04-26", "day")
    assert summary[0]["sessions"] == 2 and summary[0]["training_days"] == 1
    hevy_only = db.training_summary(fitness_db, "2026-04-26", "2026-04-26", "day",
                                    source="hevy_export")
    assert hevy_only[0]["total_reps"] == 23


def test_unknown_source_is_rejected_rather_than_returning_nothing(fitness_db):
    with pytest.raises(ValueError, match="unknown source"):
        db.list_workouts(fitness_db, "2026-01-01", "2026-12-31", source="hevy")


def test_a_session_with_sets_is_never_superseded_by_one_without(tmp_path, fitness_db):
    """A watch record of the same gym session must not hide the set list."""
    from tests.conftest import add_workout

    run_adapter(fitness_db, HevyExportAdapter(write_csv(tmp_path, SESSION)))
    add_workout(
        fitness_db, source="xiaomi_export", source_id="watch-1",
        local_date="2026-04-26", started_at="2026-04-26T14:21:00Z",
        duration_s=93 * 60, avg_hr=120, max_hr=160,
    )
    assert db.deduplicate(fitness_db) == []
    assert len(db.list_workouts(fitness_db, "2026-04-26", "2026-04-26")) == 2


def test_missing_columns_fail_loudly(tmp_path):
    path = tmp_path / "wrong.csv"
    path.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Hevy CSV export"):
        list(HevyExportAdapter(str(path)).fetch())
