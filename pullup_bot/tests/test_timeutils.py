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
