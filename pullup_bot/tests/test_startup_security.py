from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
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
