"""Schema, migrations and queries for fitness-mcp's own database.

Design notes
------------
* ``workouts`` is the spine: one row per training session, from any source.
  ``raw_json`` keeps the original upstream payload so a bad parse never
  destroys fidelity — a fixed parser can be re-run over stored raw data.
* ``sets`` holds strength/calisthenics work. A session may contain sets of
  several different exercises, so ``exercise`` lives on the set, not the
  workout.
* Idempotency: ``UNIQUE(source, source_id)`` plus ``ON CONFLICT ... DO UPDATE``.
  Sets are fully replaced per workout inside the same transaction, so editing a
  day upstream can never leave stale sets behind.
* Times are stored UTC; ``local_date`` is precomputed by the adapter in the
  configured local zone and is what every query filters and groups on.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = 2

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS workouts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT    NOT NULL,
    source_id   TEXT    NOT NULL,
    started_at  TEXT    NOT NULL,           -- UTC, ISO-8601 'YYYY-MM-DDTHH:MM:SSZ'
    local_date  TEXT    NOT NULL,           -- 'YYYY-MM-DD' in the configured local zone
    sport_type  TEXT,
    duration_s  INTEGER,
    distance_m  REAL,
    avg_hr      INTEGER,
    max_hr      INTEGER,
    kcal        INTEGER,
    elevation_m REAL,
    raw_json    TEXT,
    imported_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_workouts_local_date  ON workouts(local_date);
CREATE INDEX IF NOT EXISTS idx_workouts_sport_type  ON workouts(sport_type);

CREATE TABLE IF NOT EXISTS sets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    exercise   TEXT    NOT NULL,
    reps       INTEGER,
    weight_kg  REAL,
    rpe        REAL,
    set_index  INTEGER NOT NULL,
    -- 1 when the upstream recorded only a session total and the per-set
    -- breakdown was reconstructed. Such sets still count toward volume but are
    -- excluded from "best single set" records, which would otherwise be wrong.
    inferred   INTEGER NOT NULL DEFAULT 0,
    UNIQUE(workout_id, exercise, set_index)
);

CREATE INDEX IF NOT EXISTS idx_sets_workout  ON sets(workout_id);
CREATE INDEX IF NOT EXISTS idx_sets_exercise ON sets(exercise);
"""

_SCHEMA_V2 = """
-- Not every source knows when a session started. The pullup bot records only a
-- date, so its started_at is a synthesized day marker. Cross-source dedup must
-- not treat those as real clock times or every same-day session would collide.
ALTER TABLE workouts ADD COLUMN time_precision TEXT NOT NULL DEFAULT 'exact';

-- Dedup keeps BOTH source rows and marks the poorer one superseded, rather than
-- deleting it. Nothing is lost, and a wrong merge is reversible by clearing this
-- column. Queries return only canonical rows (superseded_by IS NULL).
ALTER TABLE workouts ADD COLUMN superseded_by INTEGER REFERENCES workouts(id);

UPDATE workouts SET time_precision = 'date_only' WHERE source = 'pullup_bot';

CREATE INDEX IF NOT EXISTS idx_workouts_superseded ON workouts(superseded_by);

-- Daily wellness metrics. Currently only the Xiaomi export carries these; the
-- bot has none of it. One row per (source, day).
CREATE TABLE IF NOT EXISTS daily_metrics (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source            TEXT    NOT NULL,
    local_date        TEXT    NOT NULL,
    resting_hr        INTEGER,
    sleep_minutes     INTEGER,
    sleep_stages_json TEXT,
    steps             INTEGER,
    stress            INTEGER,
    raw_json          TEXT,
    imported_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(source, local_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(local_date);
"""

_MIGRATIONS = {1: _SCHEMA_V1, 2: _SCHEMA_V2}


# ── connection ──────────────────────────────────────────────────────────────

