import asyncio
from datetime import timedelta

import aiosqlite
import pytest
import pytest_asyncio

import pullup_bot.db as db_mod
from pullup_bot.db import (add_welcome_greeting, add_xp, clear_rest_row,
                           get_day_rows, get_lang, get_user, get_workout,
                           mark_rest_day, update_streak, upsert_workout)
from pullup_bot.tests.conftest import insert_test_user
from pullup_bot.timeutils import today


# --- init_db / schema ---

@pytest.mark.asyncio
async def test_tables_exist(test_db):
    async with test_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ) as cur:
        tables = [r[0] for r in await cur.fetchall()]
    assert "users" in tables
    assert "workouts" in tables


@pytest.mark.asyncio
async def test_workouts_has_exercise_column(test_db):
    async with test_db.execute("PRAGMA table_info(workouts)") as cur:
        cols = [r[1] for r in await cur.fetchall()]
    assert "exercise" in cols
    assert "extra_activity" not in cols
    assert "extra_minutes" not in cols


@pytest.mark.asyncio
async def test_users_have_multi_exercise_columns(test_db):
    async with test_db.execute("PRAGMA table_info(users)") as cur:
        cols = [r[1] for r in await cur.fetchall()]
    for col in ["base_pushups", "base_dips", "base_squats",
                "personal_record_pushups", "set_record_pushups",
                "personal_record_dips", "set_record_dips",
                "personal_record_squats", "set_record_squats"]:
        assert col in cols, col


# --- legacy migration ---

@pytest.mark.asyncio
async def test_legacy_workouts_migration():
    """A pre-multi-exercise DB gets rebuilt: rest rows → 'rest', workouts → 'pullups'."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE NOT NULL, username TEXT, first_name TEXT,
            joined TEXT DEFAULT (date('now')),
            base_pullups INTEGER DEFAULT 130, start_day INTEGER DEFAULT 22,
            level INTEGER DEFAULT 0, xp INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0, freeze_tokens INTEGER DEFAULT 3,
            last_workout TEXT, notify_time TEXT DEFAULT '09:00',
            lang TEXT DEFAULT 'ru', program_day INTEGER DEFAULT 0
        );
        CREATE TABLE workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, date TEXT NOT NULL,
            planned INTEGER DEFAULT 0, completed INTEGER DEFAULT 0,
            sets_json TEXT DEFAULT '[]', rpe INTEGER DEFAULT 0,
            day_type TEXT DEFAULT '', extra_activity TEXT DEFAULT '',
            extra_minutes INTEGER DEFAULT 0, notes TEXT DEFAULT '',
            UNIQUE(user_id, date)
        );
        CREATE TABLE streak_recoveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, date TEXT NOT NULL, reason TEXT
        );
        CREATE TABLE friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, friend_id INTEGER NOT NULL,
            UNIQUE(user_id, friend_id)
        );
        CREATE TABLE bug_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, username TEXT, text TEXT,
            created TEXT DEFAULT (datetime('now')), status TEXT DEFAULT 'new'
        );
        INSERT INTO users (tg_id, username, first_name) VALUES (1, 'u', 'U');
        INSERT INTO workouts (user_id, date, planned, completed, sets_json, day_type, notes)
            VALUES (1, '2026-06-01', 50, 48, '[12,12,12,12]', 'Средний', 'good day');
        INSERT INTO workouts (user_id, date, planned, completed, day_type)
            VALUES (1, '2026-06-02', 0, 0, 'Отдых');
    """)
    await conn.commit()
    old_conn = db_mod._conn
    db_mod._conn = conn
    try:
        await db_mod.init_db()
        async with conn.execute(
            "SELECT exercise, completed, notes FROM workouts WHERE date='2026-06-01'"
        ) as cur:
            row = await cur.fetchone()
        assert row["exercise"] == "pullups"
        assert row["completed"] == 48
        assert row["notes"] == "good day"
        async with conn.execute(
            "SELECT exercise FROM workouts WHERE date='2026-06-02'"
        ) as cur:
            rest = await cur.fetchone()
        assert rest["exercise"] == "rest"
        async with conn.execute("PRAGMA table_info(workouts)") as cur:
            cols = [r[1] for r in await cur.fetchall()]
        assert "extra_activity" not in cols
        # New uniqueness: same user+date, different exercise is allowed
        await upsert_workout(1, "2026-06-01", "pushups", planned=80, completed=60)
        rows = await get_day_rows(1, "2026-06-01")
        assert len(rows) == 2
    finally:
        db_mod._conn = old_conn
        await conn.close()


