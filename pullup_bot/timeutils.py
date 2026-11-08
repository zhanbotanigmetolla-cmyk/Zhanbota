"""The bot's calendar, independent of the server's local timezone."""
from datetime import date, datetime, timezone

from .config import BOT_TIMEZONE


def now() -> datetime:
    """Return the current timezone-aware time in the configured bot timezone."""
    return datetime.now(BOT_TIMEZONE)


def today() -> date:
    """Return the current day used for workouts, streaks and scheduled jobs."""
    return now().date()


def display(value, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Format a stored timestamp in the bot's timezone.

    SQLite's ``datetime('now')`` defaults and older code wrote naive UTC strings;
    newer code writes ISO strings with an offset. Both are shown in BOT_TIMEZONE so
    the admin panel and the bot's calendar agree.
    """
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(BOT_TIMEZONE).strftime(fmt)
