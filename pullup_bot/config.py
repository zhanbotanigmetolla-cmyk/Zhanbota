import os
import logging
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.env.pullup_bot"))

# In test/CI mode, allow missing env vars — modules can be imported safely.
# Set PULLUP_TESTING=1 to skip the hard validation.
_TESTING = os.environ.get("PULLUP_TESTING") == "1"

_REQUIRED_ENV = ["PULLUP_BOT_TOKEN", "PULLUP_SECRET", "ADMIN_TG_ID", "GROQ_API_KEY"]
if not _TESTING:
    _missing_env = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
    if _missing_env:
        raise RuntimeError(f"Missing env vars: {', '.join(_missing_env)}")

BOT_TOKEN = os.environ.get("PULLUP_BOT_TOKEN", "")
SECRET_CODE = os.environ.get("PULLUP_SECRET", "TESTCODE")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
DB_PATH = os.environ.get("PULLUP_DB", os.path.expanduser("~/pullups.db"))
FSM_DB_PATH = os.environ.get("PULLUP_FSM_DB", os.path.expanduser("~/pullups_fsm.db"))
SECRET_CODE_NORM = SECRET_CODE.strip().upper()
ADMIN_TG_ID = int(os.environ.get("ADMIN_TG_ID", "0"))
ADMIN_USERNAMES = {"zhanbota102"}  # Always-admin usernames regardless of tg_id
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")

WAVE = {
    0: ("Средний",   1.0),
    1: ("Лёгкий",    0.5),
    2: ("Тяжёлый",   1.15),
    3: ("Отдых",     0.0),
    4: ("Плотность", 1.0),
    5: ("Лёгкий",    0.5),
    6: ("Отдых",     0.0),
}

XP_PER_PULLUP = 1
XP_PER_STREAK_DAY = 50
LEVEL_THRESHOLDS = [0, 500, 1200, 2500, 4500, 7000, 10000, 14000, 19000, 25000, 999999]
LEVEL_NAMES = ["Новичок", "Стартер", "Любитель", "Атлет", "Боец",
               "Мастер", "Элита", "Легенда", "Titan", "God Mode", "∞"]

START_MENU_LABEL = "/start"


def is_admin_id(tg_id: int) -> bool:
    return tg_id == ADMIN_TG_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("pullup_bot")
