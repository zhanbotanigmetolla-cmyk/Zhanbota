"""The assistant never hangs the chat and always fits Telegram's message limit."""
import asyncio
from types import SimpleNamespace

from pullup_bot.handlers import ai
from pullup_bot.i18n import t
from .conftest import insert_test_user


class FakeState:
    def __init__(self, data):
        self.data = dict(data)

    async def get_data(self):
        return self.data

    async def update_data(self, **kwargs):
        self.data.update(kwargs)


class FakeMessage:
    def __init__(self, tg_id, text):
        self.from_user = SimpleNamespace(id=tg_id)
        self.text = text
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))
        return self

    async def edit_text(self, text, **kwargs):
        return self

    async def delete(self):
        return None


class HangingManager:
    async def chat(self, system_prompt, history, text):
        await asyncio.sleep(3600)


def test_split_reply_keeps_every_part_under_the_limit():
    text = "\n\n".join(f"Абзац {i} " + "слово " * 150 for i in range(12))
    parts = ai._split_reply(text)
    assert len(parts) > 1
    assert all(0 < len(part) <= ai.MAX_REPLY_CHARS for part in parts)
    squash = lambda value: value.replace("\n", "").replace(" ", "")
    assert "".join(squash(part) for part in parts) == squash(text)


def test_short_reply_is_not_split():
    assert ai._split_reply("🤖 Привет") == ["🤖 Привет"]


async def test_hanging_gemini_request_ends_with_an_unavailable_notice(test_db, monkeypatch):
    await insert_test_user(test_db, tg_id=1)
    monkeypatch.setattr(ai, "AI_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(ai, "get_manager", lambda: HangingManager())
    message = FakeMessage(1, "Как мне прогрессировать?")
    state = FakeState({"ai_lang": "ru", "ai_system": "", "ai_history": []})
    await asyncio.wait_for(ai.ai_chat_message(message, state), timeout=10)
    assert t("ai_unavailable", "ru") in message.answers[-1][0]


async def test_long_answer_is_delivered_in_several_messages(test_db, monkeypatch):
    await insert_test_user(test_db, tg_id=1)
    long_answer = "Строка совета. " * 600  # ~9 000 characters

    class VerboseManager:
        async def chat(self, system_prompt, history, text):
            return long_answer, "test-model"

    monkeypatch.setattr(ai, "get_manager", lambda: VerboseManager())
    message = FakeMessage(1, "План на месяц?")
    state = FakeState({"ai_lang": "ru", "ai_system": "", "ai_history": []})
    await ai.ai_chat_message(message, state)
    replies = message.answers[1:]  # the first answer is the "thinking" placeholder
    assert len(replies) >= 3
    assert replies[0][0].startswith("🤖")
    assert all(len(text) <= 4096 for text, _ in message.answers)
    assert message.answers[-1][1].get("reply_markup") is not None
