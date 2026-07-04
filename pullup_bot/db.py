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
    # index 13
    "ALTER TABLE users ADD COLUMN is_weekly_champ INTEGER DEFAULT 0",
    # index 14
    """CREATE TABLE IF NOT EXISTS ai_usage_log (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        date     TEXT NOT NULL,
        user_id  INTEGER,
        model    TEXT,
        question TEXT,
        answer   TEXT,
        created  TEXT DEFAULT (datetime('now'))
    )""",
    # index 15 — no-op: question already included in CREATE TABLE at index 14
    "SELECT 1",
    # index 16 — no-op: answer already included in CREATE TABLE at index 14
    "SELECT 1",
    # index 17 — missing indexes for frequently queried columns
    "CREATE INDEX IF NOT EXISTS idx_ai_usage_log_date ON ai_usage_log(date)",
    # index 18
    "CREATE INDEX IF NOT EXISTS idx_bug_reports_status ON bug_reports(status)",
    # index 19 — opt-in workout finish notifications (default OFF)
    "ALTER TABLE users ADD COLUMN notify_workouts INTEGER DEFAULT 0",
    # index 20 — flag for morning reminder when base was auto-increased
    "ALTER TABLE users ADD COLUMN base_increased_to INTEGER DEFAULT NULL",
    # index 21 — per-set personal record (best single-set rep count ever)
    "ALTER TABLE users ADD COLUMN set_record INTEGER DEFAULT 0",
    # index 22 — selected training program ('standard', 'beginner', 'advanced')
    "ALTER TABLE users ADD COLUMN program_type TEXT DEFAULT 'standard'",
    # index 23 — all-time maximum streak reached
    "ALTER TABLE users ADD COLUMN max_streak INTEGER DEFAULT 0",
    # index 24 — drop legacy weight_kg column (never collected, always defaulted to 80)
    "ALTER TABLE users DROP COLUMN weight_kg",
    # index 25–30 — multi-exercise support: per-exercise bases and records
    "ALTER TABLE users ADD COLUMN base_pushups INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN base_dips INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN personal_record_pushups INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN set_record_pushups INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN personal_record_dips INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN set_record_dips INTEGER DEFAULT 0",
]


