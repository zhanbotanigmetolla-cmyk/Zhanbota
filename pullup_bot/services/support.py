from ..config import KASPI_NAME, KASPI_PHONE
from ..i18n import t


def support_line(lang: str, markdown: bool = True) -> str:
    """Return a one-line Kaspi donation ask to append to a message, or "" when no number is set."""
    if not KASPI_PHONE:
        return ""
    key = "support_line" if markdown else "support_line_plain"
    return t(key, lang, phone=KASPI_PHONE, name=KASPI_NAME)
