import pytest

from pullup_bot.db import add_xp, get_lang, get_today_workout, get_user, update_streak, upsert_workout
from pullup_bot.tests.conftest import insert_test_user
from pullup_bot.db import add_welcome_greeting


# --- init_db / schema ---

@pytest.mark.asyncio
async def test_tables_exist(test_db):
    async with test_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ) as cur:
        tables = [r[0] for r in await cur.fetchall()]
    assert "users" in tables
    assert "workouts" in tables


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


# --- upsert_workout / get_today_workout ---

@pytest.mark.asyncio
async def test_upsert_and_get_workout(test_db):
    await insert_test_user(test_db)
    user = await get_user(12345)
    await upsert_workout(user["id"], "2026-03-26", planned=100, completed=80, day_type="Средний")
    w = await get_today_workout(user["id"], "2026-03-26")
    assert w is not None
    assert w["completed"] == 80
    assert w["planned"] == 100


@pytest.mark.asyncio
async def test_upsert_updates_existing(test_db):
    await insert_test_user(test_db)
    user = await get_user(12345)
    await upsert_workout(user["id"], "2026-03-26", planned=100, completed=50, day_type="Средний")
    await upsert_workout(user["id"], "2026-03-26", completed=90)
    w = await get_today_workout(user["id"], "2026-03-26")
    assert w["completed"] == 90


@pytest.mark.asyncio
async def test_get_today_workout_none(test_db):
    await insert_test_user(test_db)
    user = await get_user(12345)
    assert await get_today_workout(user["id"], "2026-01-01") is None


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