async def _migrate_workouts_exercise(conn):
    """
    One-time rebuild of the workouts table adding the exercise dimension.

    - New column `exercise` ('pullups'/'pushups'/'dips' or 'rest' for rest-day rows)
    - UNIQUE(user_id, date) becomes UNIQUE(user_id, date, exercise)
    - Legacy rest rows (day_type='Отдых', no reps) become exercise='rest';
      everything else becomes 'pullups'
    - Drops the removed extra_activity/extra_minutes columns

    Runs inside an explicit transaction; raises on failure so the bot stops
    loudly instead of running on a half-migrated schema.
    """
    async with conn.execute("PRAGMA table_info(workouts)") as cur:
        cols = [r[1] for r in await cur.fetchall()]
    if "exercise" in cols:
        return  # already migrated

    logger.info("[migration] rebuilding workouts table with exercise column...")
    try:
        await conn.execute("""
            CREATE TABLE workouts_new (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                date      TEXT NOT NULL,
                exercise  TEXT NOT NULL DEFAULT 'pullups',
                planned   INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                sets_json TEXT DEFAULT '[]',
                rpe       INTEGER DEFAULT 0,
                day_type  TEXT DEFAULT '',
                notes     TEXT DEFAULT '',
                UNIQUE(user_id, date, exercise)
            )
        """)
        await conn.execute("""
            INSERT INTO workouts_new
                (id, user_id, date, exercise, planned, completed, sets_json, rpe, day_type, notes)
            SELECT id, user_id, date,
                   CASE WHEN day_type='Отдых' AND COALESCE(completed,0)=0
                        THEN 'rest' ELSE 'pullups' END,
                   planned, completed, sets_json, rpe, day_type, notes
            FROM workouts
        """)
        async with conn.execute("SELECT COUNT(*) FROM workouts") as cur:
            old_count = (await cur.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM workouts_new") as cur:
            new_count = (await cur.fetchone())[0]
        if old_count != new_count:
            raise RuntimeError(
                f"workouts migration row mismatch: {old_count} -> {new_count}")
        await conn.execute("DROP TABLE workouts")
        await conn.execute("ALTER TABLE workouts_new RENAME TO workouts")
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workouts_user_date ON workouts(user_id, date)")
        await conn.commit()
        logger.info(f"[migration] workouts table rebuilt OK ({new_count} rows)")
    except Exception:
        await conn.rollback()
        logger.error("[migration] workouts rebuild FAILED — rolled back")
        raise


async def get_db() -> aiosqlite.Connection:
    """Return the shared singleton DB connection, opening it on first call."""
    global _conn
    if _conn is None:
        _conn = await aiosqlite.connect(DB_PATH)
        _conn.row_factory = aiosqlite.Row
        await _conn.execute("PRAGMA journal_mode=WAL")
        await _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


async def close_db():
    """Close the shared DB connection and reset the singleton to None."""
    global _conn
    if _conn:
        await _conn.close()
        _conn = None


async def init_db():
    """Create all tables, run pending migrations, and seed program_day for legacy users."""
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
            lang          TEXT DEFAULT 'ru',
            program_day   INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS workouts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            date           TEXT NOT NULL,
            exercise       TEXT NOT NULL DEFAULT 'pullups',
            planned        INTEGER DEFAULT 0,
            completed      INTEGER DEFAULT 0,
            sets_json      TEXT DEFAULT '[]',
            rpe            INTEGER DEFAULT 0,
            day_type       TEXT DEFAULT '',
            notes          TEXT DEFAULT '',
            UNIQUE(user_id, date, exercise)
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
        except Exception as e:
            # Column/index may already exist — log for visibility
            logger.debug(f"[migration {i}] skipped: {e}")
    if current < len(MIGRATIONS):
        await conn.execute("UPDATE migrations SET version=?", (len(MIGRATIONS),))
    # Structural rebuild — must run after column migrations, raises on failure
    await _migrate_workouts_exercise(conn)
    # Legacy migrations (idempotent — safe to run even if column already exists)
    for col_sql in [
        "ALTER TABLE users ADD COLUMN first_name TEXT",
        "ALTER TABLE users ADD COLUMN is_logged_out INTEGER DEFAULT 0",
    ]:
        try:
            await conn.execute(col_sql)
        except Exception:
            pass  # column already exists
    # Seed program_day from start_day for existing users (only where never set)
    await conn.execute(
        "UPDATE users SET program_day = start_day WHERE program_day IS NULL"
    )
    # Backfill max_streak: at minimum it equals the current streak
    await conn.execute(
        "UPDATE users SET max_streak = streak WHERE max_streak < streak"
    )
    # Backfill set_record: scan all sets_json and find each user's best single set
    async with conn.execute(
        "SELECT user_id, sets_json FROM workouts "
        "WHERE exercise='pullups' AND sets_json IS NOT NULL AND sets_json != '[]'"
    ) as cur:
        best: dict[int, int] = {}
        async for row in cur:
            try:
                sets = json.loads(row[1])
                if sets:
                    m = max(sets)
                    if m > best.get(row[0], 0):
                        best[row[0]] = m
            except Exception:
                pass
    for uid, top_set in best.items():
        await conn.execute(
            "UPDATE users SET set_record = ? WHERE id = ? AND set_record < ?",
            (top_set, uid, top_set)
        )
    await conn.commit()


async def get_user(tg_id: int) -> Optional[aiosqlite.Row]:
    """Fetch a user row by Telegram ID, or None if not registered."""
    conn = await get_db()
    async with conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)) as cur:
        return await cur.fetchone()


async def get_lang(tg_id: int) -> str:
    """Return the user's preferred language code ('ru' or 'en'), defaulting to 'ru'."""
    user = await get_user(tg_id)
    return user["lang"] if user and user["lang"] else "ru"


async def get_workout(user_id: int, d: str, exercise: str) -> Optional[aiosqlite.Row]:
    """Return the workout row for the given user, date and exercise, or None."""
    conn = await get_db()
    async with conn.execute(
        "SELECT * FROM workouts WHERE user_id=? AND date=? AND exercise=?",
        (user_id, d, exercise)
    ) as cur:
        return await cur.fetchone()


async def get_day_rows(user_id: int, d: str = None) -> list:
    """Return all workout rows (any exercise, incl. rest markers) for the given date."""
    if d is None:
        d = date.today().isoformat()
    conn = await get_db()
    async with conn.execute(
        "SELECT * FROM workouts WHERE user_id=? AND date=?", (user_id, d)
    ) as cur:
        return await cur.fetchall()


_WORKOUT_COLS = {"planned", "completed", "sets_json", "rpe", "day_type", "notes"}


