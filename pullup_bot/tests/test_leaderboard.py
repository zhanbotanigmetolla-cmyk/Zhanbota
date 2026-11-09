from datetime import timedelta
from types import SimpleNamespace

from pullup_bot import timeutils
from pullup_bot.handlers import friends
from .conftest import insert_test_user


class FakeMessage:
    def __init__(self, tg_id):
        self.from_user = SimpleNamespace(id=tg_id)
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append(text)


async def _workout(conn, tg_id, day, reps):
    await conn.execute(
        "INSERT INTO workouts (user_id,date,exercise,planned,completed) "
        "SELECT id,?,'pullups',?,? FROM users WHERE tg_id=?", (day, reps, reps, tg_id))
    await conn.commit()


async def test_leaderboard_counts_the_current_calendar_week_and_active_accounts_only(test_db):
    today = timeutils.today()
    monday = today - timedelta(days=today.weekday())
    await insert_test_user(test_db, tg_id=1, first_name="Anna")
    await insert_test_user(test_db, tg_id=2, first_name="Boris")
    await insert_test_user(test_db, tg_id=3, first_name="Blocked", is_banned=1)
    await _workout(test_db, 1, today.isoformat(), 10)
    await _workout(test_db, 2, (monday - timedelta(days=1)).isoformat(), 100)  # last Sunday
    await _workout(test_db, 3, today.isoformat(), 500)
    message = FakeMessage(1)
    await friends.leaderboard(message)
    text = message.answers[-1]
    assert "Anna" in text and "10 XP" in text
    assert "Boris" not in text
    assert "Blocked" not in text
