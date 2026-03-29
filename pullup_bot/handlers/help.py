from aiogram import Router, types
from aiogram.filters import Command

from ..db import get_lang
from ..i18n import t
from ..keyboards import main_kb

router = Router()


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("help", lang), parse_mode="Markdown",
                         reply_markup=main_kb(lang))