async def upsert_workout(user_id: int, d: str, exercise: str, **kwargs):
    """Insert or update the workout row for (user, date, exercise) with the supplied values."""
    for k in kwargs:
        if k not in _WORKOUT_COLS:
            raise ValueError(f"Invalid workout column: {k}")
    conn = await get_db()
    if kwargs:
        cols = "user_id, date, exercise, " + ", ".join(kwargs.keys())
        vals = "?, ?, ?, " + ", ".join("?" * len(kwargs))
        updates = ", ".join(f"{k}=excluded.{k}" for k in kwargs)
        await conn.execute(
            f"INSERT INTO workouts ({cols}) VALUES ({vals})"
            f" ON CONFLICT(user_id, date, exercise) DO UPDATE SET {updates}",
            [user_id, d, exercise] + list(kwargs.values()),
        )
    else:
        await conn.execute(
            "INSERT OR IGNORE INTO workouts (user_id, date, exercise) VALUES (?, ?, ?)",
            (user_id, d, exercise),
        )
    await conn.commit()


async def mark_rest_day(user_id: int, d: str):
    """Write the day-level rest marker row (idempotent)."""
    await upsert_workout(user_id, d, "rest", planned=0, completed=0,
                         day_type="Отдых", sets_json=json.dumps([]))


async def clear_rest_row(user_id: int, d: str):
    """Remove the rest marker row for a date (used when a rest day is overridden)."""
    conn = await get_db()
    await conn.execute(
        "DELETE FROM workouts WHERE user_id=? AND date=? AND exercise='rest'",
        (user_id, d)
    )
    await conn.commit()


def _level_from_xp(xp: int) -> int:
    """Compute the level index from a raw XP value using the global thresholds table."""
    lvl = 0
    for i, t in enumerate(LEVEL_THRESHOLDS[:-1]):
        if xp >= t:
            lvl = i
    return lvl


async def add_xp(tg_id: int, amount: int):
    """Add (or subtract) XP for a user and recalculate their level."""
    conn = await get_db()
    await conn.execute("UPDATE users SET xp = xp + ? WHERE tg_id = ?", (amount, tg_id))
    async with conn.execute("SELECT xp FROM users WHERE tg_id = ?", (tg_id,)) as cur:
        row = await cur.fetchone()
    if row:
        xp = max(0, row[0])
        lvl = _level_from_xp(xp)
        await conn.execute("UPDATE users SET level=?, xp=? WHERE tg_id=?", (lvl, xp, tg_id))
    await conn.commit()


async def update_streak(tg_id: int, today: str = None):
    """Extend or reset the streak. Auto-spends freeze tokens for missed training days."""
    user = await get_user(tg_id)
    if not user:
        return
    if today is None:
        today = date.today().isoformat()
    last = user["last_workout"]
    today_d = date.fromisoformat(today)
    yesterday = (today_d - timedelta(days=1)).isoformat()
    conn = await get_db()
    if last == today:
        return

    old_streak = user["streak"] or 0

    if last is None or last == yesterday:
        # No gap — simple start or extend
        new_streak = 1 if last is None else old_streak + 1
    else:
        # Gap detected — find which gap days have rest-day records (free) vs missed (cost a token each)
        last_d = date.fromisoformat(last)
        gap_days = [
            (last_d + timedelta(days=i)).isoformat()
            for i in range(1, (today_d - last_d).days)
        ]
        if gap_days:
            placeholders = ",".join("?" * len(gap_days))
            async with conn.execute(
                f"SELECT date FROM workouts WHERE user_id=? AND date IN ({placeholders}) AND planned=0",
                [user["id"]] + gap_days,
            ) as cur:
                rest_rows = await cur.fetchall()
            rest_dates = {r["date"] for r in rest_rows}
            missed = [d for d in gap_days if d not in rest_dates]
        else:
            missed = []

        tokens = user["freeze_tokens"] or 0
        if len(missed) <= tokens:
            # Auto-spend tokens silently to bridge missed days
            if missed:
                await conn.execute(
                    "UPDATE users SET freeze_tokens=? WHERE tg_id=?",
                    (tokens - len(missed), tg_id),
                )
            new_streak = old_streak + 1
        else:
            # Not enough tokens — streak resets
            new_streak = 1

    await conn.execute(
        "UPDATE users SET streak=?, last_workout=?, inactivity_warned=NULL WHERE tg_id=?",
        (new_streak, today, tg_id),
    )
    # Award streak XP whenever the streak genuinely continued (not a reset to 1 from nothing)
    if last is not None and new_streak == old_streak + 1:
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
    """Return (users, total_count) for the given page, ordered by join date descending."""
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
    """Search users by Telegram ID (if numeric) or by username/first_name substring."""
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
    """Set is_banned=1 and add the user to the permanent banned_ids table."""
    conn = await get_db()
    await conn.execute("UPDATE users SET is_banned=1 WHERE tg_id=?", (tg_id,))
    try:
        await conn.execute(
            "INSERT OR REPLACE INTO banned_ids (tg_id, reason) VALUES (?, ?)",
            (tg_id, reason)
        )
    except Exception as e:
        logger.warning(f"[ban_user] failed to insert banned_ids for {tg_id}: {e}")
    await conn.commit()


