import json
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import aiosqlite

from .config import DB_PATH, LEVEL_THRESHOLDS, XP_PER_STREAK_DAY, logger

_conn: Optional[aiosqlite.Connection] = None

MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'ru'",
    "ALTER TABLE users ADD COLUMN program_day INTEGER DEFAULT 0",
    "CREATE INDEX IF NOT EXISTS idx_workouts_user_date ON workouts(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_users_notify_time ON users(notify_time)",
    "CREATE INDEX IF NOT EXISTS idx_streak_recoveries_user_date ON streak_recoveries(user_id, date)",
    "ALTER TABLE users ADD COLUMN personal_record INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN inactivity_warned TEXT DEFAULT NULL",
    "ALTER TABLE users ADD COLUMN is_logged_out INTEGER DEFAULT 0",
    """CREATE TABLE IF NOT EXISTS pokes (
        from_user_id INTEGER NOT NULL,
        to_user_id   INTEGER NOT NULL,
        date         TEXT NOT NULL,
        PRIMARY KEY (from_user_id, to_user_id, date)
    )""",
    """CREATE TABLE IF NOT EXISTS welcome_greetings (
        from_tg_id INTEGER NOT NULL,
        to_tg_id   INTEGER NOT NULL,
        created    TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (from_tg_id, to_tg_id)
    )""",
    # index 10
    "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0",
    # index 11
    "ALTER TABLE users ADD COLUMN muted_until TEXT DEFAULT NULL",
    # index 12
    """CREATE TABLE IF NOT EXISTS banned_ids (
        tg_id     INTEGER PRIMARY KEY,
        reason    TEXT DEFAULT '',
        banned_at TEXT DEFAULT (datetime('now'))
    )""",
]


async def get_db() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        _conn = await aiosqlite.connect(DB_PATH)
        _conn.row_factory = aiosqlite.Row
        await _conn.execute("PRAGMA journal_mode=WAL")
        await _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


async def close_db():
    global _conn
    if _conn:
        await _conn.close()
        _conn = None


