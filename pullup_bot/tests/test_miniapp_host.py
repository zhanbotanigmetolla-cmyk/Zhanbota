from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from pullup_bot import config
from pullup_bot.miniapp_server import setup_static


@pytest.mark.parametrize("url", [
    "http://example.test/app", "https://example.test/", "https://example.test/app?x=1",
    "https://example.test/app#fragment", "https://user:pass@example.test/app", "https:///app",
])
def test_launch_url_must_be_https_app_entry(monkeypatch, url):
    monkeypatch.setattr(config, "MINI_APP_URL", url)
    with pytest.raises(RuntimeError):
        config.validate_miniapp_config()


async def test_host_serves_only_public_assets():
    app = web.Application()
    setup_static(app)
    async with TestClient(TestServer(app)) as client:
        for path in ("/app", "/app/"):
            response = await client.get(path)
            assert response.status == 200
            assert "telegram-web-app.js" in await response.text()
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert "object-src 'none'" in response.headers["Content-Security-Policy"]
        for path in ("/app/app.css", "/app/app.js"):
            assert (await client.get(path)).status == 200
        for path in ("/config.py", "/app/config.py", "/.env", "/app/.env", "/pullups.db"):
            assert (await client.get(path)).status == 404
        response = await client.get("/healthz")
        assert await response.json() == {"ok": True, "service": "turnikmen"}


async def test_telegram_menu_keeps_bot_commands(monkeypatch):
    import pullup_bot.main as main
    bot = SimpleNamespace(set_my_commands=AsyncMock(), set_chat_menu_button=AsyncMock())
    monkeypatch.setattr(main, "bot", bot)
    monkeypatch.setattr(main, "MINI_APP_URL", "https://example.test/app")
    await main._set_bot_commands()
    commands = bot.set_my_commands.call_args_list[0].args[0]
    assert {command.command for command in commands} >= {"app", "train", "stats", "history", "cancel"}
    menu = bot.set_chat_menu_button.call_args.kwargs["menu_button"]
    assert menu.web_app.url == "https://example.test/app"
    monkeypatch.setattr(main, "MINI_APP_URL", "")
    await main._set_bot_commands()
    assert bot.set_chat_menu_button.call_args.kwargs["menu_button"].type == "commands"


async def test_app_launch_preserves_unfinished_bot_state(monkeypatch):
    from pullup_bot.handlers import start
    message = SimpleNamespace(from_user=SimpleNamespace(id=12345),
                              chat=SimpleNamespace(type="private"), answer=AsyncMock())
    monkeypatch.setattr(start, "get_lang", AsyncMock(return_value="ru"))
    monkeypatch.setattr(start, "MINI_APP_URL", "https://example.test/app")
    await start.cmd_app(message)
    markup = message.answer.call_args.kwargs["reply_markup"]
    assert markup.inline_keyboard[0][0].web_app.url == "https://example.test/app"


async def test_polling_and_miniapp_share_one_process(monkeypatch):
    import pullup_bot.main as main
    import pullup_bot.miniapp as api
    from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
    from aiohttp import web

    storage = MemoryStorage()
    storage.open = AsyncMock()
    storage.close = AsyncMock()
    isolation = SimpleEventIsolation()
    bot = SimpleNamespace(id=123456, delete_webhook=AsyncMock(), session=SimpleNamespace(close=AsyncMock()))
    dispatcher = SimpleNamespace(fsm=SimpleNamespace(events_isolation=isolation),
                                 start_polling=AsyncMock(side_effect=RuntimeError("test stop")))
    runner = SimpleNamespace(setup=AsyncMock(), cleanup=AsyncMock())
    site = SimpleNamespace(start=AsyncMock())
    create_runner = Mock(return_value=runner)
    setup_api = Mock()
    for name, value in {"bot": bot, "dp": dispatcher, "storage": storage,
                        "scheduler": Mock(running=True), "init_db": AsyncMock(),
                        "close_db": AsyncMock(), "_set_bot_commands": AsyncMock(),
                        "configure_scheduler": Mock(), "WEBHOOK_URL": "",
                        "MINI_APP_URL": "https://example.test/app", "WEB_BIND": "127.0.0.1",
                        "validate_webhook_config": Mock(), "validate_miniapp_config": Mock()}.items():
        monkeypatch.setattr(main, name, value)
    monkeypatch.setattr(web, "AppRunner", create_runner)
    monkeypatch.setattr(web, "TCPSite", Mock(return_value=site))
    monkeypatch.setattr(api, "setup_miniapp", setup_api)
    with pytest.raises(RuntimeError, match="test stop"):
        await main.main()
    site.start.assert_awaited_once()
    dispatcher.start_polling.assert_awaited_once_with(bot)
    assert setup_api.call_args.kwargs["events_isolation"] is isolation
    assert setup_api.call_args.kwargs["storage"] is storage
    runner.cleanup.assert_awaited_once()
    storage.close.assert_awaited_once()
