from aiogram import F, Router, types
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from datetime import date, timedelta

from ..config import LEVEL_NAMES, logger
from ..db import add_welcome_greeting, get_db, get_lang, get_user, is_permanently_banned
from ..i18n import t, text_filter
from ..keyboards import (LANG_EN_BTN, LANG_RU_BTN, LANG_TOGGLE_BTN,
                         about_kb, guide_kb, landing_kb, lang_kb,
                         logout_confirm_kb, main_kb, welcome_new_user_kb)
from ..states import About, Guide, Login, Logout, Reg
from ..services.xp import display, md_escape

router = Router()


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Clear any active FSM state and confirm the cancellation to the user."""
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
    """Clear state and return to the landing/welcome screen."""
    await state.clear()
    user = await get_user(message.from_user.id)
    lang = (user["lang"] or "ru") if user else "ru"
    await message.answer(t("welcome", lang), parse_mode="Markdown", reply_markup=landing_kb(lang))


@router.message(StateFilter(None), text_filter("btn_back"))
async def back_handler(message: types.Message, state: FSMContext):
    """Clear state and return the user to their appropriate main menu (logged-in or landing)."""
    await state.clear()
    lang = await get_lang(message.from_user.id)
    user = await get_user(message.from_user.id)
    if user:
        await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))
    else:
        await message.answer(t("main_menu", lang), reply_markup=landing_kb(lang))


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Handle /start: send the welcome screen for existing users or the language picker for new ones."""
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
    """Save the chosen language and show the landing screen."""
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
    """Show the first About page and start the About pager flow."""
    user = await get_user(message.from_user.id)
    data = await state.get_data()
    lang = (user["lang"] or "ru") if user else data.get("lang", "ru")
    await state.set_state(About.page2)
    await state.update_data(about_lang=lang)
    await message.answer(t("about", lang), parse_mode="Markdown",
                         reply_markup=about_kb("page1", lang))


@router.message(About.page2, text_filter("btn_about_next"))
async def about_page2(message: types.Message, state: FSMContext):
    """Advance to About page 2."""
    data = await state.get_data()
    lang = data.get("about_lang", "ru")
    await state.set_state(About.page3)
    await message.answer(t("about_page2", lang), parse_mode="Markdown",
                         reply_markup=about_kb("page2", lang))


@router.message(About.page3, text_filter("btn_about_next"))
async def about_page3(message: types.Message, state: FSMContext):
    """Show About page 3 (last page) and return to the landing keyboard."""
    data = await state.get_data()
    lang = data.get("about_lang", "ru")
    await state.clear()
    await message.answer(t("about_page3", lang), parse_mode="Markdown",
                         reply_markup=landing_kb(lang))


@router.message(StateFilter(About.page2, About.page3), text_filter("btn_back"))
async def about_back(message: types.Message, state: FSMContext):
    """Exit the About flow and return to the landing screen."""
    data = await state.get_data()
    lang = data.get("about_lang", "ru")
    await state.clear()
    await message.answer(t("main_menu", lang), reply_markup=landing_kb(lang))


@router.message(text_filter("btn_guide"))
async def guide_handler(message: types.Message, state: FSMContext):
    """Show the guide intro page and enter the step-by-step guide flow."""
    user = await get_user(message.from_user.id)
    data = await state.get_data()
    lang = (user["lang"] or "ru") if user else data.get("lang", "ru")
    await state.set_state(Guide.step1)
    await state.update_data(guide_lang=lang)
    await message.answer(t("guide_intro", lang), parse_mode="Markdown",
                         reply_markup=guide_kb("intro", lang))


@router.message(Guide.step1, text_filter("btn_guide_step1"))
async def guide_step1(message: types.Message, state: FSMContext):
    """Advance the guide to step 1 (registration)."""
    data = await state.get_data()
    lang = data.get("guide_lang", "ru")
    await state.set_state(Guide.step2)
    await message.answer(t("guide_step1", lang), parse_mode="Markdown",
                         reply_markup=guide_kb("step1", lang))


@router.message(Guide.step2, text_filter("btn_guide_step2"))
async def guide_step2(message: types.Message, state: FSMContext):
    """Advance the guide to step 2 (the wave cycle)."""
    data = await state.get_data()
    lang = data.get("guide_lang", "ru")
    await state.set_state(Guide.step3)
    await message.answer(t("guide_step2", lang), parse_mode="Markdown",
                         reply_markup=guide_kb("step2", lang))


