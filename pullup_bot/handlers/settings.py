from datetime import date

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..db import (add_xp, get_db, get_lang, get_today_workout, get_user,
                  upsert_workout)
from ..i18n import t, text_filter
from ..keyboards import (LANG_BACK_BILINGUAL, LANG_EN_BTN, LANG_RU_BTN, LANG_TOGGLE_BTN,
                         delete_confirm_kb, landing_kb, lang_kb,
                         logout_confirm_kb, main_kb, parse_rpe, rpe_menu_kb,
                         settings_kb, skip_reason_kb)
from aiogram.filters import StateFilter
from ..states import (DeleteAccount, EditDay, Logout, SetBase, SetNotify, SetWeight,
                      Settings, SkipReason)

_INPUT_STATES = (
    SetNotify.enter_time,
    SetBase.enter_base,
    SetWeight.enter_weight,
    EditDay.pick_date, EditDay.pick_done, EditDay.pick_rpe,
    SkipReason.pick_date, SkipReason.enter_reason,
)
from ..services.xp import level_info
from ..config import XP_PER_PULLUP

router = Router()


@router.message(StateFilter(*_INPUT_STATES), text_filter("btn_back"))
async def settings_input_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))


@router.message(Settings.viewing, text_filter("btn_back"))
async def settings_back(message: types.Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))


@router.message(text_filter("btn_settings"))
async def settings_menu(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    lang = user["lang"] or "ru"
    await state.set_state(Settings.viewing)
    await message.answer(
        t("settings_title", lang,
          base=user["base_pullups"], weight=user["weight_kg"],
          notify=user["notify_time"], freeze=user["freeze_tokens"]),
        parse_mode="Markdown", reply_markup=settings_kb(lang))


@router.message(text_filter("btn_logout"))
async def account_logout_msg(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("confirm_logout", lang), reply_markup=logout_confirm_kb(lang))
    await state.set_state(Logout.confirm)


@router.message(Logout.confirm, text_filter("confirm_yes"))
async def logout_confirm(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    conn = await get_db()
    await conn.execute("UPDATE users SET is_logged_out=1 WHERE tg_id=?", (message.from_user.id,))
    await conn.commit()
    await state.clear()
    await message.answer(t("bye", lang), reply_markup=landing_kb(lang))


@router.message(Logout.confirm, text_filter("confirm_no"))
async def logout_cancel(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.clear()
    await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))


@router.message(text_filter("btn_delete_account"))
async def delete_account_start(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("delete_account_warning", lang),
                         parse_mode="Markdown", reply_markup=delete_confirm_kb(lang))
    await state.set_state(DeleteAccount.confirm)


@router.message(DeleteAccount.confirm, text_filter("delete_confirm_yes"))
async def delete_account_confirm(message: types.Message, state: FSMContext):
    from ..keyboards import lang_kb
    lang = await get_lang(message.from_user.id)
    user = await get_user(message.from_user.id)
    if user:
        conn = await get_db()
        await conn.execute("DELETE FROM workouts WHERE user_id=?", (user["id"],))
        await conn.execute("DELETE FROM friends WHERE user_id=? OR friend_id=?",
                           (user["id"], user["id"]))
        await conn.execute("DELETE FROM streak_recoveries WHERE user_id=?", (user["id"],))
        await conn.execute("DELETE FROM bug_reports WHERE user_id=?", (user["id"],))
        await conn.execute("DELETE FROM users WHERE id=?", (user["id"],))
        await conn.commit()
    from aiogram.types import ReplyKeyboardRemove
    await state.clear()
    await message.answer(t("delete_account_done", lang), reply_markup=ReplyKeyboardRemove())


@router.message(DeleteAccount.confirm, text_filter("delete_confirm_no"))
async def delete_account_cancel(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    user = await get_user(message.from_user.id)
    await state.clear()
    if not user:
        await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))
        return
    await message.answer(
        t("settings_title", lang,
          base=user["base_pullups"], weight=user["weight_kg"],
          notify=user["notify_time"], freeze=user["freeze_tokens"]),
        parse_mode="Markdown", reply_markup=settings_kb(lang))