# --- get_user / get_lang ---

@pytest.mark.asyncio
async def test_get_user_not_found(test_db):
    assert await get_user(99999) is None


@pytest.mark.asyncio
async def test_get_user_found(test_db):
    await insert_test_user(test_db)
    user = await get_user(12345)
    assert user is not None
    assert user["first_name"] == "Test"
    assert user["base_pullups"] == 100


@pytest.mark.asyncio
async def test_get_lang(test_db):
    await insert_test_user(test_db, lang="en")
    assert await get_lang(12345) == "en"


@pytest.mark.asyncio
async def test_get_lang_default(test_db):
    assert await get_lang(99999) == "ru"


# --- upsert_workout / get_workout / get_day_rows ---

@pytest.mark.asyncio
async def test_upsert_and_get_workout(test_db):
    await insert_test_user(test_db)
    user = await get_user(12345)
    await upsert_workout(user["id"], "2026-03-26", "pullups",
                         planned=100, completed=80, day_type="Средний")
    w = await get_workout(user["id"], "2026-03-26", "pullups")
    assert w is not None
    assert w["completed"] == 80
    assert w["planned"] == 100


@pytest.mark.asyncio
async def test_upsert_updates_existing(test_db):
    await insert_test_user(test_db)
    user = await get_user(12345)
    await upsert_workout(user["id"], "2026-03-26", "pullups",
                         planned=100, completed=50, day_type="Средний")
    await upsert_workout(user["id"], "2026-03-26", "pullups", completed=90)
    w = await get_workout(user["id"], "2026-03-26", "pullups")
    assert w["completed"] == 90


@pytest.mark.asyncio
async def test_two_exercises_same_day(test_db):
    await insert_test_user(test_db)
    user = await get_user(12345)
    await upsert_workout(user["id"], "2026-03-26", "pullups", planned=50, completed=48)
    await upsert_workout(user["id"], "2026-03-26", "pushups", planned=80, completed=80)
    rows = await get_day_rows(user["id"], "2026-03-26")
    assert {r["exercise"] for r in rows} == {"pullups", "pushups"}
    pu = await get_workout(user["id"], "2026-03-26", "pushups")
    assert pu["completed"] == 80


@pytest.mark.asyncio
async def test_get_workout_none(test_db):
    await insert_test_user(test_db)
    user = await get_user(12345)
    assert await get_workout(user["id"], "2026-01-01", "pullups") is None


# --- rest day helpers ---

@pytest.mark.asyncio
async def test_mark_and_clear_rest_day(test_db):
    await insert_test_user(test_db)
    user = await get_user(12345)
    await mark_rest_day(user["id"], "2026-03-27")
    rows = await get_day_rows(user["id"], "2026-03-27")
    assert len(rows) == 1
    assert rows[0]["exercise"] == "rest"
    assert rows[0]["planned"] == 0
    # idempotent
    await mark_rest_day(user["id"], "2026-03-27")
    assert len(await get_day_rows(user["id"], "2026-03-27")) == 1
    await clear_rest_row(user["id"], "2026-03-27")
    assert await get_day_rows(user["id"], "2026-03-27") == []


# --- add_xp ---

@pytest.mark.asyncio
async def test_add_xp(test_db):
    await insert_test_user(test_db)
    await add_xp(12345, 100)
    user = await get_user(12345)
    assert user["xp"] == 100


@pytest.mark.asyncio
async def test_add_xp_level_up(test_db):
    await insert_test_user(test_db)
    await add_xp(12345, 500)
    user = await get_user(12345)
    assert user["level"] == 1


@pytest.mark.asyncio
async def test_add_xp_cumulative(test_db):
    await insert_test_user(test_db)
    await add_xp(12345, 100)
    await add_xp(12345, 200)
    user = await get_user(12345)
    assert user["xp"] == 300


# --- update_streak ---

@pytest.mark.asyncio
async def test_update_streak_first_workout(test_db):
    await insert_test_user(test_db)
    await update_streak(12345)
    user = await get_user(12345)
    assert user["streak"] >= 1


