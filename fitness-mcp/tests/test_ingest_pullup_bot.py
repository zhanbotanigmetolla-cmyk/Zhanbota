"""Phase 1 adapter: mapping rules, idempotency, and read-only guarantees."""

import hashlib
import os
import sqlite3

import pytest

from fitness_mcp import config, db
from fitness_mcp.ingest.base import run_adapter
from fitness_mcp.ingest.pullup_bot import PullupBotAdapter

OWNER_TG = 111


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def ingest(conn, bot_path, tg_id=OWNER_TG):
    adapter = PullupBotAdapter(bot_db_path=bot_path, owner_tg_id=tg_id)
    return adapter, run_adapter(conn, adapter)


# ── mapping rules ───────────────────────────────────────────────────────────

def test_rest_rows_are_not_sessions(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=25, sets_json="[10, 8, 7]"),
        dict(date="2026-01-06", exercise="rest", completed=0, sets_json="[]"),
    ])
    _, res = ingest(fitness_db, path)
    assert res.created == 1
    assert [r["local_date"] for r in db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")] \
        == ["2026-01-05"]


def test_planned_but_not_performed_is_skipped_entirely(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", planned=70, completed=0, sets_json="[]"),
    ])
    _, res = ingest(fitness_db, path)
    assert res.created == 0
    assert db.list_workouts(fitness_db, "2026-01-01", "2026-12-31") == []


def test_session_total_without_a_breakdown_becomes_one_inferred_set(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=57, sets_json="[]"),
    ])
    ingest(fitness_db, path)
    w = db.get_workout(fitness_db, db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")[0]["id"])
    assert w["total_reps"] == 57              # volume preserved
    assert [s["inferred"] for s in w["sets"]] == [1]
    # ...and it must never surface as a record
    assert db.personal_records(fitness_db, "pullups")[0]["best_set_by_reps"] is None


def test_one_day_with_several_exercises_is_a_single_session(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=25, sets_json="[10, 8, 7]"),
        dict(date="2026-01-05", exercise="pushups", completed=40, sets_json="[20, 20]"),
    ])
    _, res = ingest(fitness_db, path)
    assert res.created == 1
    rows = db.list_workouts(fitness_db, "2026-01-01", "2026-12-31")
    assert len(rows) == 1
    assert rows[0]["total_reps"] == 65
    assert sorted(rows[0]["exercises"].split(",")) == ["pullups", "pushups"]


def test_rpe_zero_means_unrecorded_not_zero(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=10, sets_json="[10]", rpe=0),
        dict(date="2026-01-06", exercise="pullups", completed=10, sets_json="[10]", rpe=8),
    ])
    ingest(fitness_db, path)
    hist = db.exercise_history(fitness_db, "pullups")
    assert [h["rpe"] for h in hist] == [None, 8.0]


def test_other_users_are_never_ingested(fitness_db, bot_db_factory):
    path = bot_db_factory(
        [dict(date="2026-01-05", exercise="pullups", completed=25, sets_json="[25]")],
        extra_users=[(2, 999)],
    )
    # Someone else's row, inserted directly against the real bot schema.
    conn = sqlite3.connect(path)
    conn.execute("""INSERT INTO workouts (user_id, date, exercise, completed, sets_json)
                    VALUES (2, '2026-01-05', 'pullups', 500, '[500]')""")
    conn.commit()
    conn.close()

    ingest(fitness_db, path)
    assert fitness_db.execute("SELECT COALESCE(SUM(reps), 0) FROM sets").fetchone()[0] == 25


def test_started_at_is_local_midnight_expressed_in_utc(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=10, sets_json="[10]"),
    ])
    ingest(fitness_db, path)
    row = fitness_db.execute("SELECT started_at, local_date FROM workouts").fetchone()
    # Almaty is UTC+5, so local midnight is 19:00 the previous UTC day.
    assert row["started_at"] == "2026-01-04T19:00:00Z"
    assert row["local_date"] == "2026-01-05"


def test_source_id_is_stable_and_namespaced_by_telegram_id(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=10, sets_json="[10]"),
    ])
    ingest(fitness_db, path)
    row = fitness_db.execute("SELECT source, source_id FROM workouts").fetchone()
    assert row["source"] == "pullup_bot"
    assert row["source_id"] == f"{OWNER_TG}:2026-01-05"


def test_raw_payload_is_preserved_for_reparsing(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=25, sets_json="[10, 8, 7]",
             day_type="Тяжёлый", notes="10 км бега"),
    ])
    ingest(fitness_db, path)
    raw = fitness_db.execute("SELECT raw_json FROM workouts").fetchone()["raw_json"]
    assert "10 км бега" in raw and "Тяжёлый" in raw


# ── data quality ────────────────────────────────────────────────────────────

def test_disagreement_between_sets_and_total_is_reported_not_silently_resolved(
        fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-04-05", exercise="pullups", completed=40,
             sets_json="[10, 10, 10, 10, 10, 10, 10, 10]"),
    ])
    adapter, res = ingest(fitness_db, path)
    assert any("sets sum to 80" in w and "completed=40" in w for w in res.warnings)
    # the granular breakdown wins
    assert fitness_db.execute("SELECT SUM(reps) FROM sets").fetchone()[0] == 80


