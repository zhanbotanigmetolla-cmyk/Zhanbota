import asyncio
import json
from datetime import date, timedelta

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from ..config import XP_PER_PULLUP, logger
from ..db import (add_xp, get_db, get_lang, get_today_workout, get_user,
                  update_streak, upsert_workout)
from ..i18n import t, text_filter, day_name
from ..keyboards import (activity_reply_kb, back_only_kb, cancel_confirm_kb, freeze_confirm_kb,
                         main_kb, parse_rpe, rest_day_kb, rpe_menu_kb, training_kb)
from ..states import Training
from ..services.xp import (activity_reduction, display, level_info, md_escape,
                            planned_for_day, progress_bar)

router = Router()

# Per-user locks to prevent duplicate processing when messages arrive in rapid succession
_user_locks: dict[int, asyncio.Lock] = {}


def _days_since_last(user) -> int:
    """Return days since last recorded workout, or 999 if never."""
    if not user["last_workout"]:
        return 999
    try:
        return (date.today() - date.fromisoformat(user["last_workout"])).days
    except Exception:
        return 999


async def _mark_rest_day_if_missing(user_id: int, today_str: str):
    """Persist a rest-day row so today's plan stays consistent across screens."""
    existing = await get_today_workout(user_id, today_str)
    if existing:
        return
    await upsert_workout(
        user_id,
        today_str,
        planned=0,
        day_type="Отдых",
        sets_json=json.dumps([]),
        completed=0,
    )