@pytest.mark.asyncio
async def test_streak_gap_bridged_by_rest_row(test_db):
    """A rest marker row on the gap day keeps the streak without spending tokens."""
    await insert_test_user(test_db)
    user = await get_user(12345)
    await update_streak(12345, "2026-03-25")
    await mark_rest_day(user["id"], "2026-03-26")
    await update_streak(12345, "2026-03-27")
    user = await get_user(12345)
    assert user["streak"] == 2
    assert user["freeze_tokens"] == 3  # untouched


# --- welcome greetings ---

@pytest.mark.asyncio
async def test_add_welcome_greeting_once(test_db):
    await insert_test_user(test_db, tg_id=11111, username="u1", first_name="User1")
    await insert_test_user(test_db, tg_id=22222, username="u2", first_name="User2")
    assert await add_welcome_greeting(11111, 22222) is True
    assert await add_welcome_greeting(11111, 22222) is False


@pytest.mark.asyncio
async def test_add_welcome_greeting_no_self(test_db):
    await insert_test_user(test_db, tg_id=11111, username="u1", first_name="User1")
    assert await add_welcome_greeting(11111, 11111) is False


@pytest.mark.asyncio
async def test_reset_streak_preserves_activity_and_account(test_db):
    from pullup_bot.services.scheduler import auto_cleanup_inactive

    class FakeBot:
        async def send_message(self, *args, **kwargs):
            pass

    yesterday = (today() - timedelta(days=1)).isoformat()
    joined = (today() - timedelta(days=100)).isoformat()
    await insert_test_user(test_db, joined=joined, last_workout=yesterday,
                           streak=20, xp=2500)
    user = await get_user(12345)
    await upsert_workout(user["id"], yesterday, "pullups", planned=100, completed=100)
    await db_mod.reset_streak(12345)
    user = await get_user(12345)
    assert user["streak"] == 0
    assert user["last_workout"] == yesterday
    await auto_cleanup_inactive(FakeBot())
    assert await get_user(12345) is not None
    assert (await get_workout(user["id"], yesterday, "pullups"))["completed"] == 100


@pytest.mark.asyncio
async def test_unban_clears_both_ban_sources(test_db):
    await insert_test_user(test_db)
    await db_mod.ban_user(12345)
    assert await db_mod.is_permanently_banned(12345)
    await db_mod.unban_user(12345)
    assert (await get_user(12345))["is_banned"] == 0
    assert not await db_mod.is_permanently_banned(12345)


@pytest.mark.asyncio
@pytest.mark.parametrize("old,expected", [("8:00", "08:00"), ("0:05", "00:05"),
                                        ("8:0", "08:00"), ("8: 0", "08:00"),
                                        ("+8:00", "08:00"),
                                        ("23:59", "23:59"), ("25:00", "25:00")])
async def test_startup_normalizes_existing_notification_times(test_db, old, expected):
    await insert_test_user(test_db, notify_time=old)
    await db_mod.init_db()
    assert (await get_user(12345))["notify_time"] == expected


@pytest.mark.asyncio
async def test_concurrent_xp_awards_preserve_total_and_rank(test_db):
    await insert_test_user(test_db, xp=450)
    await asyncio.gather(*(add_xp(12345, 13) for _ in range(50)))
    user = await get_user(12345)
    assert user["xp"] == 1100
    assert user["level"] == 2


@pytest.mark.asyncio
async def test_finishing_an_old_session_cannot_rewind_activity(test_db):
    d = today().isoformat()
    await insert_test_user(test_db, last_workout=d, streak=10, xp=100)
    await update_streak(12345, (today() - timedelta(days=1)).isoformat())
    user = await get_user(12345)
    assert (user["last_workout"], user["streak"], user["xp"]) == (d, 10, 100)


@pytest.mark.asyncio
async def test_decay_does_not_overwrite_a_concurrent_xp_award(test_db, monkeypatch):
    await insert_test_user(test_db, xp=1000, level=2)
    original_execute = test_db.execute

    def race_before_decay_update(sql, parameters=()):
        if sql.startswith("UPDATE users SET xp=?, level=?"):
            async def award_then_update():
                await original_execute("UPDATE users SET xp=xp+100 WHERE tg_id=12345")
                await test_db.commit()
                return await original_execute(sql, parameters)
            return award_then_update()
        return original_execute(sql, parameters)

    monkeypatch.setattr(test_db, "execute", race_before_decay_update)
    assert await db_mod.apply_xp_decay(12345, 7) is None
    user = await get_user(12345)
    assert (user["xp"], user["level"]) == (1100, 2)