async def unban_user(tg_id: int) -> None:
    """Clear the is_banned flag for the given user."""
    conn = await get_db()
    await conn.execute("UPDATE users SET is_banned=0 WHERE tg_id=?", (tg_id,))
    await conn.commit()


async def mute_user(tg_id: int, until_iso: str) -> None:
    """Set muted_until to an ISO datetime string, silencing the user until that time."""
    conn = await get_db()
    await conn.execute("UPDATE users SET muted_until=? WHERE tg_id=?", (until_iso, tg_id))
    await conn.commit()


async def unmute_user(tg_id: int) -> None:
    """Clear the muted_until field, restoring full access for the user."""
    conn = await get_db()
    await conn.execute("UPDATE users SET muted_until=NULL WHERE tg_id=?", (tg_id,))
    await conn.commit()


async def is_muted(tg_id: int) -> bool:
    """Return True if the user's muted_until timestamp is in the future."""
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
    """Zero out the streak and clear last_workout for the given user."""
    conn = await get_db()
    await conn.execute("UPDATE users SET streak=0, last_workout=NULL WHERE tg_id=?", (tg_id,))
    await conn.commit()


async def reset_xp(tg_id: int) -> None:
    """Reset XP and level to zero for the given user."""
    conn = await get_db()
    await conn.execute("UPDATE users SET xp=0, level=0 WHERE tg_id=?", (tg_id,))
    await conn.commit()


async def apply_xp_decay(tg_id: int, days_inactive: int):
    """
    Decay XP for an inactive user (grace period: 7 days).

    Decay rate:
      days 7–13: 0.5% of XP/day (min 20 XP)
      days 14–20: 1.0% of XP/day (min 30 XP)
      days 21+:   1.5% of XP/day (min 50 XP)

    Floor: XP cannot drop below the threshold of one rank below current.
    Returns (old_xp, new_xp, old_level, new_level) or None if no decay applied.
    """
    if days_inactive < 7:
        return None
    conn = await get_db()
    async with conn.execute("SELECT xp, level FROM users WHERE tg_id=?", (tg_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    current_xp = row[0] or 0
    current_level = row[1] or 0
    # Floor: one rank below current — cap the loss at a single rank per absence
    floor_xp = LEVEL_THRESHOLDS[max(0, current_level - 1)] if current_level > 0 else 0
    if current_xp <= floor_xp:
        return None
    if days_inactive < 14:
        rate, min_decay = 0.005, 20
    elif days_inactive < 21:
        rate, min_decay = 0.010, 30
    else:
        rate, min_decay = 0.015, 50
    decay = max(min_decay, int(current_xp * rate))
    new_xp = max(floor_xp, current_xp - decay)
    if new_xp == current_xp:
        return None
    new_level = _level_from_xp(new_xp)
    await conn.execute(
        "UPDATE users SET xp=?, level=? WHERE tg_id=?",
        (new_xp, new_level, tg_id)
    )
    await conn.commit()
    return current_xp, new_xp, current_level, new_level


async def give_freeze_tokens(tg_id: int, delta: int, max_tokens: int = 5) -> None:
    """Add or remove freeze tokens, clamping the result between 0 and max_tokens."""
    conn = await get_db()
    await conn.execute(
        "UPDATE users SET freeze_tokens = MIN(?, MAX(0, freeze_tokens + ?)) WHERE tg_id=?",
        (max_tokens, delta, tg_id)
    )
    await conn.commit()


async def get_bot_stats() -> dict:
    """Return aggregate bot statistics: total users, banned count, active today, and total workouts."""
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
    async with conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT user_id, date FROM workouts WHERE completed > 0)"
    ) as cur:
        total_workouts = (await cur.fetchone())[0]
    return {
        "total_users": total_users,
        "banned_count": banned_count,
        "active_today": active_today,
        "total_workouts": total_workouts,
    }


