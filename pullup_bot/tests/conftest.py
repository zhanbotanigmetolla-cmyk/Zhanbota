import asyncio
import os
import sys
import tempfile

# Set test env vars BEFORE any pullup_bot imports so config.py doesn't hard-fail
os.environ.setdefault("PULLUP_TESTING", "1")
os.environ.setdefault("PULLUP_BOT_TOKEN", "123456:test_token")
os.environ.setdefault("PULLUP_SECRET", "TESTCODE")
os.environ.setdefault("ADMIN_TG_ID", "999")
os.environ.setdefault("GEMINI_API_KEY", "test_gemini_key")
# Never let a test touch the developer's or the server's real FSM database.
os.environ.setdefault("PULLUP_FSM_DB",
                      os.path.join(tempfile.mkdtemp(prefix="pullup-test-fsm-"), "fsm.db"))

import pytest
import pytest_asyncio
import aiosqlite

import pullup_bot.db as db_mod


@pytest.fixture(autouse=True)
def fsm_hook_isolation():
    """Keep account deletions in tests away from the bot's module-level FSM storage.

    main.py wires ``db.fsm_cleanup_hook`` to the real ``SqliteStorage``; opening it
    from a test starts an aiosqlite worker thread that nothing closes, and pytest
    then prints its summary and never exits (seen on CI and during a deployment).
    The fixture yields the original hook so a test can still assert the wiring.
    """
    original = db_mod.fsm_cleanup_hook
    db_mod.fsm_cleanup_hook = None
    yield original
    db_mod.fsm_cleanup_hook = original


@pytest.fixture(scope="session", autouse=True)
def close_module_level_storage():
    """Belt and braces: close the bot's FSM storage if any test opened it anyway."""
    yield
    app = sys.modules.get("pullup_bot.main")
    storage = getattr(app, "storage", None)
    if storage is not None and getattr(storage, "_conn", None) is not None:
        asyncio.run(storage.close())


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
