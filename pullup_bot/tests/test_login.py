"""Resuming a paused account through the bot's Join button."""
from datetime import timedelta

from pullup_bot import timeutils
from pullup_bot.db import get_user
from pullup_bot.handlers import start
from .conftest import insert_test_user
from .test_settings_hardening import FakeMessage, FakeState


async def test_resuming_on_the_day_of_a_workout_keeps_the_activity_cursor(test_db):
    """Join used to set last_workout to yesterday unconditionally, so a second session
    the same day extended the streak and paid the daily bonus again."""
    today = timeutils.today().isoformat()
    await insert_test_user(test_db, tg_id=1, is_logged_out=1, last_workout=today,
                           inactivity_warned="2026-01-01")
    await start.login_start(FakeMessage(1, "Войти"), FakeState())
    user = await get_user(1)
    assert (user["is_logged_out"], user["last_workout"], user["inactivity_warned"]) == (0, today, None)


async def test_resuming_after_a_long_pause_grants_a_fresh_inactivity_window(test_db):
    yesterday = (timeutils.today() - timedelta(days=1)).isoformat()
    await insert_test_user(test_db, tg_id=2, is_logged_out=1, last_workout="2026-01-01")
    await start.login_start(FakeMessage(2, "Войти"), FakeState())
    assert (await get_user(2))["last_workout"] == yesterday