def connect(path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    """Open a connection. ``read_only=True`` uses SQLite URI ro mode."""
    path = Path(path)
    if read_only:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        # There are now two independent writers — the hourly bot sync and the
        # pushed Apple Health endpoint. WAL lets a reader continue during a
        # write, and the busy timeout makes a collision wait rather than fail
        # with "database is locked".
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Bring the schema up to SCHEMA_VERSION. Safe to call on every start.

    Steps apply in order and each bumps the recorded version, so an existing
    database upgrades in place rather than needing a rebuild.
    """
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version(version) VALUES (0)")
        current = 0
    else:
        current = int(row["version"])

    for version in range(current + 1, SCHEMA_VERSION + 1):
        conn.executescript(_MIGRATIONS[version])
        conn.execute("UPDATE schema_version SET version = ?", (version,))
    conn.commit()


# ── write path (used by ingest only) ────────────────────────────────────────

@dataclass
class SetRow:
    exercise: str
    reps: int | None = None
    weight_kg: float | None = None
    rpe: float | None = None
    set_index: int = 0
    inferred: bool = False


@dataclass
class WorkoutRow:
    source: str
    source_id: str
    started_at: str
    local_date: str
    sport_type: str | None = None
    duration_s: int | None = None
    distance_m: float | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    kcal: int | None = None
    elevation_m: float | None = None
    raw: Any = None
    sets: Sequence[SetRow] = ()
    # 'exact' when started_at is a real clock time, 'date_only' when the source
    # knew the day but not the time. Only 'exact' rows take part in dedup.
    time_precision: str = "exact"


def upsert_workout(conn: sqlite3.Connection, w: WorkoutRow) -> tuple[int, bool]:
    """Insert or update one workout and replace its sets.

    Returns ``(workout_id, created)``. Caller controls the transaction.
    """
    existing = conn.execute(
        "SELECT id FROM workouts WHERE source = ? AND source_id = ?", (w.source, w.source_id)
    ).fetchone()

    conn.execute(
        """
        INSERT INTO workouts (source, source_id, started_at, local_date, sport_type,
                              duration_s, distance_m, avg_hr, max_hr, kcal,
                              elevation_m, raw_json, time_precision)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, source_id) DO UPDATE SET
            started_at     = excluded.started_at,
            local_date     = excluded.local_date,
            sport_type     = excluded.sport_type,
            duration_s     = excluded.duration_s,
            distance_m     = excluded.distance_m,
            avg_hr         = excluded.avg_hr,
            max_hr         = excluded.max_hr,
            kcal           = excluded.kcal,
            elevation_m    = excluded.elevation_m,
            raw_json       = excluded.raw_json,
            time_precision = excluded.time_precision,
            imported_at    = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
        """,
        (
            w.source, w.source_id, w.started_at, w.local_date, w.sport_type,
            w.duration_s, w.distance_m, w.avg_hr, w.max_hr, w.kcal,
            w.elevation_m,
            json.dumps(w.raw, ensure_ascii=False) if w.raw is not None else None,
            w.time_precision,
        ),
    )

    if existing is None:
        workout_id = int(
            conn.execute(
                "SELECT id FROM workouts WHERE source = ? AND source_id = ?",
                (w.source, w.source_id),
            ).fetchone()["id"]
        )
        created = True
    else:
        workout_id = int(existing["id"])
        created = False

    # Full replacement keeps re-ingest exactly idempotent even when the upstream
    # session was edited to have fewer sets than before.
    conn.execute("DELETE FROM sets WHERE workout_id = ?", (workout_id,))
    conn.executemany(
        """INSERT INTO sets (workout_id, exercise, reps, weight_kg, rpe, set_index, inferred)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (workout_id, s.exercise, s.reps, s.weight_kg, s.rpe, s.set_index, int(s.inferred))
            for s in w.sets
        ],
    )
    return workout_id, created


# ── read path (used by MCP tools) ───────────────────────────────────────────

_WORKOUT_COLS = """
    id, source, local_date, started_at, time_precision, sport_type, duration_s,
    distance_m, avg_hr, max_hr, kcal, elevation_m
"""


