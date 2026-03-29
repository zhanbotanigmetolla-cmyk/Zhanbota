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
    """Helper to insert a user for tests."""
    defaults = dict(username="test", first_name="Test", start_day=1,
                    weight_kg=80.0, lang=lang, base_pullups=base)
    defaults.update(kw)
    await conn.execute(
        "INSERT INTO users (tg_id, username, first_name, base_pullups, "
        "start_day, weight_kg, lang) VALUES (?,?,?,?,?,?,?)",
        (tg_id, defaults["username"], defaults["first_name"],
         defaults["base_pullups"], defaults["start_day"],
         defaults["weight_kg"], defaults["lang"]))
    await conn.commit()
