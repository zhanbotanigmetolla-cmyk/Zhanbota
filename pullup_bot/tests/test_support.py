from pullup_bot import keyboards
from pullup_bot.i18n import t


def _texts(kb):
    return [btn.text for row in kb.keyboard for btn in row]


def test_support_button_hidden_without_kaspi(monkeypatch):
    monkeypatch.setattr(keyboards, "KASPI_PHONE", "")
    assert t("btn_support", "ru") not in _texts(keyboards.main_kb("ru"))


def test_support_button_on_bottom_row_with_kaspi(monkeypatch):
    monkeypatch.setattr(keyboards, "KASPI_PHONE", "+7 777 000 00 00")
    kb = keyboards.main_kb("en")
    assert t("btn_support", "en") in [btn.text for btn in kb.keyboard[-1]]


def test_support_note_is_bold_and_has_details():
    for lang in ("ru", "en"):
        note = t("support_note", lang, phone="+7 777 000 00 00", name="Жанбота Н.")
        assert "+7 777 000 00 00" in note
        assert "*(Жанбота Н.)*" in note
        assert note.count("*") % 2 == 0  # balanced Markdown bold markers
