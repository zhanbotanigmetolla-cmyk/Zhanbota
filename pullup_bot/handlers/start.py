from aiogram import F, Router, types
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from datetime import date, datetime, timedelta

from ..config import LEVEL_NAMES, SECRET_CODE_NORM, logger
from ..db import add_welcome_greeting, get_db, get_lang, get_user
from ..i18n import t, text_filter
from ..keyboards import (LANG_EN_BTN, LANG_RU_BTN, LANG_TOGGLE_BTN,
                         landing_kb, lang_kb, logout_confirm_kb, main_kb,
                         welcome_new_user_kb)
from ..states import Login, Logout, Reg
from ..services.xp import display, md_escape

router = Router()


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = await get_user(message.from_user.id)
    lang = (user["lang"] or "ru") if user else data.get("lang", "ru")
    current = await state.get_state()
    if current is None:
        kb = main_kb(lang) if user else landing_kb(lang)
        await message.answer(t("nothing_to_cancel", lang), reply_markup=kb)
        return
    await state.clear()
    kb = main_kb(lang) if user else landing_kb(lang)
    await message.answer(t("cancelled", lang), reply_markup=kb)


@router.message(StateFilter(None), text_filter("btn_entrance"))
async def entrance_handler(message: types.Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)
    lang = (user["lang"] or "ru") if user else "ru"
    await message.answer(t("welcome", lang), parse_mode="Markdown", reply_markup=landing_kb(lang))


@router.message(StateFilter(None), text_filter("btn_back"))
async def back_handler(message: types.Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    user = await get_user(message.from_user.id)
    if user:
        await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))
    else:
        await message.answer(t("main_menu", lang), reply_markup=landing_kb(lang))


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)
    if user:
        lang = user["lang"] or "ru"
        await message.answer(t("welcome", lang), parse_mode="Markdown",
                             reply_markup=landing_kb(lang))
    else:
        await message.answer(
            "🌐 *Choose your language / Выберите язык*\n\n"
            "_You can change this later in Settings._\n"
            "_Можно изменить позже в Настройках._",
            parse_mode="Markdown",
            reply_markup=lang_kb())
        await state.set_state(Login.lang)


