import sqlite3

import pytest

from fitness_mcp import db

# Bot schema subset the adapter actually reads. Kept minimal on purpose: if the
# adapter starts depending on a new column, these fixtures fail loudly.
_BOT_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE NOT NULL,
    username TEXT
);
CREATE TABLE workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    exercise TEXT NOT NULL DEFAULT 'pullups',
    planned INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    sets_json TEXT DEFAULT '[]',
    rpe INTEGER DEFAULT 0,
    day_type TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    UNIQUE(user_id, date, exercise)
);
"""


@pytest.fixture
def fitness_db(tmp_path):
    """Empty, migrated fitness-mcp database."""
    conn = db.connect(tmp_path / "fitness.db")
    db.migrate(conn)
    yield conn
    conn.close()


@pytest.fixture
def bot_db_factory(tmp_path):
    """Builds a synthetic pullup_bot database from row tuples."""

    def build(rows, *, tg_id=111, extra_users=()):
        path = tmp_path / "bot.db"
        conn = sqlite3.connect(path)
        conn.executescript(_BOT_SCHEMA)
        conn.execute("INSERT INTO users (id, tg_id, username) VALUES (1, ?, 'owner')", (tg_id,))
        for uid, utg in extra_users:
            conn.execute("INSERT INTO users (id, tg_id, username) VALUES (?, ?, 'other')", (uid, utg))
        conn.executemany(
            """INSERT INTO workouts (user_id, date, exercise, planned, completed,
                                     sets_json, rpe, day_type, notes)
               VALUES (:user_id, :date, :exercise, :planned, :completed,
                       :sets_json, :rpe, :day_type, :notes)""",
            [
                {
                    "user_id": 1, "planned": 0, "completed": 0, "sets_json": "[]",
                    "rpe": 0, "day_type": "", "notes": "", **r,
                }
                for r in rows
            ],
        )
        conn.commit()
        conn.close()
        return str(path)

    return build


def add_workout(conn, *, source="test", source_id, local_date, sets=(), **kw):
    """Insert a workout with known sets straight into the fitness database."""
    row = db.WorkoutRow(
        source=source,
        source_id=source_id,
        started_at=f"{local_date}T00:00:00Z",
        local_date=local_date,
        sport_type=kw.pop("sport_type", "strength"),
        sets=[db.SetRow(**s) for s in sets],
        **kw,
    )
    with conn:
        wid, _ = db.upsert_workout(conn, row)
    return wid