def test_unparseable_sets_json_falls_back_to_the_session_total(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=30, sets_json="{broken"),
    ])
    adapter, res = ingest(fitness_db, path)
    assert any("unparseable" in w for w in res.warnings)
    assert fitness_db.execute("SELECT SUM(reps) FROM sets").fetchone()[0] == 30
    assert fitness_db.execute("SELECT inferred FROM sets").fetchone()[0] == 1


def test_unexpected_sets_json_shape_falls_back(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=12,
             sets_json='[{"reps": 12}]'),
    ])
    _, res = ingest(fitness_db, path)
    assert any("unexpected" in w for w in res.warnings)
    assert fitness_db.execute("SELECT SUM(reps) FROM sets").fetchone()[0] == 12


# ── idempotency & safety ────────────────────────────────────────────────────

def test_reingest_updates_in_place_without_duplicating(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=25, sets_json="[10, 8, 7]"),
    ])
    _, first = ingest(fitness_db, path)
    _, second = ingest(fitness_db, path)
    _, third = ingest(fitness_db, path)
    assert (first.created, first.updated) == (1, 0)
    assert (second.created, second.updated) == (0, 1)
    assert (third.created, third.updated) == (0, 1)
    assert fitness_db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 1
    assert fitness_db.execute("SELECT COUNT(*) FROM sets").fetchone()[0] == 3


def test_removing_sets_upstream_leaves_no_orphans(fitness_db, bot_db_factory, tmp_path):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=25, sets_json="[10, 8, 7]"),
    ])
    ingest(fitness_db, path)
    # the day is edited upstream to two shorter sets
    conn = sqlite3.connect(path)
    conn.execute("UPDATE workouts SET sets_json = '[5, 5]', completed = 10")
    conn.commit()
    conn.close()
    ingest(fitness_db, path)
    assert fitness_db.execute("SELECT COUNT(*) FROM sets").fetchone()[0] == 2
    assert fitness_db.execute("SELECT SUM(reps) FROM sets").fetchone()[0] == 10


def test_bot_database_is_never_modified(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=25, sets_json="[10, 8, 7]"),
    ])
    before = sha(path)
    ingest(fitness_db, path)
    ingest(fitness_db, path)
    assert sha(path) == before


def test_adapter_connection_rejects_writes(bot_db_factory):
    path = bot_db_factory([])
    adapter = PullupBotAdapter(bot_db_path=path, owner_tg_id=OWNER_TG)
    conn = adapter._connect()
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE should_not_exist (x INTEGER)")
    finally:
        conn.close()


def test_missing_owner_fails_loudly_without_writing(fitness_db, bot_db_factory):
    path = bot_db_factory([
        dict(date="2026-01-05", exercise="pullups", completed=25, sets_json="[25]"),
    ])
    _, res = ingest(fitness_db, path, tg_id=424242)
    assert res.failed and "LookupError" in res.error
    assert fitness_db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 0


# ── fail-soft contract ──────────────────────────────────────────────────────

class _ExplodingAdapter:
    name = "exploding"

    def fetch(self):
        raise RuntimeError("upstream changed its API")


class _HalfBadAdapter:
    """Yields one valid row then garbage, to prove the write is atomic."""
    name = "half_bad"

    def fetch(self):
        return [
            db.WorkoutRow(source="half_bad", source_id="ok", started_at="2026-01-05T00:00:00Z",
                          local_date="2026-01-05",
                          sets=[db.SetRow(exercise="pullups", reps=10, set_index=0)]),
            "not a workout row",
        ]


def test_a_failing_adapter_never_raises_and_never_writes(fitness_db):
    res = run_adapter(fitness_db, _ExplodingAdapter())
    assert res.failed
    assert "upstream changed its API" in res.error
    assert fitness_db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 0


def test_a_partial_failure_rolls_back_the_whole_import(fitness_db):
    res = run_adapter(fitness_db, _HalfBadAdapter())
    assert res.failed
    assert res.created == 0
    assert fitness_db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0] == 0


def test_strava_adapter_refuses_to_run(fitness_db):
    from fitness_mcp.ingest.strava import StravaAdapter
    res = run_adapter(fitness_db, StravaAdapter())
    assert res.failed
    assert "NotImplementedError" in res.error
    assert "subscription" in res.error


# ── config ──────────────────────────────────────────────────────────────────

def test_owner_id_must_be_set_explicitly(monkeypatch):
    monkeypatch.delenv("FITNESS_MCP_OWNER_TG_ID", raising=False)
    with pytest.raises(RuntimeError, match="multiple users"):
        config.owner_tg_id()


def test_owner_id_must_be_numeric(monkeypatch):
    monkeypatch.setenv("FITNESS_MCP_OWNER_TG_ID", "@zhanbota")
    with pytest.raises(RuntimeError, match="must be an integer"):
        config.owner_tg_id()
