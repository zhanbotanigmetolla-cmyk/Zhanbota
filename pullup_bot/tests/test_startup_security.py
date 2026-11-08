import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.fsm.storage.memory import SimpleEventIsolation

from pullup_bot import config
import pullup_bot.main as app


def test_username_never_grants_admin_access(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TG_ID", 999)
    assert not config.is_admin_user(123, "zhanbota102")
    assert config.is_admin_user(999, "a_new_username")
    monkeypatch.setattr(config, "ADMIN_TG_ID", 0)
    assert not config.is_admin_user(0)


@pytest.mark.parametrize("url,secret", [
    ("https://example.test/webhook", ""),
    ("https://example.test/webhook", "has spaces"),
    ("https://example.test/webhook", "x" * 257),
    ("http://example.test/webhook", "valid-secret"),
    ("https://", "valid-secret"),
    ("https://example.test/custom-path", "valid-secret"),
    ("https://example.test/webhook?key=value", "valid-secret"),
])
def test_invalid_webhook_config_is_rejected(monkeypatch, url, secret):
    monkeypatch.setattr(config, "WEBHOOK_URL", url)
    monkeypatch.setattr(config, "WEBHOOK_SECRET", secret)
    with pytest.raises(RuntimeError):
        config.validate_webhook_config()


def test_polling_needs_no_webhook_secret(monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_URL", "")
    monkeypatch.setattr(config, "WEBHOOK_SECRET", "")
    config.validate_webhook_config()


def test_valid_webhook_configuration(monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_URL", "https://example.test/webhook")
    monkeypatch.setattr(config, "WEBHOOK_SECRET", "a_valid-secret_123")
    config.validate_webhook_config()


async def test_webhook_validation_precedes_database_and_telegram(monkeypatch):
    init_db = AsyncMock()
    monkeypatch.setattr(app, "init_db", init_db)
    monkeypatch.setattr(config, "WEBHOOK_URL", "https://example.test/webhook")
    monkeypatch.setattr(config, "WEBHOOK_SECRET", "")
    with pytest.raises(RuntimeError):
        await app.main()
    init_db.assert_not_awaited()


async def test_polling_preserves_queue_and_closes_resources_on_failure(monkeypatch):
    bot = SimpleNamespace(delete_webhook=AsyncMock(), session=SimpleNamespace(close=AsyncMock()))
    dispatcher = SimpleNamespace(start_polling=AsyncMock(side_effect=RuntimeError("polling failed")))
    scheduler = Mock(running=True)
    storage = SimpleNamespace(open=AsyncMock(), close=AsyncMock())
    close_db = AsyncMock()
    for name, value in {"bot": bot, "dp": dispatcher, "scheduler": scheduler,
                        "storage": storage, "close_db": close_db,
                        "init_db": AsyncMock(), "_set_bot_commands": AsyncMock(),
                        "configure_scheduler": Mock(), "WEBHOOK_URL": "",
                        "MINI_APP_URL": "",
                        "validate_webhook_config": Mock()}.items():
        monkeypatch.setattr(app, name, value)
    with pytest.raises(RuntimeError, match="polling failed"):
        await app.main()
    bot.delete_webhook.assert_awaited_once_with(drop_pending_updates=False)
    close_db.assert_awaited_once()
    storage.close.assert_awaited_once()
    bot.session.close.assert_awaited_once()
    scheduler.shutdown.assert_called_once_with(wait=False)


def test_every_job_uses_the_bot_calendar(monkeypatch):
    scheduler = AsyncIOScheduler(timezone=config.BOT_TIMEZONE)
    monkeypatch.setattr(app, "scheduler", scheduler)
    app.configure_scheduler()
    cron_jobs = [j for j in scheduler.get_jobs() if hasattr(j.trigger, "fields")]
    assert len(cron_jobs) == 7
    assert all(j.trigger.timezone == config.BOT_TIMEZONE for j in cron_jobs)
    assert isinstance(app.dp.fsm.events_isolation, SimpleEventIsolation)


async def test_daily_jobs_tolerate_a_late_tick(monkeypatch):
    """APScheduler skips a job that fires more than 1 s late by default; a busy
    loop at 08:00 on Monday would silently drop the weekly summary."""
    scheduler = AsyncIOScheduler(timezone=config.BOT_TIMEZONE)
    monkeypatch.setattr(app, "scheduler", scheduler)
    app.configure_scheduler()
    scheduler.start(paused=True)  # pending jobs only get their defaults on start
    try:
        for job in scheduler.get_jobs():
            if job.func is app.daily_reminder:
                continue
            assert job.misfire_grace_time >= 120, job.name  # an hour for daily jobs, 2 min for the watchdog
            assert job.coalesce is True, job.name
    finally:
        scheduler.shutdown(wait=False)


async def test_reminder_allows_overlapping_minutes_and_job_failures_alert_the_admin(monkeypatch):
    """One reminder run stalled on a slow Telegram send must not swallow the next
    minutes, and a crashed job must be counted and reported like a handler error."""
    scheduler = AsyncIOScheduler(timezone=config.BOT_TIMEZONE)
    monkeypatch.setattr(app, "scheduler", scheduler)
    app.configure_scheduler()
    scheduler.start(paused=True)
    try:
        reminder = next(job for job in scheduler.get_jobs() if job.func is app.daily_reminder)
        assert reminder.max_instances == 3
        sent = []

        async def fake_send(chat_id, text, **kwargs):
            sent.append((chat_id, text))

        monkeypatch.setattr(app.bot, "send_message", fake_send)
        from pullup_bot.services import monitoring
        before = monitoring.get("errors")
        app._scheduled_job_failed(SimpleNamespace(job_id=reminder.id, code=EVENT_JOB_ERROR,
                                                  exception=RuntimeError("boom")))
        for _ in range(3):
            await asyncio.sleep(0)
        assert monitoring.get("errors") == before + 1
        assert sent and sent[0][0] == config.ADMIN_TG_ID
        assert "daily_reminder" in sent[0][1] and "boom" in sent[0][1]
    finally:
        scheduler.shutdown(wait=False)
