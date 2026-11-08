from types import SimpleNamespace

from pullup_bot import config
from pullup_bot.handlers import help as help_handler
from pullup_bot.i18n import t
from pullup_bot.keyboards import main_kb, settings_kb
from .conftest import insert_test_user


class FakeMessage:
    def __init__(self, tg_id):
        self.from_user = SimpleNamespace(id=tg_id)
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append(text)


def _texts(markup):
    return [button.text for row in markup.keyboard for button in row]


async def test_help_hides_admin_commands_from_participants(test_db):
    await insert_test_user(test_db, tg_id=1)
    message = FakeMessage(1)
    await help_handler.cmd_help(message)
    assert "/train" in message.answers[0]
    assert "/version" not in message.answers[0]


async def test_help_shows_admin_commands_to_the_admin(test_db):
    await insert_test_user(test_db, tg_id=config.ADMIN_TG_ID)
    message = FakeMessage(config.ADMIN_TG_ID)
    await help_handler.cmd_help(message)
    assert "/version" in message.answers[0]


def test_bug_report_moved_from_the_main_menu_to_settings():
    for lang in ("ru", "en"):
        assert t("btn_bug", lang) not in _texts(main_kb(lang))
        assert t("btn_bug", lang) in _texts(settings_kb(lang))
        assert len(main_kb(lang).keyboard) <= 5
