"""The bot's calendar, independent of the server's local timezone."""
from datetime import date, datetime

from .config import BOT_TIMEZONE


def now() -> datetime:
    """Return the current timezone-aware time in the configured bot timezone."""
    return datetime.now(BOT_TIMEZONE)


def today() -> date:
    """Return the current day used for workouts, streaks and scheduled jobs."""
    return now().date()
