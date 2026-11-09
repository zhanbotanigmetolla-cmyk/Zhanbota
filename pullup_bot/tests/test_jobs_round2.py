"""Scheduled jobs: the daily report window, the XP-decay floor, the weekly crown
and rest-day acknowledgement after the 8 November 2026 audit."""
from datetime import timedelta

import pullup_bot.db as db_mod
from pullup_bot import timeutils
from pullup_bot.config import LEVEL_THRESHOLDS
from pullup_bot.db import get_user, upsert_workout
from pullup_bot.services import scheduler
from pullup_bot.services.xp import day_type_for
from .conftest import insert_test_user
from .test_cleanup import FakeBot


def days_ago(n):
    return (timeutils.today() - timedelta(days=n)).isoformat()


async def test_daily_report_counts_yesterdays_workouts(test_db):
    """The 08:00 report used to count 'today', i.e. only 00:00-08:00, so it said 0."""
    await insert_test_user(test_db, tg_id=1)
    await upsert_workout((await get_user(1))["id"], days_ago(1), "pullups", completed=20, planned=30)
    bot = FakeBot()
    await scheduler.daily_health_summary(bot)
    assert "Тренировались вчера: 1" in bot.sent[0][1]


async def test_decay_floor_is_pinned_to_the_rank_held_when_the_break_began(test_db):
    """Each lost rank used to lower the floor by another rank, so a long absence walked
    the user down to zero XP; one absence now costs at most one rank."""
    await insert_test_user(test_db, tg_id=43, xp=7600, level=7, last_workout=days_ago(30))
    bot = FakeBot()
    for _ in range(90):
        await scheduler.daily_xp_decay(bot)
    user = await get_user(43)
    assert (user["xp"], user["level"]) == (LEVEL_THRESHOLDS[6], 6)
    assert len([text for _, text in bot.sent if "ранг упал" in text]) == 1


async def test_decay_floor_resets_when_the_user_trains_again(test_db):
    await insert_test_user(test_db, tg_id=43, xp=7600, level=7, last_workout=days_ago(30))
    bot = FakeBot()
    await scheduler.daily_xp_decay(bot)
    assert (await get_user(43))["decay_floor_level"] == 7
    await test_db.execute("UPDATE users SET last_workout=? WHERE tg_id=43",
                          (timeutils.today().isoformat(),))
    await test_db.commit()
    await scheduler.daily_xp_decay(bot)
    assert (await get_user(43))["decay_floor_level"] is None


async def test_crown_expires_when_nobody_trained_last_week(test_db):
    await insert_test_user(test_db, tg_id=1, is_weekly_champ=1)
    await insert_test_user(test_db, tg_id=2)
    await scheduler.weekly_summary(FakeBot())
    async with test_db.execute("SELECT SUM(is_weekly_champ) FROM users") as cur:
        assert (await cur.fetchone())[0] == 0


async def test_rest_day_acknowledgement_survives_one_broken_profile(test_db, monkeypatch):
    rest_day = next(p for p in range(7)
                    if day_type_for({"program_day": p, "program_type": "standard"})[0] == "Отдых")
    for tg_id in (1, 2):
        await insert_test_user(test_db, tg_id=tg_id, last_workout=days_ago(1), program_day=rest_day)
    broken = (await get_user(1))["id"]
    real_rows = scheduler.get_day_rows

    async def flaky(user_id, d=None):
        if user_id == broken:
            raise RuntimeError("boom")
        return await real_rows(user_id, d)

    monkeypatch.setattr(scheduler, "get_day_rows", flaky)
    await scheduler.auto_acknowledge_rest_days(FakeBot())
    assert (await get_user(2))["last_workout"] == timeutils.today().isoformat()
    assert (await get_user(1))["last_workout"] == days_ago(1)