async def is_permanently_banned(tg_id: int) -> bool:
    """Return True if the Telegram ID appears in the banned_ids table."""
    conn = await get_db()
    async with conn.execute("SELECT tg_id FROM banned_ids WHERE tg_id=?", (tg_id,)) as cur:
        row = await cur.fetchone()
    return row is not None


async def delete_user_by_tg_id(tg_id: int, permanent_ban: bool = True) -> None:
    """Delete all data for a user and optionally add them to the permanent ban list."""
    conn = await get_db()
    async with conn.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,)) as cur:
        row = await cur.fetchone()
    # Wrap all deletes in a single transaction to avoid orphaned data on crash
    try:
        if row:
            user_id = row[0]
            await conn.execute("DELETE FROM workouts WHERE user_id=?", (user_id,))
            await conn.execute("DELETE FROM friends WHERE user_id=? OR friend_id=?",
                               (user_id, user_id))
            await conn.execute("DELETE FROM streak_recoveries WHERE user_id=?", (user_id,))
            await conn.execute("DELETE FROM bug_reports WHERE user_id=?", (user_id,))
            await conn.execute("DELETE FROM ai_usage_log WHERE user_id=?", (user_id,))
            await conn.execute("DELETE FROM pokes WHERE from_user_id=? OR to_user_id=?",
                               (user_id, user_id))
            await conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        if permanent_ban:
            await conn.execute(
                "INSERT OR REPLACE INTO banned_ids (tg_id, reason) VALUES (?, ?)",
                (tg_id, "admin_deleted")
            )
        await conn.commit()
    except Exception as e:
        logger.error(f"[delete_user] failed for tg_id={tg_id}: {e}")
        await conn.rollback()
        raise


async def log_ai_usage(user_id: int, model: str, question: str = "", answer: str = "") -> None:
    """Insert an AI usage record with the question and answer for analytics."""
    from datetime import date as _date
    conn = await get_db()
    await conn.execute(
        "INSERT INTO ai_usage_log (date, user_id, model, question, answer) VALUES (?, ?, ?, ?, ?)",
        (str(_date.today()), user_id, model, question, answer),
    )
    await conn.commit()


async def get_ai_usage_stats() -> dict:
    """Return today's and all-time AI request counts, plus per-user and per-model breakdowns."""
    from datetime import date as _date
    conn = await get_db()
    today = str(_date.today())
    async with conn.execute(
        "SELECT COUNT(*) as cnt FROM ai_usage_log WHERE date=?", (today,)
    ) as cur:
        today_row = await cur.fetchone()
    async with conn.execute(
        "SELECT COUNT(*) as cnt FROM ai_usage_log"
    ) as cur:
        total_row = await cur.fetchone()
    async with conn.execute(
        """SELECT COALESCE(u.first_name, u.username, 'unknown') as name,
                  COUNT(*) as cnt
           FROM ai_usage_log a
           LEFT JOIN users u ON u.id = a.user_id
           WHERE a.date=?
           GROUP BY a.user_id ORDER BY cnt DESC LIMIT 10""",
        (today,),
    ) as cur:
        per_user = await cur.fetchall()
    async with conn.execute(
        """SELECT model, COUNT(*) as cnt
           FROM ai_usage_log WHERE date=?
           GROUP BY model ORDER BY cnt DESC""",
        (today,),
    ) as cur:
        per_model = await cur.fetchall()
    return {
        "today": today_row["cnt"] if today_row else 0,
        "total": total_row["cnt"] if total_row else 0,
        "per_user": per_user,
        "per_model": per_model,
    }


async def get_ai_conversations(page: int = 0, per_page: int = 5) -> tuple:
    """Return (rows, has_more) for paginated AI conversation log entries, newest first."""
    conn = await get_db()
    offset = page * per_page
    async with conn.execute(
        """SELECT a.id, a.created, a.model, a.question, a.answer,
                  COALESCE(u.first_name, u.username, 'unknown') as name
           FROM ai_usage_log a
           LEFT JOIN users u ON u.id = a.user_id
           ORDER BY a.id DESC
           LIMIT ? OFFSET ?""",
        (per_page + 1, offset),
    ) as cur:
        rows = await cur.fetchall()
    has_more = len(rows) > per_page
    return rows[:per_page], has_more


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
