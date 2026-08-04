import os

# Set test env vars BEFORE any pullup_bot imports so config.py doesn't hard-fail
os.environ.setdefault("PULLUP_TESTING", "1")
os.environ.setdefault("PULLUP_BOT_TOKEN", "test_token")
os.environ.setdefault("PULLUP_SECRET", "TESTCODE")
os.environ.setdefault("ADMIN_TG_ID", "999")
os.environ.setdefault("GROQ_API_KEY", "test_groq_key")

import pytest
import pytest_asyncio
import aiosqlite

import pullup_bot.db as db_mod


@pytest_asyncio.fixture
async def test_db():
    """In-memory SQLite DB patched into the db module's global connection."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    old_conn = db_mod._conn
    db_mod._conn = conn
    await db_mod.init_db()
    yield conn
    db_mod._conn = old_conn
    await conn.close()


async def insert_test_user(conn, tg_id=12345, base=100, lang="ru", **kw):
    """Helper to insert a user for tests. Extra kwargs set any other users column."""
    cols = dict(tg_id=tg_id, username="test", first_name="Test", start_day=1,
                lang=lang, base_pullups=base)
    cols.update(kw)
    names = ", ".join(cols)
    placeholders = ", ".join("?" * len(cols))
    await conn.execute(
        f"INSERT INTO users ({names}) VALUES ({placeholders})", tuple(cols.values())
    )
    await conn.commit()
