from datetime import date, datetime, timedelta, timezone

import pytest

from pullup_bot import timeutils


@pytest.mark.parametrize("offset,instant,expected_day", [
    (5, datetime(2026, 9, 22, 20, 0, tzinfo=timezone.utc), date(2026, 9, 23)),
    (-3, datetime(2026, 9, 23, 1, 0, tzinfo=timezone.utc), date(2026, 9, 22)),
])
def test_calendar_uses_configured_timezone_across_utc_midnight(monkeypatch, offset, instant, expected_day):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz)

    bot_timezone = timezone(timedelta(hours=offset))
    monkeypatch.setattr(timeutils, "BOT_TIMEZONE", bot_timezone)
    monkeypatch.setattr(timeutils, "datetime", FixedDatetime)
    assert timeutils.today() == expected_day
    assert timeutils.now().utcoffset() == timedelta(hours=offset)
    assert timeutils.now().astimezone(timezone.utc) == instant


def test_display_shows_stored_timestamps_in_bot_time(monkeypatch):
    monkeypatch.setattr(timeutils, "BOT_TIMEZONE", timezone(timedelta(hours=5)))
    assert timeutils.display("2026-11-08 10:00:00") == "08.11.2026 15:00"       # SQLite datetime('now') is UTC
    assert timeutils.display("2026-11-08T11:00:00+05:00") == "08.11.2026 11:00"  # already carries the offset
    assert timeutils.display(None) == "—"
    assert timeutils.display("not a date") == "not a date"
