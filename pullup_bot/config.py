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
EXERCISES = ["pullups", "pushups", "dips", "squats",
             "pullups_weighted", "dips_weighted"]

# Exercises performed with extra load hung from a belt/vest. They carry a
# weight in kg on the workout row and progress by adding weight, not only reps.
WEIGHTED_EXERCISES = ["pullups_weighted", "dips_weighted"]

# The bodyweight movement each weighted variant is built on, so the UI can
# group them and the guide can point back to the basics.
WEIGHTED_PARENT = {
    "pullups_weighted": "pullups",
    "dips_weighted": "dips",
}

EXERCISE_EMOJI = {
    "pullups": "🆙",
    "pushups": "💪",
    "dips": "⏸️",
    "squats": "🦵",
    "pullups_weighted": "🏋️",
    "dips_weighted": "⛓️",
}

# XP per rep — easier-per-rep exercises earn proportionally less
# to keep ranks comparable across exercises. Weighted variants start from the
# same per-rep value as the bodyweight movement; the load multiplier below is
# what makes a weighted rep worth more.
XP_PER_REP = {
    "pullups": 1.0,
    "dips": 0.75,
    "pushups": 0.5,
    "squats": 0.25,
    "pullups_weighted": 1.0,
    "dips_weighted": 0.75,
}

# Each kg of added load makes a rep worth 3% more XP, counted up to 50 kg
# (a 50 kg rep is worth 2.5 bodyweight reps). Capped so that a mis-typed 500
# cannot mint an unbounded amount of XP.
XP_PER_KG = 0.03
XP_KG_CAP = 50

# users-table column that stores the daily base for each exercise
BASE_COLS = {
    "pullups": "base_pullups",
    "pushups": "base_pushups",
    "dips": "base_dips",
    "squats": "base_squats",
    "pullups_weighted": "base_pullups_weighted",
    "dips_weighted": "base_dips_weighted",
}

# users-table columns for records (best day total / best single set)
PR_COLS = {
    "pullups": "personal_record",
    "pushups": "personal_record_pushups",
    "dips": "personal_record_dips",
    "squats": "personal_record_squats",
    "pullups_weighted": "personal_record_pullups_weighted",
    "dips_weighted": "personal_record_dips_weighted",
}
SET_RECORD_COLS = {
    "pullups": "set_record",
    "pushups": "set_record_pushups",
    "dips": "set_record_dips",
    "squats": "set_record_squats",
    "pullups_weighted": "set_record_pullups_weighted",
    "dips_weighted": "set_record_dips_weighted",
}

# Weighted-only: the load currently being worked with, and the heaviest ever used
WEIGHT_COLS = {
    "pullups_weighted": "weight_pullups_weighted",
    "dips_weighted": "weight_dips_weighted",
}
BEST_WEIGHT_COLS = {
    "pullups_weighted": "best_weight_pullups_weighted",
    "dips_weighted": "best_weight_dips_weighted",
}

# Load is added in 2.5 kg steps — the smallest plate most people own.
WEIGHT_STEP = 2.5
# Never suggest more than this in one jump, whatever the maths says.
MAX_WEIGHT_KG = 100.0

# SQL expression converting a workouts row to XP (for weekly leaderboards).
# Mirrors xp_for(): weighted rows scale with the load stored on the row.
XP_CASE_SQL = (
    "CASE exercise "
    "WHEN 'pullups' THEN completed "
    "WHEN 'dips' THEN completed * 0.75 "
    "WHEN 'pushups' THEN completed * 0.5 "
    "WHEN 'squats' THEN completed * 0.25 "
    f"WHEN 'pullups_weighted' THEN completed * (1 + MIN(COALESCE(weight_kg,0), {XP_KG_CAP}) * {XP_PER_KG}) "
    f"WHEN 'dips_weighted' THEN completed * 0.75 * (1 + MIN(COALESCE(weight_kg,0), {XP_KG_CAP}) * {XP_PER_KG}) "
    "ELSE 0 END"
)

# ── RPE expectations ─────────────────────────────────────────────────────────
# What each day of the wave is *supposed* to feel like. A hard day at RPE 8 is
# the plan working, not a signal to back off — comparing raw RPE against one
# fixed threshold made the bot cut the base for training exactly as prescribed.
DAY_TYPE_RPE = {
    "Лёгкий":    5.0,
    "Средний":   6.5,
    "Плотность": 7.0,
    "Тяжёлый":   8.0,
}
DEFAULT_EXPECTED_RPE = 6.5

# How far above/below the day's expected RPE training has to land before the
# base moves. The neutral band between EASY and HARD is deliberately wide:
# small week-to-week swings in how a session feels are noise, not a trend.
RPE_HARD_DELTA = 0.5      # felt half a point harder than prescribed → ease off
RPE_TOO_HARD_DELTA = 1.5  # a point and a half harder → cut properly
RPE_EASY_DELTA = -1.0     # a full point easier than prescribed → add load


def expected_rpe(day_type: str) -> float:
    """Return the RPE a given day type is expected to feel like."""
    return DAY_TYPE_RPE.get(day_type or "", DEFAULT_EXPECTED_RPE)


def is_weighted(exercise: str) -> bool:
    """True if the exercise carries an added load."""
    return exercise in WEIGHTED_EXERCISES


def weight_multiplier(weight_kg: float) -> float:
    """XP multiplier for a rep performed with the given added load."""
    kg = max(0.0, min(float(weight_kg or 0), XP_KG_CAP))
    return 1.0 + kg * XP_PER_KG


def xp_for(exercise: str, reps: int, weight_kg: float = 0) -> int:
    """XP earned for the given rep count, scaled by added load where it applies."""
    per_rep = XP_PER_REP.get(exercise, 0)
    if is_weighted(exercise):
        per_rep *= weight_multiplier(weight_kg)
    return int(round(reps * per_rep))


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

# Telegram message effect IDs (Bot API 7.4+, private chats only)
EFFECT_FIRE = "5104841245755180586"      # 🔥
EFFECT_CONFETTI = "5046509860389126442"  # 🎉


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