@router.message(text_filter("btn_train"))
async def start_training(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return

    lang = user["lang"] or "ru"
    today_str = date.today().isoformat()
    existing_today = await get_today_workout(user["id"], today_str)
    if existing_today:
        # Keep today's saved plan/day type stable if the user re-enters training.
        planned = existing_today["planned"] or 0
        day_type = existing_today["day_type"] or planned_for_day(user)[1]
    else:
        planned, day_type = planned_for_day(user)
    days_off = _days_since_last(user)

    # If user has been off 3+ days and today is a rest day, skip the rest prompt
    # and start a light session instead — they've already rested enough
    if day_type == "Отдых" and days_off >= 3:
        note = (f"ℹ️ _Ты не тренировался {days_off} дней, поэтому день отдыха пропускается. Начинаем лёгкую тренировку._\n\n"
                if lang == "ru" else
                f"ℹ️ _You haven't trained for {days_off} days, so the rest day is skipped. Starting a light session._\n\n")
        day_type = "Лёгкий"
        planned = int(user["base_pullups"] * 0.7)
        await message.answer(note, parse_mode="Markdown")
        await _begin_training(message, state, user, lang, today_str, planned, day_type)
        return

    # Rest day override (normal case)
    if day_type == "Отдых":
        await message.answer(t("rest_day_prompt", lang), reply_markup=rest_day_kb(lang))
        await state.update_data(rest_day_lang=lang)
        await state.set_state(Training.rest_day)
        return

    # After a long break (3+ days), reduce load and warn
    if days_off >= 3 and days_off < 999:
        reduction = 0.6 if days_off >= 7 else 0.75
        planned = int(planned * reduction)
        break_note = (f"⚠️ _Перерыв {days_off} дн. — нагрузка снижена до {int(reduction*100)}% для плавного возвращения._\n\n"
                      if lang == "ru" else
                      f"⚠️ _Break of {days_off} days — load reduced to {int(reduction*100)}% for a smooth return._\n\n")
        await message.answer(break_note, parse_mode="Markdown")

    await _begin_training(message, state, user, lang, today_str, planned, day_type)


@router.message(Training.rest_day, text_filter("rest_day_train"))
async def rest_override_train(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await state.clear()
        await message.answer(t("register_first", "ru"))
        return
    lang = user["lang"] or "ru"
    today = date.today()
    today_str = today.isoformat()
    day_type = "Средний"
    planned = int(user["base_pullups"] * 1.0)
    await _begin_training(message, state, user, lang, today_str, planned, day_type)


@router.message(Training.rest_day, text_filter("rest_day_rest"))
async def rest_override_rest(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("rest_day_lang", "ru")
    user = await get_user(message.from_user.id)
    if user:
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        # Check if streak would break (last workout was not yesterday or today)
        streak_breaks = (user["last_workout"] != today and user["last_workout"] != yesterday
                         and user["streak"] > 0)
        if streak_breaks and (user["freeze_tokens"] or 0) > 0:
            await state.update_data(rest_day_advancing=True)
            await state.set_state(Training.freeze_confirm)
            await message.answer(
                t("freeze_prompt", lang, tokens=user["freeze_tokens"]),
                reply_markup=freeze_confirm_kb(lang))
            return
        # Advance program_day for rest day acknowledgement
        if user["last_workout"] != today:
            conn = await get_db()
            new_pd = (user["program_day"] or 0) + 1
            await conn.execute(
                "UPDATE users SET program_day=?, last_workout=? WHERE tg_id=?",
                (new_pd, today, message.from_user.id)
            )
            await conn.commit()
        await _mark_rest_day_if_missing(user["id"], today)
    await state.clear()
    await message.answer(t("reminder_rest", lang), reply_markup=main_kb(lang))


@router.message(Training.freeze_confirm, text_filter("freeze_yes_btn"))
async def freeze_yes(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("rest_day_lang", "ru")
    user = await get_user(message.from_user.id)
    if not user:
        await state.clear()
        return
    today = date.today().isoformat()
    conn = await get_db()
    new_tokens = max(0, (user["freeze_tokens"] or 0) - 1)
    new_streak = (user["streak"] or 0) + 1
    await conn.execute(
        "UPDATE users SET freeze_tokens=?, streak=?, last_workout=? WHERE tg_id=?",
        (new_tokens, new_streak, today, message.from_user.id)
    )
    await conn.execute(
        "INSERT INTO streak_recoveries (user_id, date, reason) VALUES (?,?,?)",
        (user["id"], today, "freeze")
    )
    # Advance program_day
    new_pd = (user["program_day"] or 0) + 1
    await conn.execute("UPDATE users SET program_day=? WHERE tg_id=?",
                       (new_pd, message.from_user.id))
    await conn.commit()
    await _mark_rest_day_if_missing(user["id"], today)
    await state.clear()
    await message.answer(t("freeze_used", lang, streak=new_streak, tokens=new_tokens),
                         parse_mode="Markdown", reply_markup=main_kb(lang))


@router.message(Training.freeze_confirm, text_filter("freeze_no_btn"))
async def freeze_no(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("rest_day_lang", "ru")
    user = await get_user(message.from_user.id)
    if user:
        today = date.today().isoformat()
        conn = await get_db()
        new_pd = (user["program_day"] or 0) + 1
        await conn.execute(
            "UPDATE users SET program_day=?, last_workout=?, streak=0 WHERE tg_id=?",
            (new_pd, today, message.from_user.id)
        )
        await conn.commit()
        await _mark_rest_day_if_missing(user["id"], today)
    await state.clear()
    await message.answer(t("reminder_rest", lang), reply_markup=main_kb(lang))


async def _begin_training(message, state, user, lang, today_str, planned, day_type, tg_id=None):
    if tg_id is None:
        tg_id = user["tg_id"]
    today = date.fromisoformat(today_str)
    yesterday_str = (today - timedelta(days=1)).isoformat()
    yesterday_w = await get_today_workout(user["id"], yesterday_str)
    reduction = 1.0
    if yesterday_w and yesterday_w["extra_activity"]:
        reduction = activity_reduction(yesterday_w["extra_activity"], yesterday_w["extra_minutes"])
        planned = int(planned * reduction)

    existing = await get_today_workout(user["id"], today_str)
    done_today = existing["completed"] if existing else 0
    session_sets: list = []
    done_before = done_today

    if existing:
        # Restore planned only if the stored value is non-zero (rest days store planned=0;
        # overriding a rest day passes base_pullups which we must not lose).
        if existing["planned"]:
            planned = existing["planned"]
        # Do NOT restore day_type from DB — the caller already computed it correctly,
        # and overwriting here would revert a rest-day override back to "Отдых".
    else:
        await upsert_workout(user["id"], today_str, planned=planned, day_type=day_type,
                             sets_json=json.dumps([]), completed=0)

    reduction_note = (f"\n{t('train_reduction', lang, pct=int((1 - reduction) * 100))}"
                      if reduction < 1 else "")
    await state.set_state(Training.active)
    await state.update_data(date=today_str, planned=planned, sets=session_sets,
                            done_before=done_before, lang=lang)

    day_display = day_name(day_type, lang)
    em = "🟢" if day_type != "Отдых" else "😴"
    density_note = ("\n\n" + t("density_hint", lang)) if day_type == "Плотность" else ""
    hint = "\n_Нажми на число или введи вручную:_" if lang == "ru" else "\n_Tap a number or enter manually:_"
    await message.answer(
        f"{em} *{day_display}*\n\n"
        f"{t('train_goal', lang, planned=planned)}{reduction_note}\n"
        f"{t('train_done_today', lang, done=done_today)}\n"
        f"{t('train_done_now', lang, done=0)}"
        f"{density_note}{hint}",
        parse_mode="Markdown", reply_markup=training_kb(session_sets, planned, lang))


async def _training_status(message: types.Message, state: FSMContext):
    data = await state.get_data()
    sets = data.get("sets", [])
    lang = data.get("lang", "ru")
    done_now = sum(sets)
    done_before = data.get("done_before", 0)
    done_today = done_before + done_now
    planned = data.get("planned", 0)
    pct = int(done_today / planned * 100) if planned else 0
    bar = progress_bar(min(100, pct))
    pd = f"🔥{pct}%" if pct > 100 else f"{pct}%"
    today_line = f"За сегодня: *{done_today}* / {planned}" if lang == "ru" else f"Today: *{done_today}* / {planned}"
    sets_line = f"Подходов: {len(sets)}" if lang == "ru" else f"Sets: {len(sets)}"
    sets_display = ", ".join(str(s) for s in sets) if sets else "—"
    last_line = f"Подходы: {sets_display}" if lang == "ru" else f"Sets: {sets_display}"
    await message.answer(
        f"{t('train_in_progress', lang)}\n\n"
        f"{t('train_done_now', lang, done=done_now)}\n"
        f"✅ {today_line}\n"
        f"[{bar}] {pd}\n"
        f"📦 {sets_line}\n"
        f"{last_line}",
        parse_mode="Markdown", reply_markup=training_kb(sets, planned, lang))


@router.message(text_filter("btn_undo"), Training.active)
async def undo_set(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    sets = data.get("sets", [])
    if not sets:
        await message.answer(t("train_no_sets", lang))
        return
    sets.pop()
    await state.update_data(sets=sets)
    await _training_status(message, state)


@router.message(text_filter("btn_manual"), Training.active)
async def prompt_custom_set(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await message.answer(t("train_enter_reps", lang))


@router.message(text_filter("btn_finish"), Training.active)
async def finish_training_btn(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await message.answer(t("train_rate_rpe", lang), reply_markup=rpe_menu_kb(lang))
    await state.set_state(Training.rpe)


@router.message(text_filter("btn_back"), Training.rpe)
async def rpe_back(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    sets = data.get("sets", [])
    planned = data.get("planned", 0)
    await state.set_state(Training.active)
    await message.answer(t("train_lets_go", lang), reply_markup=training_kb(sets, planned, lang))


async def _cleanup_cancelled_workout(tg_id: int, state_data: dict):
    """Delete or restore workout record when training is cancelled."""
    done_before = state_data.get("done_before", 0)
    d = state_data.get("date", date.today().isoformat())
    user = await get_user(tg_id)
    if not user:
        return
    if done_before == 0:
        # No prior progress — delete the ghost record entirely
        conn = await get_db()
        await conn.execute(
            "DELETE FROM workouts WHERE user_id=? AND date=?",
            (user["id"], d)
        )
        await conn.commit()
    # If done_before > 0, the DB record still holds the previous completed value — no action needed


@router.message(text_filter("btn_cancel_train"), Training.active)
async def cancel_training_btn(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    sets = data.get("sets", [])
    done = sum(sets)
    if done == 0:
        await _cleanup_cancelled_workout(message.from_user.id, data)
        await state.clear()
        await message.answer(t("train_cancelled", lang), reply_markup=main_kb(lang))
        return
    await message.answer(
        t("train_confirm_cancel", lang, done=done, sets=len(sets)),
        parse_mode="Markdown", reply_markup=cancel_confirm_kb(lang))
    await state.set_state(Training.cancel_confirm)


@router.message(Training.cancel_confirm, text_filter("train_yes_cancel"))
async def cancel_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await _cleanup_cancelled_workout(message.from_user.id, data)
    await state.clear()
    await message.answer(t("train_cancelled", lang), reply_markup=main_kb(lang))


@router.message(Training.cancel_confirm, text_filter("train_continue"))
async def cancel_back_msg(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    sets = data.get("sets", [])
    planned = data.get("planned", 0)
    await state.set_state(Training.active)
    await message.answer(t("train_lets_go", lang), reply_markup=training_kb(sets, planned, lang))


@router.message(Training.active, F.text.regexp(r"^\s*\d+\s*$"))
async def custom_set_input(message: types.Message, state: FSMContext):
    reps = int(message.text.strip())
    if reps < 1 or reps > 500:
        data = await state.get_data()
        lang = data.get("lang", "ru")
        await message.answer(t("enter_number", lang, example="10"))
        return
    data = await state.get_data()
    sets = data.get("sets", [])
    sets.append(reps)
    await state.update_data(sets=sets)
    await _training_status(message, state)


@router.message(Training.rpe)
async def set_rpe_msg(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in _user_locks:
        _user_locks[uid] = asyncio.Lock()
    if _user_locks[uid].locked():
        return  # duplicate rapid message — drop silently
    async with _user_locks[uid]:
        # Re-check state in case a concurrent message already advanced it
        current_state = await state.get_state()
        if current_state != Training.rpe:
            return
        data = await state.get_data()
        lang = data.get("lang", "ru")
        rpe = parse_rpe(message.text or "")
        if rpe is None:
            await message.answer(t("train_rpe_invalid", lang), reply_markup=rpe_menu_kb(lang))
            return
        await state.update_data(rpe=rpe)
        await message.answer(t("train_extra_activity", lang),
                             parse_mode="Markdown", reply_markup=activity_reply_kb(lang))
        await state.set_state(Training.activity)


_ACTIVITY_MAP = {
    "🏃 Бег/Кардио": "бег", "🏃 Running/Cardio": "бег",
    "🏋️ Зал": "зал", "🏋️ Gym": "зал",
    "⏭️ Пропустить": "skip", "⏭️ Skip": "skip",
}


async def _prompt_notes(message, state, lang):
    from aiogram.types import KeyboardButton
    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=t("train_skip_notes", lang)))
    b.row(KeyboardButton(text=t("btn_back", lang)))
    await message.answer(t("train_notes_prompt", lang), parse_mode="Markdown",
                         reply_markup=b.as_markup(resize_keyboard=True, one_time_keyboard=True))
    await state.set_state(Training.notes)


@router.message(text_filter("btn_back"), Training.activity)
async def activity_back(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.set_state(Training.rpe)
    await message.answer(t("train_rate_rpe", lang), reply_markup=rpe_menu_kb(lang))


@router.message(Training.activity)
async def set_activity(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    act_val = _ACTIVITY_MAP.get(message.text or "", "skip")
    if act_val == "skip":
        await state.update_data(activity="", act_mins=0)
        await _prompt_notes(message, state, lang)
    else:
        await state.update_data(activity=act_val)
        await message.answer(t("train_how_long", lang, act=act_val), parse_mode="Markdown",
                             reply_markup=back_only_kb(lang))
        await state.set_state(Training.act_mins)


@router.message(text_filter("btn_back"), Training.act_mins)
async def act_mins_back(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.set_state(Training.activity)
    await message.answer(t("train_extra_activity", lang), parse_mode="Markdown",
                         reply_markup=activity_reply_kb(lang))


@router.message(Training.act_mins)
async def set_act_mins(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    if not message.text:
        await message.answer(t("train_enter_mins", lang))
        return
    try:
        mins = int(message.text.strip())
        await state.update_data(act_mins=mins)
        await _prompt_notes(message, state, lang)
    except ValueError:
        await message.answer(t("train_enter_mins", lang))


@router.message(text_filter("btn_back"), Training.notes)
async def notes_back(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.set_state(Training.activity)
    await message.answer(t("train_extra_activity", lang), parse_mode="Markdown",
                         reply_markup=activity_reply_kb(lang))


@router.message(Training.notes)
async def enter_notes(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    skip_text = t("train_skip_notes", lang)
    notes = "" if (message.text or "").strip() == skip_text else (message.text or "").strip()
    await state.update_data(notes=notes)
    processing_msg = await message.answer(t("train_saving", lang))
    await _save_workout(message, state, message.from_user.id, processing_msg)


async def _check_weekly_progression(tg_id: int, user_id: int, current_base: int):
    """After completing a 7-day cycle, bump base +5% if last 5 training days averaged ≥90%."""
    conn = await get_db()
    async with conn.execute(
        "SELECT completed, planned FROM workouts "
        "WHERE user_id=? AND planned > 0 ORDER BY date DESC LIMIT 5",
        (user_id,)
    ) as cur:
        rows = await cur.fetchall()
    if len(rows) < 5:
        return None
    avg = sum(r["completed"] / r["planned"] for r in rows if r["planned"] > 0) / len(rows)
    if avg >= 0.9:
        new_base = int(current_base * 1.05)
        await conn.execute("UPDATE users SET base_pullups=? WHERE tg_id=?", (new_base, tg_id))
        await conn.commit()
        return new_base
    return None


async def _apply_rpe_adjustment(tg_id: int, user_id: int, current_base: int):
    """Rolling average of last 3 RPE readings. Proportional adjustments both ways."""
    conn = await get_db()
    async with conn.execute(
        "SELECT rpe, completed, planned FROM workouts "
        "WHERE user_id=? AND rpe > 0 AND planned > 0 ORDER BY date DESC LIMIT 3",
        (user_id,)
    ) as cur:
        rows = await cur.fetchall()
    if len(rows) < 3:
        return None, None
    avg_rpe = sum(r["rpe"] for r in rows) / 3
    all_hit = all(r["completed"] >= r["planned"] for r in rows)
    if avg_rpe >= 8.5:
        new_base = max(10, int(current_base * 0.95))
        await conn.execute("UPDATE users SET base_pullups=? WHERE tg_id=?", (new_base, tg_id))
        await conn.commit()
        return new_base, avg_rpe
    if avg_rpe <= 4.5 and all_hit:
        new_base = int(current_base * 1.03)
        await conn.execute("UPDATE users SET base_pullups=? WHERE tg_id=?", (new_base, tg_id))
        await conn.commit()
        return new_base, avg_rpe
    return None, None


async def _save_workout(msg, state: FSMContext, tg_id: int, processing_msg=None):
    if processing_msg:
        try:
            await processing_msg.delete()
        except Exception:
            pass
    data = await state.get_data()
    sets = data.get("sets", [])
    lang = data.get("lang", "ru")
    done_now = sum(sets)
    done_before = data.get("done_before", 0)
    done = done_before + done_now
    planned = data.get("planned", 0)
    rpe = data.get("rpe", 0)
    act = data.get("activity", "")
    mins = data.get("act_mins", 0)
    notes = data.get("notes", "")
    d = data.get("date", date.today().isoformat())

    # Capture state before any updates
    user_before = await get_user(tg_id)
    is_first_today = (user_before["last_workout"] != d)

    existing = await get_today_workout(user_before["id"], d)
    try:
        old_sets = json.loads(existing["sets_json"]) if existing else []
    except (json.JSONDecodeError, TypeError):
        old_sets = []
        logger.warning(f"[WARN] Corrupted sets_json for user {tg_id} on {d}")
    all_sets = old_sets + sets
    await upsert_workout(user_before["id"], d, completed=done, sets_json=json.dumps(all_sets),
                         rpe=rpe, extra_activity=act, extra_minutes=mins, notes=notes)

    # Personal record check
    pr_broken = done > (user_before["personal_record"] or 0) and done > 0
    if pr_broken:
        conn = await get_db()
        await conn.execute("UPDATE users SET personal_record=? WHERE tg_id=?", (done, tg_id))
        await conn.commit()

    level_before = user_before["level"] or 0
    xp_gained = done_now * XP_PER_PULLUP
    await add_xp(tg_id, xp_gained)

    progression_base = None
    if done > 0:
        if is_first_today:
            conn = await get_db()
            new_pd = (user_before["program_day"] or 0) + 1
            await conn.execute("UPDATE users SET program_day=? WHERE tg_id=?", (new_pd, tg_id))
            await conn.commit()
            if new_pd % 7 == 0:
                progression_base = await _check_weekly_progression(
                    tg_id, user_before["id"], user_before["base_pullups"])
        await update_streak(tg_id)

    # Refresh after streak/program_day update
    user = await get_user(tg_id)

    # ── Token earning ────────────────────────────────────────────────────────
    tokens_earned = []
    level_up = (user["level"] or 0) > level_before
    streak_milestone = (done > 0 and is_first_today
                        and (user["streak"] or 0) > 0
                        and (user["streak"] % 7) == 0)
    if level_up:
        tokens_earned.append("level")
    if streak_milestone:
        tokens_earned.append("streak")
    if pr_broken:
        tokens_earned.append("pr")
    if tokens_earned:
        from ..db import give_freeze_tokens
        await give_freeze_tokens(tg_id, len(tokens_earned))
        user = await get_user(tg_id)  # refresh token count
    lvl, lname, to_nxt, pct = level_info(user["xp"])
    bar = progress_bar(pct)
    pct_done = int(done / planned * 100) if planned else 0
    pd = f"🔥{pct_done}%" if pct_done > 100 else f"{pct_done}%"

    # Smoothed RPE adjustment
    rpe_new_base, avg_rpe = await _apply_rpe_adjustment(tg_id, user["id"], user["base_pullups"])

    # Refresh again if base changed
    if rpe_new_base or progression_base:
        user = await get_user(tg_id)

    # Build RPE comment
    rpe_comment = ""
    if rpe_new_base and avg_rpe is not None:
        if avg_rpe >= 8.5:
            rpe_comment = t("train_rpe_trending_high", lang, avg=avg_rpe, base=rpe_new_base)
        else:
            rpe_comment = t("train_rpe_trending_low", lang, avg=avg_rpe, base=rpe_new_base)

    # Build progression comment
    progression_comment = ""
    if progression_base:
        progression_comment = t("train_progression", lang, base=progression_base)

    em = "💥" if done > planned else ("🎯" if done == planned else ("✅" if done >= planned * 0.8 else "📉"))
    summary = t("train_complete", lang,
                em=em, done=done, planned=planned, pct=pd,
                sets=len(all_sets), rpe=rpe, rpe_comment=rpe_comment,
                xp_gained=xp_gained, xp_total=user["xp"],
                level=lname, bar=bar, to_next=to_nxt,
                streak=user["streak"])
    if act:
        summary += t("train_extra_note", lang, act=act, mins=mins)
    if progression_comment:
        summary += progression_comment
    if pr_broken:
        summary += t("new_pr", lang, done=done)
    if "level" in tokens_earned:
        summary += t("token_earned_level", lang, tokens=user["freeze_tokens"])
    if "streak" in tokens_earned:
        summary += t("token_earned_streak", lang, streak=user["streak"], tokens=user["freeze_tokens"])
    if "pr" in tokens_earned:
        summary += t("token_earned_pr", lang, tokens=user["freeze_tokens"])

    # Smart base recommendation (only if no automatic adjustment was made)
    if not rpe_new_base and not progression_base and planned > 0:
        ratio = done / planned
        if ratio >= 1.3 and len(all_sets) <= 5:
            rec = ("\n\n💡 *Рекомендация:* Ты выполнил задание с запасом за мало подходов. "
                   "Рассмотри увеличение базы в ⚙️ Настройки → Изменить базу."
                   if lang == "ru" else
                   "\n\n💡 *Recommendation:* You crushed the goal in few sets. "
                   "Consider raising your base in ⚙️ Settings → Change Base.")
            summary += rec
        elif ratio < 0.6 and done > 0:
            rec = ("\n\n💡 *Рекомендация:* Цель выполнена менее чем на 60%. "
                   "Рассмотри снижение базы в ⚙️ Настройки → Изменить базу."
                   if lang == "ru" else
                   "\n\n💡 *Recommendation:* You hit less than 60% of target. "
                   "Consider lowering your base in ⚙️ Settings → Change Base.")
            summary += rec

    await msg.answer(summary, parse_mode="Markdown", reply_markup=main_kb(lang))
    await _notify_friends(tg_id, done, planned, len(sets), lang)
    await state.clear()


async def _notify_friends(tg_id: int, done: int, planned: int, sets_count: int, lang: str = "ru"):
    from ..main import bot
    user = await get_user(tg_id)
    if not user:
        return
    conn = await get_db()
    # Participant model: notify all users except the sender
    async with conn.execute(
        "SELECT * FROM users WHERE tg_id != ?", (tg_id,)
    ) as cur:
        participants = await cur.fetchall()
    emoji = "🔥" if done >= planned else "💪"
    for p in participants:
        try:
            p_lang = p["lang"] or "ru"
            await bot.send_message(
                p["tg_id"],
                t("train_friend_notify", p_lang,
                  name=md_escape(display(user)),
                  emoji=emoji, done=done, planned=planned, sets=sets_count),
                parse_mode="Markdown")
        except Exception:
            pass
