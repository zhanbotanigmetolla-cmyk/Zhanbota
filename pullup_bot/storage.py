import asyncio
import json
import time
from typing import Any, Dict, Optional

import aiosqlite
from aiogram.fsm.storage.base import BaseStorage, StorageKey


class SqliteStorage(BaseStorage):
    """aiogram FSM storage backend that persists state and data in a SQLite database."""

    def __init__(self, db_path: str):
        """Initialize with the path to the SQLite FSM database file."""
        self._db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._init_lock = asyncio.Lock()

    async def _get_conn(self) -> aiosqlite.Connection:
        """Return the lazily-opened SQLite connection, creating the fsm_states table if needed."""
        async with self._init_lock:
            if self._conn is None:
                conn = await aiosqlite.connect(self._db_path)
                conn.row_factory = aiosqlite.Row
                try:
                    await conn.execute(
                        "CREATE TABLE IF NOT EXISTS fsm_states ("
                        "chat_id INTEGER, user_id INTEGER, "
                        "state TEXT, data TEXT DEFAULT '{}', "
                        "destiny TEXT DEFAULT '', updated_at REAL NOT NULL DEFAULT 0, "
                        "stale_notified_at REAL, PRIMARY KEY (chat_id, user_id))"
                    )
                    async with conn.execute("PRAGMA table_info(fsm_states)") as cur:
                        columns = {row[1] for row in await cur.fetchall()}
                    for name, definition in (
                        ("destiny", "TEXT DEFAULT ''"),
                        ("updated_at", "REAL NOT NULL DEFAULT 0"),
                        ("stale_notified_at", "REAL"),
                    ):
                        if name not in columns:
                            await conn.execute(
                                f"ALTER TABLE fsm_states ADD COLUMN {name} {definition}"
                            )
                    # Legacy rows have no reliable activity time. Give them a
                    # fresh grace period without changing their saved session.
                    await conn.execute(
                        "UPDATE fsm_states SET updated_at=? WHERE updated_at IS NULL OR updated_at<=0",
                        (time.time(),),
                    )
                    await conn.commit()
                except BaseException:
                    await conn.close()
                    raise
                self._conn = conn
        return self._conn

    async def open(self) -> None:
        """Complete schema migration before updates and scheduled jobs start."""
        await self._get_conn()

    async def set_state(self, key: StorageKey, state=None) -> None:
        """Persist the FSM state value for the given chat/user key."""
        conn = await self._get_conn()
        state_val = None if state is None else state.state if hasattr(state, 'state') else str(state)
        await conn.execute(
            "INSERT INTO fsm_states (chat_id, user_id, state, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET state=excluded.state, "
            "updated_at=excluded.updated_at, stale_notified_at=NULL",
            (key.chat_id, key.user_id, state_val, time.time()),
        )
        await conn.commit()

    async def get_state(self, key: StorageKey) -> Optional[str]:
        """Retrieve the current FSM state string for the given chat/user key."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT state FROM fsm_states WHERE chat_id=? AND user_id=?",
            (key.chat_id, key.user_id),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        """Persist the FSM context data dict as JSON for the given chat/user key."""
        conn = await self._get_conn()
        await conn.execute(
            "INSERT INTO fsm_states (chat_id, user_id, data, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET data=excluded.data, "
            "updated_at=excluded.updated_at, stale_notified_at=NULL",
            (key.chat_id, key.user_id, json.dumps(data, default=str), time.time()),
        )
        await conn.commit()

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        """Retrieve and deserialize the FSM context data dict for the given chat/user key."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT data FROM fsm_states WHERE chat_id=? AND user_id=?",
            (key.chat_id, key.user_id),
        ) as cur:
            row = await cur.fetchone()
            return json.loads(row[0]) if row and row[0] else {}

    async def close(self) -> None:
        """Close the underlying SQLite connection."""
        async with self._init_lock:
            if self._conn:
                await self._conn.close()
                self._conn = None

    async def get_inactive_states(self, before: float) -> list:
        """Find sessions needing a reminder, without changing their saved data."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT chat_id, user_id, state, updated_at FROM fsm_states "
            "WHERE state IS NOT NULL AND updated_at<=? "
            "AND (stale_notified_at IS NULL OR stale_notified_at<updated_at)",
            (before,),
        ) as cur:
            return await cur.fetchall()

    async def mark_inactivity_notified(self, chat_id: int, user_id: int,
                                     updated_at: float) -> None:
        """Acknowledge a reminder only if the session has not changed meanwhile."""
        conn = await self._get_conn()
        await conn.execute(
            "UPDATE fsm_states SET stale_notified_at=? "
            "WHERE chat_id=? AND user_id=? AND updated_at=?",
            (updated_at, chat_id, user_id, updated_at),
        )
        await conn.commit()
