from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from pullup_bot.handlers import fallback
from pullup_bot.i18n import t
from pullup_bot.services import gemini


@pytest.mark.asyncio
@pytest.mark.parametrize("user,language_code,expected_button", [
    (None, "en", t("btn_login", "en")),
    ({"lang": "ru", "is_logged_out": 0}, "ru", t("btn_ai", "ru")),
    ({"lang": "en", "is_logged_out": 1}, "en", t("btn_login", "en")),
])
async def test_unhandled_message_offers_local_navigation_without_ai(
    monkeypatch, user, language_code, expected_button
):
    get_manager = Mock(side_effect=AssertionError("Fallback must not contact Gemini"))
    monkeypatch.setattr(gemini, "get_manager", get_manager)
    monkeypatch.setattr(fallback, "get_manager", get_manager, raising=False)
    monkeypatch.setattr(fallback, "get_user", AsyncMock(return_value=user))
    monkeypatch.setattr(fallback, "_fallback_cooldown", {})
    message = SimpleNamespace(
        text="Private message outside the AI chat",
        from_user=SimpleNamespace(id=12345, language_code=language_code),
        answer=AsyncMock(),
    )
    state = SimpleNamespace(get_state=AsyncMock(return_value=None))

    await fallback.unhandled_message(message, state)

    get_manager.assert_not_called()
    message.answer.assert_awaited_once()
    reply = message.answer.await_args
    assert message.text not in reply.args[0]
    keyboard = reply.kwargs["reply_markup"]
    assert expected_button in [button.text for row in keyboard.keyboard for button in row]


@pytest.mark.asyncio
async def test_active_input_flow_is_not_replaced_by_fallback_menu(monkeypatch):
    get_user = AsyncMock()
    monkeypatch.setattr(fallback, "get_user", get_user)
    message = SimpleNamespace(
        text="Unexpected input", from_user=SimpleNamespace(id=12345), answer=AsyncMock()
    )
    state = SimpleNamespace(get_state=AsyncMock(return_value="Reg:max_pullups"))

    await fallback.unhandled_message(message, state)

    get_user.assert_not_awaited()
    message.answer.assert_not_awaited()
