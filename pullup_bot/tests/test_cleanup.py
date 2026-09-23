from datetime import timedelta

import pytest

from pullup_bot.services.scheduler import auto_cleanup_inactive
from pullup_bot import timeutils
from .conftest import insert_test_user


class FakeBot:
    """Collects messages instead of sending them."""

    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


def days_ago(n: int) -> str:
    return (timeutils.today() - timedelta(days=n)).isoformat()


async def _tg_ids(conn):
    async with conn.execute("SELECT tg_id FROM users ORDER BY tg_id") as cur:
        return [r[0] for r in await cur.fetchall()]


@pytest.mark.asyncio
async def test_never_trained_account_is_deleted_after_30_days(test_db):
    """A user who registered 40 days ago and never trained must not be exempt."""
    await insert_test_user(test_db, tg_id=1, joined=days_ago(40), last_workout=None)
    await auto_cleanup_inactive(FakeBot())
    assert await _tg_ids(test_db) == []


@pytest.mark.asyncio
async def test_never_trained_account_is_warned_before_deletion(test_db):
    """At 28 days since registration the user gets a warning, not a deletion."""
    await insert_test_user(test_db, tg_id=2, joined=days_ago(28), last_workout=None)
    bot = FakeBot()
    await auto_cleanup_inactive(bot)
    assert await _tg_ids(test_db) == [2]
    assert len(bot.sent) == 2  # the user, then the admin summary
    assert "зарегистрировался" in bot.sent[0][1]


@pytest.mark.asyncio
async def test_recent_signup_is_left_alone(test_db):
    """Someone who joined a week ago has not run out of time yet."""
    await insert_test_user(test_db, tg_id=3, joined=days_ago(7), last_workout=None)
    bot = FakeBot()
    await auto_cleanup_inactive(bot)
    assert await _tg_ids(test_db) == [3]
    assert bot.sent == []


@pytest.mark.asyncio
async def test_last_workout_still_wins_over_join_date(test_db):
    """An old account that trained yesterday stays; the join date must not delete it."""
    await insert_test_user(test_db, tg_id=4, joined=days_ago(200), last_workout=days_ago(1))
    await auto_cleanup_inactive(FakeBot())
    assert await _tg_ids(test_db) == [4]


@pytest.mark.asyncio
async def test_logged_out_never_trained_account_is_paused(test_db):
    """Logged-out accounts are paused on purpose and stay paused."""
    await insert_test_user(test_db, tg_id=5, joined=days_ago(90),
                           last_workout=None, is_logged_out=1)
    await auto_cleanup_inactive(FakeBot())
    assert await _tg_ids(test_db) == [5]


@pytest.mark.parametrize("last_workout", [None, days_ago(60)])
async def test_recorded_workout_protects_account_with_missing_or_stale_cursor(test_db, last_workout):
    await insert_test_user(test_db, tg_id=6, joined=days_ago(200), last_workout=last_workout)
    await test_db.execute(
        "INSERT INTO workouts (user_id,date,exercise,completed) "
        "SELECT id,?,'pullups',20 FROM users WHERE tg_id=6", (days_ago(1),))
    await test_db.commit()
    bot = FakeBot()
    await auto_cleanup_inactive(bot)
    assert await _tg_ids(test_db) == [6]
    assert bot.sent == []


async def test_recent_rest_marker_protects_account(test_db):
    await insert_test_user(test_db, tg_id=7, joined=days_ago(200), last_workout=None)
    await test_db.execute(
        "INSERT INTO workouts (user_id,date,exercise,planned,completed) "
        "SELECT id,?,'rest',0,0 FROM users WHERE tg_id=7", (days_ago(1),))
    await test_db.commit()
    await auto_cleanup_inactive(FakeBot())
    assert await _tg_ids(test_db) == [7]


async def test_empty_training_plan_does_not_count_as_completed_activity(test_db):
    await insert_test_user(test_db, tg_id=8, joined=days_ago(200), last_workout=None)
    await test_db.execute(
        "INSERT INTO workouts (user_id,date,exercise,planned,completed) "
        "SELECT id,?,'pullups',50,0 FROM users WHERE tg_id=8", (days_ago(1),))
    await test_db.commit()
    await auto_cleanup_inactive(FakeBot())
    assert await _tg_ids(test_db) == []


async def test_warning_uses_history_date_after_cursor_reset(test_db):
    await insert_test_user(test_db, tg_id=9, joined=days_ago(200), last_workout=None)
    await test_db.execute(
        "INSERT INTO workouts (user_id,date,exercise,completed) "
        "SELECT id,?,'pullups',20 FROM users WHERE tg_id=9", (days_ago(27),))
    await test_db.commit()
    bot = FakeBot()
    await auto_cleanup_inactive(bot)
    assert await _tg_ids(test_db) == [9]
    assert "27" in bot.sent[0][1]
    assert "Через 3" in bot.sent[0][1]
    assert "зарегистрировался" not in bot.sent[0][1]


async def test_cleanup_deletes_on_thirtieth_day(test_db):
    await insert_test_user(test_db, tg_id=10, joined=days_ago(30), last_workout=None)
    await auto_cleanup_inactive(FakeBot())
    assert await _tg_ids(test_db) == []
