import asyncio
import json
import time

import aiosqlite
from aiogram.fsm.storage.base import StorageKey

from pullup_bot import storage as storage_module
from pullup_bot.storage import SqliteStorage


async def test_legacy_schema_migration_preserves_unfinished_training(tmp_path):
    path = str(tmp_path / "legacy.db")
    data = {"date": "2026-09-22", "sets": [10, 8]}
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE fsm_states(chat_id INTEGER,user_id INTEGER,state TEXT,data TEXT,"
            "PRIMARY KEY(chat_id,user_id))")
        await conn.execute("INSERT INTO fsm_states VALUES(42,42,?,?)",
                           ("Training:active", json.dumps(data)))
        await conn.commit()
    storage = SqliteStorage(path)
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    try:
        assert await storage.get_state(key) == "Training:active"
        assert await storage.get_data(key) == data
        assert await storage.get_inactive_states(time.time() - 7200) == []
    finally:
        await storage.close()


async def test_state_and_data_writes_restart_inactivity_period(tmp_path, monkeypatch):
    storage = SqliteStorage(str(tmp_path / "fsm.db"))
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    try:
        monkeypatch.setattr(storage_module.time, "time", lambda: 1000.0)
        await storage.set_state(key, "Training:active")
        rows = await storage.get_inactive_states(1000.0)
        assert len(rows) == 1
        await storage.mark_inactivity_notified(42, 42, rows[0]["updated_at"])
        assert await storage.get_inactive_states(1000.0) == []

        monkeypatch.setattr(storage_module.time, "time", lambda: 2000.0)
        await storage.set_data(key, {"sets": [10]})
        # An older watchdog snapshot must not mark the newer session as notified.
        await storage.mark_inactivity_notified(42, 42, 1000.0)
        assert await storage.get_inactive_states(1000.0) == []
        assert len(await storage.get_inactive_states(2000.0)) == 1

        monkeypatch.setattr(storage_module.time, "time", lambda: 3000.0)
        await storage.set_state(key, "Training:rpe")
        assert await storage.get_inactive_states(2000.0) == []
        assert len(await storage.get_inactive_states(3000.0)) == 1
    finally:
        await storage.close()


async def test_concurrent_first_requests_share_one_initialized_connection(tmp_path, monkeypatch):
    original_connect = aiosqlite.connect
    opened = []

    def record_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(storage_module.aiosqlite, "connect", record_connect)
    storage = SqliteStorage(str(tmp_path / "fsm.db"))
    keys = [StorageKey(bot_id=1, chat_id=uid, user_id=uid) for uid in range(10)]
    try:
        await asyncio.gather(*(storage.set_state(key, "Training:active") for key in keys))
        assert len(opened) == 1
        assert await asyncio.gather(*(storage.get_state(key) for key in keys)) == ["Training:active"] * 10
    finally:
        await storage.close()
