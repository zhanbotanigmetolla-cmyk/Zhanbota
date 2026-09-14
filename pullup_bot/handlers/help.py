from aiogram import Router, types
from aiogram.filters import Command

from ..config import KASPI_NAME, KASPI_PHONE
from ..db import get_lang
from ..i18n import t, text_filter
from ..keyboards import main_kb
from ..services.support import support_line

router = Router()


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Handle /help command: send the localized help text."""
    lang = await get_lang(message.from_user.id)
    await message.answer(t("help", lang) + support_line(lang), parse_mode="Markdown",
                         reply_markup=main_kb(lang))


@router.message(text_filter("btn_support"))
async def support_project(message: types.Message):
    """Handle the Support button: show the Kaspi number for voluntary transfers."""
    lang = await get_lang(message.from_user.id)
    if not KASPI_PHONE:
        return
    await message.answer(t("support_text", lang, phone=KASPI_PHONE, name=KASPI_NAME),
                         parse_mode="Markdown", reply_markup=main_kb(lang))
