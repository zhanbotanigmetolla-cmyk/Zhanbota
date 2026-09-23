from datetime import timedelta
import time

import pytest
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.storage.base import StorageKey
from aiogram.methods import SendMessage

from pullup_bot import config, timeutils
from pullup_bot.services import scheduler
from pullup_bot.storage import SqliteStorage
from .conftest import insert_test_user
from .test_cleanup import FakeBot


async def test_watchdog_preserves_session_crossing_midnight(test_db, tmp_path, monkeypatch):
    await insert_test_user(test_db, tg_id=42)
    path = str(tmp_path / "fsm.db")
    monkeypatch.setattr(config, "FSM_DB_PATH", path)
    storage = SqliteStorage(path)
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    data = {"date": (timeutils.today() - timedelta(days=1)).isoformat(), "sets": [10, 8]}
    try:
        await storage.set_state(key, "Training:active")
        await storage.set_data(key, data)
        bot = FakeBot()
        await scheduler.watchdog_health_check(bot)
        assert await storage.get_state(key) == "Training:active"
        assert await storage.get_data(key) == data
        assert bot.sent == []
    finally:
        await storage.close()


@pytest.mark.parametrize("has_workout", [False, True])
async def test_blocked_user_cleanup_respects_recent_activity(test_db, has_workout, monkeypatch):
    current = timeutils.now()
    monkeypatch.setattr(timeutils, "now", lambda: current)
    joined_days = 200 if has_workout else 1
    await insert_test_user(
        test_db, tg_id=42, last_workout=None,
        joined=(timeutils.today() - timedelta(days=joined_days)).isoformat(),
        notify_time=timeutils.now().strftime("%H:%M"))
    if has_workout:
        await test_db.execute(
            "INSERT INTO workouts (user_id,date,exercise,completed) "
            "SELECT id,?,'pullups',20 FROM users WHERE tg_id=42",
            ((timeutils.today() - timedelta(days=1)).isoformat(),))
        await test_db.commit()

    class BlockedBot:
        async def send_message(self, chat_id, text, **kwargs):
            raise TelegramForbiddenError(method=SendMessage(chat_id=chat_id, text=text),
                                         message="Forbidden: bot was blocked by the user")

    await scheduler.daily_reminder(BlockedBot())
    async with test_db.execute("SELECT COUNT(*) FROM users WHERE tg_id=42") as cur:
        assert (await cur.fetchone())[0] == 1


async def test_watchdog_reminds_once_without_discarding_old_workout(test_db, tmp_path, monkeypatch):
    await insert_test_user(test_db, tg_id=42)
    path = str(tmp_path / "fsm.db")
    monkeypatch.setattr(config, "FSM_DB_PATH", path)
    storage = SqliteStorage(path)
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    data = {"date": (timeutils.today() - timedelta(days=2)).isoformat(), "sets": [10, 8]}
    try:
        await storage.set_state(key, "Training:rpe")
        await storage.set_data(key, data)
        conn = await storage._get_conn()
        await conn.execute("UPDATE fsm_states SET updated_at=?", (time.time() - 3 * 60 * 60,))
        await conn.commit()
        bot = FakeBot()
        await scheduler.watchdog_health_check(bot)
        await scheduler.watchdog_health_check(bot)
        assert await storage.get_state(key) == "Training:rpe"
        assert await storage.get_data(key) == data
        assert len(bot.sent) == 1
        assert bot.sent[0][0] == 42
        assert "/cancel" in bot.sent[0][1]
    finally:
        await storage.close()
