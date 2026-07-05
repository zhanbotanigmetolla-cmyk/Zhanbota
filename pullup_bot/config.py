import os
import logging
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.env.pullup_bot"))

# In test/CI mode, allow missing env vars — modules can be imported safely.
# Set PULLUP_TESTING=1 to skip the hard validation.
_TESTING = os.environ.get("PULLUP_TESTING") == "1"

_REQUIRED_ENV = ["PULLUP_BOT_TOKEN", "PULLUP_SECRET", "ADMIN_TG_ID", "GEMINI_API_KEY"]
if not _TESTING:
    _missing_env = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
    if _missing_env:
        raise RuntimeError(f"Missing env vars: {', '.join(_missing_env)}")

BOT_TOKEN = os.environ.get("PULLUP_BOT_TOKEN", "")
SECRET_CODE = os.environ.get("PULLUP_SECRET", "TESTCODE")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_KEYS = [k for k in [
    os.environ.get("GEMINI_API_KEY", ""),
    os.environ.get("GEMINI_API_KEY_2", ""),
    os.environ.get("GEMINI_API_KEY_3", ""),
    os.environ.get("GEMINI_API_KEY_4", ""),
] if k]
DB_PATH = os.environ.get("PULLUP_DB", os.path.expanduser("~/pullups.db"))
FSM_DB_PATH = os.environ.get("PULLUP_FSM_DB", os.path.expanduser("~/pullups_fsm.db"))
SECRET_CODE_NORM = SECRET_CODE.strip().upper()
ADMIN_TG_ID = int(os.environ.get("ADMIN_TG_ID", "0"))
ADMIN_USERNAMES = {"zhanbota102"}  # Always-admin usernames regardless of tg_id
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
# UTC offset for notification time matching (default: UTC+5 = Kazakhstan/Almaty)
TZ_OFFSET_HOURS = int(os.environ.get("TZ_OFFSET_HOURS", "5"))

PROGRAMS = {
    "standard": {   # 5x/week — original wave cycle
        0: ("Средний",   1.0),
        1: ("Лёгкий",    0.5),
        2: ("Тяжёлый",   1.15),
        3: ("Отдых",     0.0),
        4: ("Плотность", 1.0),
        5: ("Лёгкий",    0.5),
        6: ("Отдых",     0.0),
    },
    "beginner": {   # 3x/week — more rest, lighter loads
        0: ("Лёгкий",    0.6),
        1: ("Отдых",     0.0),
        2: ("Средний",   1.0),
        3: ("Отдых",     0.0),
        4: ("Лёгкий",    0.6),
        5: ("Отдых",     0.0),
        6: ("Отдых",     0.0),
    },
    "advanced": {   # 6x/week — extra training day
        0: ("Средний",   1.0),
        1: ("Лёгкий",    0.5),
        2: ("Тяжёлый",   1.15),
        3: ("Средний",   1.0),
        4: ("Плотность", 1.0),
        5: ("Лёгкий",    0.5),
        6: ("Отдых",     0.0),
    },
}
# Backward-compat alias — code that imports WAVE directly still works
WAVE = PROGRAMS["standard"]

# ── Exercises ────────────────────────────────────────────────────────────────
# Every workout row is tagged with one of these (or 'rest' for rest-day rows).
EXERCISES = ["pullups", "pushups", "dips", "squats"]

EXERCISE_EMOJI = {
    "pullups": "🆙",
    "pushups": "💪",
    "dips": "⏸️",
    "squats": "🦵",
}

# XP per rep — easier-per-rep exercises earn proportionally less
# to keep ranks comparable across exercises.
XP_PER_REP = {
    "pullups": 1.0,
    "dips": 0.75,
    "pushups": 0.5,
    "squats": 0.25,
}

# users-table column that stores the daily base for each exercise
BASE_COLS = {
    "pullups": "base_pullups",
    "pushups": "base_pushups",
    "dips": "base_dips",
    "squats": "base_squats",
}

# users-table columns for records (best day total / best single set)
PR_COLS = {
    "pullups": "personal_record",
    "pushups": "personal_record_pushups",
    "dips": "personal_record_dips",
    "squats": "personal_record_squats",
}
SET_RECORD_COLS = {
    "pullups": "set_record",
    "pushups": "set_record_pushups",
    "dips": "set_record_dips",
    "squats": "set_record_squats",
}

# SQL expression converting a workouts row to XP (for weekly leaderboards)
XP_CASE_SQL = (
    "CASE exercise "
    "WHEN 'pullups' THEN completed "
    "WHEN 'dips' THEN completed * 0.75 "
    "WHEN 'pushups' THEN completed * 0.5 "
    "WHEN 'squats' THEN completed * 0.25 "
    "ELSE 0 END"
)


def xp_for(exercise: str, reps: int) -> int:
    """XP earned for the given rep count of an exercise (rounded to nearest int)."""
    return int(round(reps * XP_PER_REP.get(exercise, 0)))


XP_PER_STREAK_DAY = 50
LEVEL_THRESHOLDS = [
    0, 500, 1000, 1800, 2800, 4000,        # Silver I – Silver Elite Master
    5500, 7500, 10000, 13500,              # Gold Nova I – Gold Nova Master
    18000, 23000, 29000, 36000,            # Master Guardian I – Distinguished MG
    44000, 53000,                          # Legendary Eagle – LEM
    63000,                                 # Supreme Master First Class
    70000,                                 # The Global Elite
    999999,                                # sentinel (∞)
]
LEVEL_NAMES = [
    "Silver I", "Silver II", "Silver III", "Silver IV",
    "Silver Elite", "Silver Elite Master",
    "Gold Nova I", "Gold Nova II", "Gold Nova III", "Gold Nova Master",
    "Master Guardian I", "Master Guardian II", "Master Guardian Elite",
    "Distinguished Master Guardian",
    "Legendary Eagle", "Legendary Eagle Master",
    "Supreme Master First Class",
    "The Global Elite",
    "∞",
]

START_MENU_LABEL = "/start"


def is_admin_id(tg_id: int) -> bool:
    """Return True if the given Telegram ID matches the configured admin."""
    return tg_id == ADMIN_TG_ID


def is_admin_user(tg_id: int, username: str | None = None) -> bool:
    """Return True if the Telegram ID or username matches the configured admin."""
    if tg_id == ADMIN_TG_ID:
        return True
    return (username or "").lower() in {u.lower() for u in ADMIN_USERNAMES}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("pullup_bot")