@router.message(Guide.step3, text_filter("btn_guide_step3"))
async def guide_step3(message: types.Message, state: FSMContext):
    """Advance the guide to step 3 (XP and streaks)."""
    data = await state.get_data()
    lang = data.get("guide_lang", "ru")
    await state.set_state(Guide.step4)
    await message.answer(t("guide_step3", lang), parse_mode="Markdown",
                         reply_markup=guide_kb("step3", lang))


@router.message(Guide.step4, text_filter("btn_guide_step4"))
async def guide_step4(message: types.Message, state: FSMContext):
    """Advance the guide to step 4 (tips and AI)."""
    data = await state.get_data()
    lang = data.get("guide_lang", "ru")
    await state.set_state(Guide.extra)
    await message.answer(t("guide_step4", lang), parse_mode="Markdown",
                         reply_markup=guide_kb("step4", lang))


@router.message(Guide.extra, text_filter("btn_guide_extra"))
async def guide_extra(message: types.Message, state: FSMContext):
    """Show the extra tips page and finish the guide flow."""
    data = await state.get_data()
    lang = data.get("guide_lang", "ru")
    await state.clear()
    await message.answer(t("guide_extra", lang), parse_mode="Markdown",
                         reply_markup=landing_kb(lang))


@router.message(StateFilter(Guide.step1, Guide.step2, Guide.step3, Guide.step4, Guide.extra),
                text_filter("btn_back"))
async def guide_back(message: types.Message, state: FSMContext):
    """Exit the guide flow and return to the landing screen."""
    data = await state.get_data()
    lang = data.get("guide_lang", "ru")
    await state.clear()
    await message.answer(t("main_menu", lang), reply_markup=landing_kb(lang))


@router.message(text_filter("btn_exit"))
async def exit_btn(message: types.Message, state: FSMContext):
    """Handle the Exit button: prompt for logout confirmation if logged in, or farewell if not."""
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
    """Handle Join button: re-activate a logged-out user or start the registration flow for new users."""
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
        if await is_permanently_banned(message.from_user.id):
            await state.clear()
            await message.answer("⛔ Ваш аккаунт был удалён. Регистрация невозможна."
                                 if lang == "ru" else
                                 "⛔ Your account was deleted. Registration is not possible.")
            return
        await message.answer(t("code_accepted", lang), parse_mode="Markdown",
                             reply_markup=ReplyKeyboardRemove())
        await state.set_state(Reg.name)


@router.message(Reg.name)
async def reg_name(message: types.Message, state: FSMContext):
    """Validate and save the registration name (minimum 3 chars), then ask for max pullups."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    name = (message.text or "").strip()
    if len(name) < 3:
        prompt = "❌ Минимум 3 символа. Как тебя зовут?" if lang == "ru" else "❌ At least 3 characters. What's your name?"
        await message.answer(prompt)
        return
    await state.update_data(first_name=name)
    await message.answer(t("hello_name", lang, name=md_escape(name)), parse_mode="Markdown")
    await state.set_state(Reg.max_pullups)


@router.message(Reg.max_pullups)
async def reg_max_pullups(message: types.Message, state: FSMContext):
    """Validate max pullups (1–200), create the user row, and broadcast the new arrival."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    if not message.text:
        await message.answer(t("enter_number", lang, example="10"))
        return
    try:
        max_reps = int(message.text.strip())
        if not (1 <= max_reps <= 200):
            await message.answer(t("enter_number", lang, example="10"))
            return
        base = max(5, max_reps * 3)
        conn = await get_db()
        await conn.execute(
            "INSERT INTO users (tg_id, username, first_name, base_pullups, start_day, lang, program_day) "
            "VALUES (?,?,?,?,?,?,?)",
            (message.from_user.id,
             message.from_user.username or data.get("first_name"),
             data.get("first_name", message.from_user.first_name),
             base, 0, lang, 0))
        await conn.commit()
        await state.clear()
        new_name = data.get("first_name", "атлет")
        await message.answer(
            t("welcome_user", lang,
              name=md_escape(new_name),
              max_pullups=max_reps,
              base=base,
              level=LEVEL_NAMES[0]),
            parse_mode="Markdown", reply_markup=main_kb(lang))
        await _broadcast_new_user(message.from_user.id, new_name)
    except ValueError:
        await message.answer(t("enter_number", lang, example="10"))


@router.callback_query(F.data.startswith("welcome_new:"))
async def welcome_new_user_callback(callback: types.CallbackQuery):
    """Handle a user clicking Welcome for a new member: register the greeting and notify both parties."""
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
    """Notify all existing users that a new member joined, with a one-time Welcome inline button."""
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
        except Exception as e:
            logger.debug(f"[broadcast_new_user] {u['tg_id']}: {e}")