def list_workouts(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
    sport_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    sql = f"""
        SELECT {_WORKOUT_COLS},
               (SELECT COUNT(*)   FROM sets s WHERE s.workout_id = w.id) AS set_count,
               (SELECT COALESCE(SUM(s.reps), 0) FROM sets s WHERE s.workout_id = w.id) AS total_reps,
               (SELECT GROUP_CONCAT(DISTINCT s.exercise) FROM sets s WHERE s.workout_id = w.id) AS exercises
        FROM workouts w
        WHERE local_date BETWEEN ? AND ? AND superseded_by IS NULL
    """
    params: list[Any] = [start_date, end_date]
    if sport_type:
        sql += " AND sport_type = ?"
        params.append(sport_type)
    sql += " ORDER BY local_date DESC, started_at DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params)]


def get_workout(conn: sqlite3.Connection, workout_id: int) -> dict | None:
    row = conn.execute(
        f"SELECT {_WORKOUT_COLS}, imported_at FROM workouts w WHERE id = ?", (workout_id,)
    ).fetchone()
    if row is None:
        return None
    out = dict(row)
    out["sets"] = [
        dict(r)
        for r in conn.execute(
            """SELECT exercise, set_index, reps, weight_kg, rpe, inferred
               FROM sets WHERE workout_id = ?
               ORDER BY exercise, set_index""",
            (workout_id,),
        )
    ]
    out["total_reps"] = sum(s["reps"] or 0 for s in out["sets"])
    return out


# Monday-start week buckets: 'weekday 0' advances to the coming Sunday (staying
# put if already Sunday), and -6 days lands on that week's Monday.
_BUCKET_SQL = {
    "day": "local_date",
    "week": "date(local_date, 'weekday 0', '-6 days')",
    "month": "strftime('%Y-%m', local_date)",
}


def training_summary(
    conn: sqlite3.Connection, start_date: str, end_date: str, group_by: str = "week"
) -> list[dict]:
    if group_by not in _BUCKET_SQL:
        raise ValueError(f"group_by must be one of {sorted(_BUCKET_SQL)}, got {group_by!r}")
    bucket = _BUCKET_SQL[group_by]

    # Sets are aggregated in a subquery first. Joining sets directly to workouts
    # would multiply each workout row by its set count and inflate the duration,
    # distance and session-count sums.
    sql = f"""
        SELECT {bucket} AS bucket,
               COUNT(*)                        AS sessions,
               -- Distinct days, because several activities can share one day:
               -- six cycling commutes is six sessions but one training day.
               COUNT(DISTINCT w.local_date)    AS training_days,
               COALESCE(SUM(sw.reps), 0)       AS total_reps,
               COALESCE(SUM(w.duration_s), 0)  AS duration_s,
               COALESCE(SUM(w.distance_m), 0)  AS distance_m
        FROM workouts w
        LEFT JOIN (
            SELECT workout_id, SUM(reps) AS reps FROM sets GROUP BY workout_id
        ) sw ON sw.workout_id = w.id
        WHERE w.local_date BETWEEN ? AND ? AND w.superseded_by IS NULL
        GROUP BY bucket
        ORDER BY bucket
    """
    return [dict(r) for r in conn.execute(sql, (start_date, end_date))]


def exercise_history(
    conn: sqlite3.Connection,
    exercise: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    sql = """
        SELECT w.local_date, w.id AS workout_id, s.set_index, s.reps,
               s.weight_kg, s.rpe, s.inferred
        FROM sets s JOIN workouts w ON w.id = s.workout_id
        WHERE s.exercise = ? AND w.superseded_by IS NULL
    """
    params: list[Any] = [exercise]
    if start_date:
        sql += " AND w.local_date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND w.local_date <= ?"
        params.append(end_date)
    sql += " ORDER BY w.local_date, s.set_index"
    return [dict(r) for r in conn.execute(sql, params)]


def personal_records(conn: sqlite3.Connection, exercise: str | None = None) -> list[dict]:
    """Best set by reps, best by weight, and estimated 1RM, per exercise.

    Weight-based records are only meaningful where the source recorded a load.
    For unweighted bodyweight work every ``weight_kg`` is NULL, and the honest
    answer is null rather than a fabricated number — see the tool description.
    """
    where, params = "", []
    if exercise:
        where = "AND s.exercise = ?"
        params.append(exercise)

    exercises = [
        r["exercise"]
        for r in conn.execute(
            "SELECT DISTINCT s.exercise FROM sets s JOIN workouts w ON w.id = s.workout_id "
            f"WHERE w.superseded_by IS NULL {where} ORDER BY 1",
            params,
        )
    ]

    out: list[dict] = []
    for ex in exercises:
        # inferred sets are reconstructed from a session total and would produce
        # a fake "best single set", so they are excluded from records.
        best_reps = conn.execute(
            """SELECT s.reps, s.weight_kg, s.rpe, w.local_date
               FROM sets s JOIN workouts w ON w.id = s.workout_id
               WHERE s.exercise = ? AND w.superseded_by IS NULL AND s.inferred = 0 AND s.reps IS NOT NULL
               ORDER BY s.reps DESC, w.local_date ASC LIMIT 1""",
            (ex,),
        ).fetchone()

        best_weight = conn.execute(
            """SELECT s.reps, s.weight_kg, s.rpe, w.local_date
               FROM sets s JOIN workouts w ON w.id = s.workout_id
               WHERE s.exercise = ? AND w.superseded_by IS NULL AND s.inferred = 0 AND s.weight_kg IS NOT NULL
               ORDER BY s.weight_kg DESC, w.local_date ASC LIMIT 1""",
            (ex,),
        ).fetchone()

        # Epley: 1RM = w * (1 + reps/30). Undefined without an external load.
        best_1rm = conn.execute(
            """SELECT s.reps, s.weight_kg, w.local_date,
                      s.weight_kg * (1 + s.reps / 30.0) AS est_1rm
               FROM sets s JOIN workouts w ON w.id = s.workout_id
               WHERE s.exercise = ? AND w.superseded_by IS NULL AND s.inferred = 0
                     AND s.weight_kg IS NOT NULL AND s.reps IS NOT NULL
               ORDER BY est_1rm DESC, w.local_date ASC LIMIT 1""",
            (ex,),
        ).fetchone()

        best_session = conn.execute(
            """SELECT w.local_date, SUM(s.reps) AS reps
               FROM sets s JOIN workouts w ON w.id = s.workout_id
               WHERE s.exercise = ? AND w.superseded_by IS NULL
               GROUP BY w.id ORDER BY reps DESC, w.local_date ASC LIMIT 1""",
            (ex,),
        ).fetchone()

        out.append({
            "exercise": ex,
            "best_set_by_reps": dict(best_reps) if best_reps else None,
            "best_set_by_weight": dict(best_weight) if best_weight else None,
            "estimated_1rm": (
                {**dict(best_1rm), "formula": "Epley"} if best_1rm else None
            ),
            "best_session_total_reps": dict(best_session) if best_session else None,
        })
    return out


# Standard five-zone model, as a fraction of observed max HR.
HR_ZONES = [
    ("Z1 recovery",  0.00, 0.60),
    ("Z2 aerobic",   0.60, 0.70),
    ("Z3 tempo",     0.70, 0.80),
    ("Z4 threshold", 0.80, 0.90),
    ("Z5 max",       0.90, 1.01),
]


def hr_distribution(conn: sqlite3.Connection, start_date: str, end_date: str) -> dict:
    """Approximate time-in-zone from per-session average HR.

    The schema stores one avg/max HR per session, not a heart-rate time series,
    so true time-in-zone is not derivable. Each session's whole duration is
    attributed to the single zone its average HR falls in. Sessions without HR
    are reported separately rather than silently dropped.
    """
    rows = conn.execute(
        """SELECT avg_hr, max_hr, duration_s, local_date
           FROM workouts
           WHERE local_date BETWEEN ? AND ? AND superseded_by IS NULL""",
        (start_date, end_date),
    ).fetchall()

    observed_max = max((r["max_hr"] or 0) for r in rows) if rows else 0
    buckets = {name: {"zone": name, "sessions": 0, "duration_s": 0} for name, _, _ in HR_ZONES}
    without_hr = 0

    for r in rows:
        if not r["avg_hr"] or not observed_max:
            without_hr += 1
            continue
        frac = r["avg_hr"] / observed_max
        for name, lo, hi in HR_ZONES:
            if lo <= frac < hi:
                buckets[name]["sessions"] += 1
                buckets[name]["duration_s"] += r["duration_s"] or 0
                break

    return {
        "method": "per-session average HR attributed to a single zone; "
                  "not a true time-in-zone integration",
        "reference_max_hr": observed_max or None,
        "sessions_with_hr": len(rows) - without_hr,
        "sessions_without_hr": without_hr,
        "zones": list(buckets.values()),
    }


# ── daily wellness metrics ──────────────────────────────────────────────────

@dataclass
class DailyMetricRow:
    source: str
    local_date: str
    resting_hr: int | None = None
    sleep_minutes: int | None = None
    sleep_stages: Any = None
    steps: int | None = None
    stress: int | None = None
    raw: Any = None


def upsert_daily_metric(conn: sqlite3.Connection, m: DailyMetricRow) -> None:
    conn.execute(
        """
        INSERT INTO daily_metrics (source, local_date, resting_hr, sleep_minutes,
                                   sleep_stages_json, steps, stress, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, local_date) DO UPDATE SET
            resting_hr        = excluded.resting_hr,
            sleep_minutes     = excluded.sleep_minutes,
            sleep_stages_json = excluded.sleep_stages_json,
            steps             = excluded.steps,
            stress            = excluded.stress,
            raw_json          = excluded.raw_json,
            imported_at       = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
        """,
        (
            m.source, m.local_date, m.resting_hr, m.sleep_minutes,
            json.dumps(m.sleep_stages, ensure_ascii=False) if m.sleep_stages is not None else None,
            m.steps, m.stress,
            json.dumps(m.raw, ensure_ascii=False) if m.raw is not None else None,
        ),
    )


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def recovery_metrics(conn: sqlite3.Connection, start_date: str, end_date: str) -> dict:
    """Resting HR and sleep over a range, with a first-half/second-half trend.

    The trend is a plain comparison of the two halves of the range, not a
    regression. It is easy to explain and hard to over-read, which is the point.
    """
    rows = [
        dict(r)
        for r in conn.execute(
            """SELECT local_date, resting_hr, sleep_minutes, steps, stress
               FROM daily_metrics
               WHERE local_date BETWEEN ? AND ?
               ORDER BY local_date""",
            (start_date, end_date),
        )
    ]

    if not rows:
        return {
            "days": [],
            "note": "No daily wellness data is stored for this range. These metrics "
                    "come from the Xiaomi export only; the pullup bot records none. "
                    "This means no data source is connected, not that recovery was poor.",
            "resting_hr": None,
            "sleep": None,
            "trend": None,
        }

    rhr = [r["resting_hr"] for r in rows if r["resting_hr"] is not None]
    sleep = [r["sleep_minutes"] for r in rows if r["sleep_minutes"] is not None]

    half = len(rows) // 2
    first_rhr = [r["resting_hr"] for r in rows[:half] if r["resting_hr"] is not None]
    second_rhr = [r["resting_hr"] for r in rows[half:] if r["resting_hr"] is not None]
    trend = None
    if first_rhr and second_rhr:
        delta = round(_avg(second_rhr) - _avg(first_rhr), 1)
        trend = {
            "resting_hr_first_half": _avg(first_rhr),
            "resting_hr_second_half": _avg(second_rhr),
            "resting_hr_change": delta,
            # Lower resting HR generally indicates better recovery.
            "direction": "improving" if delta < 0 else "worsening" if delta > 0 else "flat",
        }

    return {
        "days": rows,
        "resting_hr": {
            "avg": _avg(rhr), "min": min(rhr) if rhr else None,
            "max": max(rhr) if rhr else None, "days_with_data": len(rhr),
        },
        "sleep": {
            "avg_minutes": _avg(sleep), "min_minutes": min(sleep) if sleep else None,
            "max_minutes": max(sleep) if sleep else None, "days_with_data": len(sleep),
        },
        "trend": trend,
    }


# ── cross-source deduplication ──────────────────────────────────────────────

# Fields whose presence makes one source's copy of a workout richer than another's.
_RICHNESS_FIELDS = ("duration_s", "distance_m", "avg_hr", "max_hr", "kcal", "elevation_m")


# When two sources record the same activity, the one earlier in this list wins
# regardless of field count. Xiaomi comes from the watch itself and carries HR
# zones, training load and recovery figures that Strava's export does not, so it
# is preferred even on the occasional record where it populates fewer columns.
# Xiaomi outranks Apple Health because the watch record carries HR zones and
# training load that HealthKit does not expose. In practice they barely meet:
# the Xiaomi export is historical (through 2026-07-26) and Apple Health is the
# live source from 2026-07-27, so this only matters if a newer Xiaomi export is
# ever imported over the same dates. Flip the order here to change that.
SOURCE_PRIORITY = ("xiaomi_export", "apple_health", "strava_export", "pullup_bot")


def _priority(source: str) -> int:
    """Lower is better. Unknown sources rank last but still beat nothing."""
    return SOURCE_PRIORITY.index(source) if source in SOURCE_PRIORITY else len(SOURCE_PRIORITY)


def _richness(row: sqlite3.Row) -> int:
    score = sum(1 for f in _RICHNESS_FIELDS if row[f] is not None)
    return score + (1 if row["set_count"] else 0)


def _epoch(started_at: str) -> float:
    return datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ").timestamp()


def find_duplicate_pairs(
    conn: sqlite3.Connection,
    time_tolerance_s: int = 180,
    duration_tolerance_s: int = 120,
    duration_tolerance_frac: float = 0.25,
) -> list[dict]:
    """Identify the same activity recorded by two different sources.

    Only rows with an exact start time are considered. The pullup bot's
    ``started_at`` is a synthesized day marker, so including those would make
    every same-day session look like a duplicate of every other.

    Matching requires a different source, start times within
    ``time_tolerance_s``, and — when both sides report one — durations within
    ``duration_tolerance_s``. The richer row wins and the other is superseded.
    """
    rows = conn.execute(
        """SELECT w.*, (SELECT COUNT(*) FROM sets s WHERE s.workout_id = w.id) AS set_count
           FROM workouts w
           WHERE w.time_precision = 'exact' AND w.superseded_by IS NULL
           ORDER BY w.started_at"""
    ).fetchall()

    pairs: list[dict] = []
    superseded: set[int] = set()

    for i, a in enumerate(rows):
        if a["id"] in superseded:
            continue
        for b in rows[i + 1:]:
            if b["id"] in superseded or a["source"] == b["source"]:
                continue
            gap = abs(_epoch(a["started_at"]) - _epoch(b["started_at"]))
            if gap > time_tolerance_s:
                break  # rows are start-time ordered, so nothing later can match
            if a["duration_s"] is not None and b["duration_s"] is not None:
                # Sources do not agree on what "duration" means: Xiaomi reports
                # active time (paused time excluded) while Strava reports
                # elapsed. A fixed tolerance would miss real duplicates whenever
                # a session was paused, so it scales with the longer session.
                allowed = max(duration_tolerance_s,
                              duration_tolerance_frac * max(a["duration_s"], b["duration_s"]))
                if abs(a["duration_s"] - b["duration_s"]) > allowed:
                    continue

            ra, rb = _richness(a), _richness(b)
            # Source preference decides first; field count only breaks ties
            # between equally-preferred sources. On a full tie the lower id is
            # kept, so repeated runs are stable rather than flip-flopping.
            rank_a = (_priority(a["source"]), -ra, a["id"])
            rank_b = (_priority(b["source"]), -rb, b["id"])
            keep, drop = (a, b) if rank_a <= rank_b else (b, a)
            superseded.add(drop["id"])
            pairs.append({
                "keep_id": keep["id"], "keep_source": keep["source"],
                "supersede_id": drop["id"], "supersede_source": drop["source"],
                "start_gap_s": round(gap), "richness": {keep["source"]: max(ra, rb),
                                                        drop["source"]: min(ra, rb)},
            })
    return pairs


def deduplicate(conn: sqlite3.Connection, **kw) -> list[dict]:
    """Apply :func:`find_duplicate_pairs`. Returns what was merged.

    Nothing is deleted — the superseded row keeps its data and its ``raw_json``.
    Clearing ``superseded_by`` fully reverses a merge.
    """
    pairs = find_duplicate_pairs(conn, **kw)
    with conn:
        for p in pairs:
            conn.execute(
                "UPDATE workouts SET superseded_by = ? WHERE id = ?",
                (p["keep_id"], p["supersede_id"]),
            )
    return pairs