@router.message(Login.lang, F.text.in_({LANG_RU_BTN, LANG_EN_BTN, LANG_TOGGLE_BTN}))
async def start_pick_lang_toggle(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.text == LANG_RU_BTN:
        lang = "ru"
    elif message.text == LANG_EN_BTN:
        lang = "en"
    else:
        # Legacy toggle
        current = data.get("lang", "")
        lang = "en" if current == "ru" else "ru"
    await state.update_data(lang=lang)
    await message.answer(t("welcome", lang), parse_mode="Markdown", reply_markup=landing_kb(lang))


@router.message(text_filter("btn_about"))
async def about_bot(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    data = await state.get_data()
    lang = (user["lang"] or "ru") if user else data.get("lang", "ru")
    await message.answer(t("about", lang), parse_mode="Markdown",
                         reply_markup=landing_kb(lang))


@router.message(text_filter("btn_guide"))
async def guide_handler(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    data = await state.get_data()
    lang = (user["lang"] or "ru") if user else data.get("lang", "ru")
    await message.answer(t("guide", lang), parse_mode="Markdown",
                         reply_markup=landing_kb(lang))


@router.message(text_filter("btn_exit"))
async def exit_btn(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    data = await state.get_data()
    lang = (user["lang"] or "ru") if user else data.get("lang", "ru")
    if user:
        await message.answer(t("confirm_logout", lang), reply_markup=logout_confirm_kb(lang))
        await state.set_state(Logout.confirm)
    else:
        await state.clear()
        await message.answer(t("bye", lang), reply_markup=ReplyKeyboardRemove())


@router.message(text_filter("btn_login"))
async def login_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if user:
        if user["is_logged_out"]:
            conn = await get_db()
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            await conn.execute(
                "UPDATE users SET is_logged_out=0, last_workout=? WHERE tg_id=?",
                (yesterday, message.from_user.id)
            )
            await conn.commit()
        await state.clear()
        fresh = await get_user(message.from_user.id)
        lang = fresh["lang"] or "ru"
        await message.answer(
            t("welcome_back", lang,
              name=md_escape(display(fresh)),
              level=LEVEL_NAMES[fresh["level"]],
              xp=fresh["xp"],
              streak=fresh["streak"]),
            parse_mode="Markdown", reply_markup=main_kb(lang))
    else:
        data = await state.get_data()
        lang = data.get("lang", "ru")
        await message.answer(t("enter_secret", lang), parse_mode="Markdown",
                             reply_markup=ReplyKeyboardRemove())
        await state.set_state(Login.enter_code)


@router.message(Login.enter_code)
async def login_check(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")

    # Check lockout
    locked_until = data.get("locked_until")
    if locked_until:
        if datetime.now() < datetime.fromisoformat(locked_until):
            await message.answer(t("wrong_code_locked", lang))
            return
        else:
            await state.update_data(attempts=0, locked_until=None)
            data = await state.get_data()

    if not message.text or message.text.strip().upper() != SECRET_CODE_NORM:
        attempts = data.get("attempts", 0) + 1
        if attempts >= 3:
            locked_until = (datetime.now() + timedelta(hours=1)).isoformat()
            await state.update_data(attempts=attempts, locked_until=locked_until)
            await message.answer(t("wrong_code_locked", lang))
            logger.warning(f"[security] user {message.from_user.id} locked out after 3 failed code attempts")
        else:
            await state.update_data(attempts=attempts)
            await message.answer(t("wrong_code", lang, attempts=attempts))
        return

    await state.update_data(attempts=0, locked_until=None)
    await message.answer(t("code_accepted", lang), parse_mode="Markdown")
    await state.set_state(Reg.name)


@router.message(Reg.name)
async def reg_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    name = (message.text or "").strip()
    if len(name) < 3:
        prompt = "❌ Минимум 3 символа. Как тебя зовут?" if lang == "ru" else "❌ At least 3 characters. What's your name?"
        await message.answer(prompt)
        return
    await state.update_data(first_name=name)
    await message.answer(t("hello_name", lang, name=md_escape(name)), parse_mode="Markdown")
    await state.set_state(Reg.weight)


@router.message(Reg.weight)
async def reg_weight(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    if not message.text:
        await message.answer(t("enter_number", lang, example="90"))
        return
    try:
        text = message.text.strip()
        if len(text) > 8:
            await message.answer(t("enter_number", lang, example="90"))
            return
        w = float(text)
        await state.update_data(weight=w)
        await message.answer(t("enter_base", lang), parse_mode="Markdown")
        await state.set_state(Reg.base)
    except ValueError:
        await message.answer(t("enter_number", lang, example="90"))


@router.message(Reg.base)
async def reg_base(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    if not message.text:
        await message.answer(t("enter_number", lang, example="130"))
        return
    try:
        text = message.text.strip()
        if len(text) > 5 or not (1 <= int(text) <= 500):
            await message.answer(t("enter_number", lang, example="130"))
            return
        base = int(text)
        await state.update_data(base=base)
        await message.answer(t("enter_start_day", lang), parse_mode="Markdown")
        await state.set_state(Reg.start_day)
    except ValueError:
        await message.answer(t("enter_number", lang, example="130"))


@router.message(Reg.start_day)
async def reg_start_day(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    if not message.text:
        await message.answer(t("enter_number", lang, example="22"))
        return
    try:
        day = int(message.text.strip())
        conn = await get_db()
        await conn.execute(
            "INSERT INTO users (tg_id, username, first_name, base_pullups, start_day, weight_kg, lang, program_day) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (message.from_user.id,
             message.from_user.username or data.get("first_name"),
             data.get("first_name", message.from_user.first_name),
             data["base"], day, data["weight"], lang, day))
        await conn.commit()
        await state.clear()
        new_name = data.get("first_name", "атлет")
        await message.answer(
            t("welcome_user", lang,
              name=md_escape(new_name),
              base=data["base"], day=day,
              level=LEVEL_NAMES[0]),
            parse_mode="Markdown", reply_markup=main_kb(lang))
        # Notify all existing users about the new member
        await _broadcast_new_user(message.from_user.id, new_name)
    except ValueError:
        await message.answer(t("enter_number", lang, example="22"))


@router.callback_query(F.data.startswith("welcome_new:"))
async def welcome_new_user_callback(callback: types.CallbackQuery):
    raw = callback.data or ""
    try:
        target_tg_id = int(raw.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    sender = await get_user(callback.from_user.id)
    sender_lang = (sender["lang"] or "ru") if sender else "ru"
    if target_tg_id == callback.from_user.id:
        await callback.answer(t("welcome_greet_self", sender_lang), show_alert=True)
        return

    target = await get_user(target_tg_id)
    if not target:
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        await callback.answer(t("welcome_greet_missing", sender_lang), show_alert=True)
        return

    inserted = await add_welcome_greeting(callback.from_user.id, target_tg_id)
    target_name = display(target)
    if not inserted:
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        await callback.answer(
            t("welcome_greet_already", sender_lang, name=target_name),
            show_alert=True,
        )
        return

    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer(t("welcome_greet_sent", sender_lang, name=target_name))

    from ..main import bot
    target_lang = target["lang"] or "ru"
    sender_name = display(sender) if sender else (callback.from_user.first_name or "Участник")
    try:
        await bot.send_message(
            target_tg_id,
            t("welcome_greet_received", target_lang, name=sender_name),
        )
    except TelegramForbiddenError:
        pass
    except Exception:
        logger.exception(
            "[welcome] failed to notify new user: from=%s to=%s",
            callback.from_user.id,
            target_tg_id,
        )

    await callback.answer()


async def _broadcast_new_user(new_tg_id: int, name: str):
    from ..main import bot
    conn = await get_db()
    async with conn.execute("SELECT tg_id, lang FROM users WHERE tg_id != ?", (new_tg_id,)) as cur:
        others = await cur.fetchall()
    for u in others:
        try:
            ulang = u["lang"] or "ru"
            await bot.send_message(
                u["tg_id"],
                t("new_user_joined", ulang, name=md_escape(name)),
                parse_mode="Markdown",
                reply_markup=welcome_new_user_kb(name, new_tg_id, ulang),
            )
        except Exception:
            pass
