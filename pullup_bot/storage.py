import json
from typing import Any, Dict, Optional

import aiosqlite
from aiogram.fsm.storage.base import BaseStorage, StorageKey


class SqliteStorage(BaseStorage):
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self._db_path)
            await self._conn.execute(
                "CREATE TABLE IF NOT EXISTS fsm_states ("
                "chat_id INTEGER, user_id INTEGER, "
                "state TEXT, data TEXT DEFAULT '{}', "
                "PRIMARY KEY (chat_id, user_id))"
            )
            # Add destiny column if missing (single-bot deployment: always "")
            try:
                await self._conn.execute(
                    "ALTER TABLE fsm_states ADD COLUMN destiny TEXT DEFAULT ''"
                )
            except Exception:
                pass  # Column already exists
            await self._conn.commit()
        return self._conn

    async def set_state(self, key: StorageKey, state=None) -> None:
        conn = await self._get_conn()
        state_val = None if state is None else state.state if hasattr(state, 'state') else str(state)
        await conn.execute(
            "INSERT INTO fsm_states (chat_id, user_id, state) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET state=excluded.state",
            (key.chat_id, key.user_id, state_val),
        )
        await conn.commit()

    async def get_state(self, key: StorageKey) -> Optional[str]:
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT state FROM fsm_states WHERE chat_id=? AND user_id=?",
            (key.chat_id, key.user_id),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        conn = await self._get_conn()
        await conn.execute(
            "INSERT INTO fsm_states (chat_id, user_id, data) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET data=excluded.data",
            (key.chat_id, key.user_id, json.dumps(data, default=str)),
        )
        await conn.commit()

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT data FROM fsm_states WHERE chat_id=? AND user_id=?",
            (key.chat_id, key.user_id),
        ) as cur:
            row = await cur.fetchone()
            return json.loads(row[0]) if row and row[0] else {}

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
