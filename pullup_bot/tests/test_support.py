from pullup_bot import keyboards
from pullup_bot.i18n import t
from pullup_bot.services import support


def test_support_line_empty_without_kaspi(monkeypatch):
    monkeypatch.setattr(support, "KASPI_PHONE", "")
    assert support.support_line("ru") == ""
    assert support.support_line("en", markdown=False) == ""


def test_support_line_markdown_and_plain(monkeypatch):
    monkeypatch.setattr(support, "KASPI_PHONE", "+77770000000")
    for lang in ("ru", "en"):
        md = support.support_line(lang)
        plain = support.support_line(lang, markdown=False)
        assert "+77770000000" in md and "+77770000000" in plain
        assert md.count("*") % 2 == 0 and md.count("`") == 2
        assert "*" not in plain and "`" not in plain


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