async def init_db():
    conn = await get_db()
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id         INTEGER UNIQUE NOT NULL,
            username      TEXT,
            first_name    TEXT,
            joined        TEXT DEFAULT (date('now')),
            base_pullups  INTEGER DEFAULT 130,
            start_day     INTEGER DEFAULT 22,
            level         INTEGER DEFAULT 0,
            xp            INTEGER DEFAULT 0,
            streak        INTEGER DEFAULT 0,
            freeze_tokens INTEGER DEFAULT 3,
            last_workout  TEXT,
            notify_time   TEXT DEFAULT '09:00',
            weight_kg     REAL DEFAULT 80,
            lang          TEXT DEFAULT 'ru',
            program_day   INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS workouts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            date           TEXT NOT NULL,
            planned        INTEGER DEFAULT 0,
            completed      INTEGER DEFAULT 0,
            sets_json      TEXT DEFAULT '[]',
            rpe            INTEGER DEFAULT 0,
            day_type       TEXT DEFAULT '',
            extra_activity TEXT DEFAULT '',
            extra_minutes  INTEGER DEFAULT 0,
            notes          TEXT DEFAULT '',
            UNIQUE(user_id, date)
        );
        CREATE TABLE IF NOT EXISTS streak_recoveries (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date    TEXT NOT NULL,
            reason  TEXT
        );
        CREATE TABLE IF NOT EXISTS friends (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            UNIQUE(user_id, friend_id)
        );
        CREATE TABLE IF NOT EXISTS bug_reports (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER,
            username TEXT,
            text     TEXT,
            created  TEXT DEFAULT (datetime('now')),
            status   TEXT DEFAULT 'new'
        );
    """)
    # Run migrations
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS migrations (version INTEGER DEFAULT 0)"
    )
    async with conn.execute("SELECT version FROM migrations") as cur:
        row = await cur.fetchone()
    if row is None:
        current = 0
        await conn.execute("INSERT INTO migrations (version) VALUES (?)", (0,))
    else:
        current = row[0]
    for i in range(current, len(MIGRATIONS)):
        try:
            await conn.executescript(MIGRATIONS[i])
        except Exception:
            pass  # Column/index may already exist
    if current < len(MIGRATIONS):
        await conn.execute("UPDATE migrations SET version=?", (len(MIGRATIONS),))
    # Legacy migrations (idempotent — safe to run even if column already exists)
    for col_sql in [
        "ALTER TABLE users ADD COLUMN first_name TEXT",
        "ALTER TABLE users ADD COLUMN is_logged_out INTEGER DEFAULT 0",
    ]:
        try:
            await conn.execute(col_sql)
        except Exception:
            pass
    # Seed program_day from start_day for existing users
    await conn.execute(
        "UPDATE users SET program_day = start_day WHERE program_day = 0 OR program_day IS NULL"
    )
    await conn.commit()


async def get_user(tg_id: int) -> Optional[aiosqlite.Row]:
    conn = await get_db()
    async with conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)) as cur:
        return await cur.fetchone()


async def get_lang(tg_id: int) -> str:
    user = await get_user(tg_id)
    return user["lang"] if user and user["lang"] else "ru"


async def get_today_workout(user_id: int, d: str = None) -> Optional[aiosqlite.Row]:
    if d is None:
        d = date.today().isoformat()
    conn = await get_db()
    async with conn.execute(
        "SELECT * FROM workouts WHERE user_id=? AND date=?", (user_id, d)
    ) as cur:
        return await cur.fetchone()


_WORKOUT_COLS = {"planned", "completed", "sets_json", "rpe", "day_type",
                 "extra_activity", "extra_minutes", "notes"}


async def upsert_workout(user_id: int, d: str, **kwargs):
    for k in kwargs:
        if k not in _WORKOUT_COLS:
            raise ValueError(f"Invalid workout column: {k}")
    conn = await get_db()
    async with conn.execute(
        "SELECT id FROM workouts WHERE user_id=? AND date=?", (user_id, d)
    ) as cur:
        existing = await cur.fetchone()
    if existing:
        s = ", ".join(f"{k}=?" for k in kwargs)
        await conn.execute(
            f"UPDATE workouts SET {s} WHERE user_id=? AND date=?",
            list(kwargs.values()) + [user_id, d],
        )
    else:
        cols = "user_id, date, " + ", ".join(kwargs.keys())
        vals = "?, ?, " + ", ".join("?" * len(kwargs))
        await conn.execute(
            f"INSERT INTO workouts ({cols}) VALUES ({vals})",
            [user_id, d] + list(kwargs.values()),
        )
    await conn.commit()


def _level_from_xp(xp: int) -> int:
    lvl = 0
    for i, t in enumerate(LEVEL_THRESHOLDS[:-1]):
        if xp >= t:
            lvl = i
    return lvl


async def add_xp(tg_id: int, amount: int):
    conn = await get_db()
    await conn.execute("UPDATE users SET xp = xp + ? WHERE tg_id = ?", (amount, tg_id))
    async with conn.execute("SELECT xp FROM users WHERE tg_id = ?", (tg_id,)) as cur:
        row = await cur.fetchone()
    if row:
        xp = max(0, row[0])
        lvl = _level_from_xp(xp)
        await conn.execute("UPDATE users SET level=?, xp=? WHERE tg_id=?", (lvl, xp, tg_id))
    await conn.commit()


async def update_streak(tg_id: int):
    user = await get_user(tg_id)
    if not user:
        return
    today = date.today().isoformat()
    last = user["last_workout"]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    conn = await get_db()
    if last == today:
        return
    if last is None or last != yesterday:
        new_streak = 1
    else:
        new_streak = (user["streak"] or 0) + 1
    await conn.execute(
        "UPDATE users SET streak=?, last_workout=?, inactivity_warned=NULL WHERE tg_id=?",
        (new_streak, today, tg_id),
    )
    # Only award streak XP if continuing a streak (not first day)
    if last == yesterday:
        await conn.execute(
            "UPDATE users SET xp = xp + ? WHERE tg_id=?", (XP_PER_STREAK_DAY, tg_id)
        )
    async with conn.execute("SELECT xp FROM users WHERE tg_id=?", (tg_id,)) as cur:
        row = await cur.fetchone()
    if row:
        lvl = _level_from_xp(row[0])
        await conn.execute("UPDATE users SET level=? WHERE tg_id=?", (lvl, tg_id))
    await conn.commit()


async def get_all_users_paginated(page: int, per_page: int = 10):
    conn = await get_db()
    offset = page * per_page
    async with conn.execute("SELECT COUNT(*) FROM users") as cur:
        row = await cur.fetchone()
        total = row[0] if row else 0
    async with conn.execute(
        "SELECT * FROM users ORDER BY joined DESC LIMIT ? OFFSET ?", (per_page, offset)
    ) as cur:
        users = await cur.fetchall()
    return users, total


async def search_users(query: str) -> list:
    conn = await get_db()
    if query.isdigit():
        async with conn.execute(
            "SELECT * FROM users WHERE tg_id=?", (int(query),)
        ) as cur:
            return await cur.fetchall()
    async with conn.execute(
        "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ? LIMIT 20",
        (f"%{query}%", f"%{query}%")
    ) as cur:
        return await cur.fetchall()


async def ban_user(tg_id: int, reason: str = "") -> None:
    conn = await get_db()
    await conn.execute("UPDATE users SET is_banned=1 WHERE tg_id=?", (tg_id,))
    try:
        await conn.execute(
            "INSERT OR REPLACE INTO banned_ids (tg_id, reason) VALUES (?, ?)",
            (tg_id, reason)
        )
    except Exception:
        pass
    await conn.commit()


async def unban_user(tg_id: int) -> None:
    conn = await get_db()
    await conn.execute("UPDATE users SET is_banned=0 WHERE tg_id=?", (tg_id,))
    await conn.commit()


async def mute_user(tg_id: int, until_iso: str) -> None:
    conn = await get_db()
    await conn.execute("UPDATE users SET muted_until=? WHERE tg_id=?", (until_iso, tg_id))
    await conn.commit()


async def unmute_user(tg_id: int) -> None:
    conn = await get_db()
    await conn.execute("UPDATE users SET muted_until=NULL WHERE tg_id=?", (tg_id,))
    await conn.commit()


async def is_muted(tg_id: int) -> bool:
    from datetime import datetime
    conn = await get_db()
    async with conn.execute("SELECT muted_until FROM users WHERE tg_id=?", (tg_id,)) as cur:
        row = await cur.fetchone()
    if not row or not row[0]:
        return False
    try:
        return datetime.fromisoformat(row[0]) > datetime.now()
    except Exception:
        return False


async def reset_streak(tg_id: int) -> None:
    conn = await get_db()
    await conn.execute("UPDATE users SET streak=0, last_workout=NULL WHERE tg_id=?", (tg_id,))
    await conn.commit()


async def reset_xp(tg_id: int) -> None:
    conn = await get_db()
    await conn.execute("UPDATE users SET xp=0, level=0 WHERE tg_id=?", (tg_id,))
    await conn.commit()


async def give_freeze_tokens(tg_id: int, delta: int) -> None:
    conn = await get_db()
    await conn.execute(
        "UPDATE users SET freeze_tokens = MAX(0, freeze_tokens + ?) WHERE tg_id=?",
        (delta, tg_id)
    )
    await conn.commit()


async def get_bot_stats() -> dict:
    from datetime import date as _date
    conn = await get_db()
    async with conn.execute("SELECT COUNT(*) FROM users") as cur:
        total_users = (await cur.fetchone())[0]
    async with conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=1") as cur:
        banned_count = (await cur.fetchone())[0]
    today = _date.today().isoformat()
    async with conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM workouts WHERE date=?", (today,)
    ) as cur:
        active_today = (await cur.fetchone())[0]
    async with conn.execute("SELECT COUNT(*) FROM workouts") as cur:
        total_workouts = (await cur.fetchone())[0]
    return {
        "total_users": total_users,
        "banned_count": banned_count,
        "active_today": active_today,
        "total_workouts": total_workouts,
    }


async def is_permanently_banned(tg_id: int) -> bool:
    conn = await get_db()
    async with conn.execute("SELECT tg_id FROM banned_ids WHERE tg_id=?", (tg_id,)) as cur:
        row = await cur.fetchone()
    return row is not None


async def delete_user_by_tg_id(tg_id: int, permanent_ban: bool = True) -> None:
    conn = await get_db()
    async with conn.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,)) as cur:
        row = await cur.fetchone()
    if row:
        user_id = row[0]
        await conn.execute("DELETE FROM workouts WHERE user_id=?", (user_id,))
        await conn.execute("DELETE FROM friends WHERE user_id=? OR friend_id=?",
                           (user_id, user_id))
        await conn.execute("DELETE FROM streak_recoveries WHERE user_id=?", (user_id,))
        await conn.execute("DELETE FROM bug_reports WHERE user_id=?", (user_id,))
        await conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    if permanent_ban:
        try:
            await conn.execute(
                "INSERT OR REPLACE INTO banned_ids (tg_id, reason) VALUES (?, ?)",
                (tg_id, "admin_deleted")
            )
        except Exception:
            pass
    await conn.commit()


async def add_welcome_greeting(from_tg_id: int, to_tg_id: int) -> bool:
    """Register one-time greeting from one Telegram user to another."""
    if from_tg_id == to_tg_id:
        return False
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO welcome_greetings (from_tg_id, to_tg_id) VALUES (?, ?)",
            (from_tg_id, to_tg_id),
        )
        await conn.commit()
        return True
    except aiosqlite.IntegrityError:
        return False