@router.message(text_filter("btn_notify_time"))
async def set_notify_msg(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    lang = (user["lang"] or "ru") if user else "ru"
    current = (user["notify_time"] or "—") if user else "—"
    await message.answer(t("set_time_prompt", lang, current=current), parse_mode="Markdown")
    await state.set_state(SetNotify.enter_time)


@router.message(text_filter("btn_change_base"))
async def set_base_start_msg(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    lang = user["lang"] or "ru"
    await message.answer(t("set_base_prompt", lang, base=user["base_pullups"]),
                         parse_mode="Markdown")
    await state.set_state(SetBase.enter_base)


@router.message(text_filter("btn_change_weight"))
async def set_weight_start_msg(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    lang = user["lang"] or "ru"
    await message.answer(t("set_weight_prompt", lang, weight=user["weight_kg"]),
                         parse_mode="Markdown")
    await state.set_state(SetWeight.enter_weight)


@router.message(text_filter("btn_edit_day"))
async def edit_day_btn_msg(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("edit_date_prompt", lang),
                         parse_mode="Markdown")
    await state.set_state(EditDay.pick_date)


@router.message(text_filter("btn_skip_reason"))
async def skip_reason_start_msg(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("skip_date_prompt", lang),
                         parse_mode="Markdown")
    await state.set_state(SkipReason.pick_date)


@router.message(text_filter("btn_language"))
async def language_menu(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("lang_prompt", lang), reply_markup=lang_kb(show_back=True))
    await state.set_state(Settings.pick_lang)


@router.message(Settings.pick_lang, F.text == LANG_BACK_BILINGUAL)
@router.message(Settings.pick_lang, text_filter("btn_back"))
async def language_back(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    user = await get_user(message.from_user.id)
    await state.clear()
    await message.answer(
        t("settings_title", lang,
          base=user["base_pullups"], weight=user["weight_kg"],
          notify=user["notify_time"], freeze=user["freeze_tokens"]),
        parse_mode="Markdown", reply_markup=settings_kb(lang))


@router.message(Settings.pick_lang, F.text.in_({LANG_RU_BTN, LANG_EN_BTN, LANG_TOGGLE_BTN}))
async def set_lang_toggle(message: types.Message, state: FSMContext):
    if message.text == LANG_RU_BTN:
        new_lang = "ru"
    elif message.text == LANG_EN_BTN:
        new_lang = "en"
    else:
        current_lang = await get_lang(message.from_user.id)
        new_lang = "en" if current_lang == "ru" else "ru"
    conn = await get_db()
    await conn.execute("UPDATE users SET lang=? WHERE tg_id=?", (new_lang, message.from_user.id))
    await conn.commit()
    await state.clear()
    await message.answer(t("lang_ok", new_lang), reply_markup=main_kb(new_lang))


@router.message(SetNotify.enter_time)
async def save_notify_time(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text:
        await message.answer(t("set_time_bad", lang))
        return
    time_str = message.text.strip()
    try:
        h, m = map(int, time_str.split(":"))
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError("invalid time")
        conn = await get_db()
        await conn.execute("UPDATE users SET notify_time=? WHERE tg_id=?",
                           (time_str, message.from_user.id))
        await conn.commit()
        await message.answer(t("set_time_ok", lang, time=time_str), parse_mode="Markdown")
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))
    except Exception:
        await message.answer(t("set_time_bad", lang))


@router.message(SetBase.enter_base)
async def set_base_save(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text:
        await message.answer(t("set_base_range", lang))
        return
    try:
        text = message.text.strip()
        if len(text) > 5:
            await message.answer(t("set_base_range", lang))
            return
        base = int(text)
        if base < 1 or base > 500:
            await message.answer(t("set_base_range", lang))
            return
        conn = await get_db()
        await conn.execute("UPDATE users SET base_pullups=? WHERE tg_id=?",
                           (base, message.from_user.id))
        await conn.commit()
        await message.answer(t("set_base_ok", lang, base=base), parse_mode="Markdown")
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))
    except ValueError:
        await message.answer(t("set_base_range", lang))


@router.message(SetWeight.enter_weight)
async def set_weight_save(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text:
        await message.answer(t("set_weight_range", lang))
        return
    try:
        import re
        text = re.sub(r'(?i)\s*к?г\w*$|\s*kg\w*$', '', message.text.strip()).strip()
        if len(text) > 8:
            await message.answer(t("set_weight_range", lang))
            return
        weight = float(text.replace(",", "."))
        if weight < 30 or weight > 300:
            await message.answer(t("set_weight_range", lang))
            return
        conn = await get_db()
        await conn.execute("UPDATE users SET weight_kg=? WHERE tg_id=?",
                           (weight, message.from_user.id))
        await conn.commit()
        await message.answer(t("set_weight_ok", lang, weight=weight), parse_mode="Markdown")
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))
    except ValueError:
        await message.answer(t("set_weight_range", lang))


@router.message(Command("edit"))
async def edit_day_start(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("edit_date_prompt", lang), parse_mode="Markdown")
    await state.set_state(EditDay.pick_date)


@router.message(EditDay.pick_date)
async def edit_pick_date(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text:
        await message.answer(t("edit_date_bad", lang))
        return
    try:
        day, month = map(int, message.text.strip().split("."))
        d = date(date.today().year, month, day)
        if d > date.today():
            d = date(date.today().year - 1, month, day)
        await state.update_data(edit_date=d.isoformat())
        await message.answer(
            t("edit_done_prompt", lang, date=message.text.strip()),
            parse_mode="Markdown")
        await state.set_state(EditDay.pick_done)
    except Exception:
        await message.answer(t("edit_date_bad", lang))


@router.message(EditDay.pick_done)
async def edit_pick_done(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text:
        await message.answer(t("enter_number", lang, example="50"))
        return
    try:
        done = int(message.text.strip())
        await state.update_data(edit_done=done)
        await message.answer(t("edit_rpe_prompt", lang), reply_markup=rpe_menu_kb(lang))
        await state.set_state(EditDay.pick_rpe)
    except ValueError:
        await message.answer(t("enter_number", lang, example="50"))


@router.message(EditDay.pick_rpe)
async def edit_pick_rpe(message: types.Message, state: FSMContext):
    rpe = parse_rpe(message.text or "")
    if rpe is None:
        lang = await get_lang(message.from_user.id)
        await message.answer(t("train_rpe_invalid", lang), reply_markup=rpe_menu_kb(lang))
        return
    data = await state.get_data()
    user = await get_user(message.from_user.id)
    lang = user["lang"] or "ru" if user else "ru"
    d = data.get("edit_date")
    done = data.get("edit_done", 0)
    if not d:
        await message.answer(t("edit_no_date", lang))
        await state.clear()
        return
    existing = await get_today_workout(user["id"], d)
    if existing:
        planned = existing["planned"] or user["base_pullups"]
        day_type = existing["day_type"] or "Средний"
    else:
        planned = user["base_pullups"]
        day_type = "Средний"
    old = existing["completed"] if existing else 0
    xp_diff = (done - old) * XP_PER_PULLUP
    await upsert_workout(user["id"], d, completed=done, planned=planned, day_type=day_type, rpe=rpe)
    if xp_diff != 0:
        await add_xp(message.from_user.id, xp_diff)
    await message.answer(
        t("edit_ok", lang, date=date.fromisoformat(d).strftime("%d.%m.%Y"), done=done, rpe=rpe),
        parse_mode="Markdown")
    await state.clear()
    await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))



@router.message(SkipReason.pick_date)
async def skip_reason_date(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if not message.text:
        await message.answer(t("edit_date_bad", lang))
        return
    try:
        day, month = map(int, message.text.strip().split("."))
        d = date(date.today().year, month, day)
        if d > date.today():
            d = date(date.today().year - 1, month, day)
        if (date.today() - d).days > 3:
            await message.answer(t("skip_date_range", lang))
            return
        await state.update_data(skip_date=d.isoformat())
        await message.answer(t("skip_choose_reason", lang), reply_markup=skip_reason_kb(lang))
        await state.set_state(SkipReason.enter_reason)
    except Exception:
        await message.answer(t("edit_date_bad", lang))


@router.message(SkipReason.enter_reason)
async def skip_reason_save(message: types.Message, state: FSMContext):
    reason = message.text or ""
    data = await state.get_data()
    user = await get_user(message.from_user.id)
    lang = user["lang"] or "ru" if user else "ru"
    d = data.get("skip_date")
    if not d:
        await message.answer(t("edit_no_date", lang))
        await state.clear()
        return
    conn = await get_db()
    async with conn.execute("SELECT id FROM streak_recoveries WHERE user_id=? AND date=?",
                            (user["id"], d)) as cur:
        existing = await cur.fetchone()
    if existing:
        await conn.execute("UPDATE streak_recoveries SET reason=? WHERE id=?",
                           (reason, existing[0]))
    else:
        await conn.execute("INSERT INTO streak_recoveries (user_id, date, reason) VALUES (?,?,?)",
                           (user["id"], d, reason))
        await conn.execute("UPDATE users SET streak = streak + 1 WHERE id=?", (user["id"],))
    await conn.commit()
    await message.answer(
        t("skip_ok", lang, date=date.fromisoformat(d).strftime("%d.%m.%Y"), reason=reason),
        parse_mode="Markdown")
    await state.clear()
    await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))


