import asyncio
import json
from datetime import date

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from ..config import (BASE_COLS, EFFECT_CONFETTI, EFFECT_FIRE, EXERCISES,
                      EXERCISE_EMOJI, PR_COLS, PROGRAMS, SET_RECORD_COLS,
                      logger, xp_for)
from ..db import (add_xp, clear_rest_row, get_db, get_day_rows, get_user,
                  get_workout, mark_rest_day, update_streak, upsert_workout)
from ..i18n import t, text_filter, day_name
from ..keyboards import (REST_TIMER_CHOICES, cancel_confirm_kb,
                         exercise_picker_kb, main_kb, parse_rpe, rest_day_kb,
                         rest_timer_kb, rpe_menu_kb, training_kb)
from ..states import Training
from ..services.xp import (answer_with_effect, day_type_for, display,
                           level_info, md_escape, progress_bar, user_base)

router = Router()


def ex_label(exercise: str, lang: str) -> str:
    """Human label for an exercise: emoji + localized name."""
    return f"{EXERCISE_EMOJI[exercise]} {t('ex_' + exercise, lang)}"


def _coeff_for_day_type(user, day_type: str) -> float:
    """Look up the load coefficient for a day-type name in the user's program wave."""
    wave = PROGRAMS.get(user["program_type"] or "standard", PROGRAMS["standard"])
    for name, coeff in wave.values():
        if name == day_type:
            return coeff
    return 1.0


async def sync_max_streak(tg_id: int) -> None:
    """Update max_streak if the user's current streak exceeds their recorded best."""
    user = await get_user(tg_id)
    if user and (user["streak"] or 0) > (user["max_streak"] or 0):
        conn = await get_db()
        await conn.execute("UPDATE users SET max_streak=? WHERE tg_id=?",
                           (user["streak"], tg_id))
        await conn.commit()


# Per-user locks to prevent duplicate processing when messages arrive in rapid succession.
# Capped to prevent unbounded memory growth — evicts oldest entries when full.
_MAX_LOCKS = 200
_user_locks: dict[int, asyncio.Lock] = {}


def _get_lock(uid: int) -> asyncio.Lock:
    """Return the per-user asyncio lock, evicting the oldest idle entry when the cap is reached."""
    if uid not in _user_locks:
        if len(_user_locks) >= _MAX_LOCKS:
            # Evict the oldest entry that is not currently held — evicting a held
            # lock would let a concurrent message bypass the duplicate guard
            for k, lock in _user_locks.items():
                if not lock.locked():
                    del _user_locks[k]
                    break
        _user_locks[uid] = asyncio.Lock()
    return _user_locks[uid]


def _days_since_last(user) -> int:
    """Return days since last recorded workout, or 999 if never."""
    if not user["last_workout"]:
        return 999
    try:
        return (date.today() - date.fromisoformat(user["last_workout"])).days
    except Exception:
        return 999


@router.message(Command("train"))
@router.message(text_filter("btn_train"))
async def start_training(message: types.Message, state: FSMContext):
    """Handle the Train button or /train command."""
    await _start_training_flow(message.from_user.id, message, state)


@router.callback_query(F.data == "reminder_train")
async def reminder_train_cb(callback: types.CallbackQuery, state: FSMContext):
    """Start today's training straight from the inline button on the morning reminder."""
    await callback.answer()
    # Buttons on messages older than 48h arrive as InaccessibleMessage (no .answer())
    if isinstance(callback.message, types.Message):
        await _start_training_flow(callback.from_user.id, callback.message, state)


async def _start_training_flow(uid: int, message: types.Message, state: FSMContext):
    """Resolve today's day type, then show the exercise picker (or the rest-day prompt)."""
    user = await get_user(uid)
    if not user:
        await message.answer(t("register_first", "ru"))
        return

    lang = user["lang"] or "ru"
    today_str = date.today().isoformat()
    day_rows = await get_day_rows(user["id"], today_str)
    training_rows = [r for r in day_rows if r["exercise"] != "rest"]
    days_off = _days_since_last(user)

    if training_rows:
        # Keep today's saved day type stable if the user re-enters training.
        day_type = training_rows[0]["day_type"] or day_type_for(user)[0]
    elif day_rows:
        day_type = "Отдых"  # rest marker exists
    elif user["last_workout"] == today_str:
        # User already handled today (acknowledged a rest day) but the row was
        # lost (e.g. cancelled a rest-override session). Restore the rest row so
        # the rest/train prompt appears again instead of jumping to a training day.
        await mark_rest_day(user["id"], today_str)
        day_type = "Отдых"
    else:
        day_type = day_type_for(user)[0]

    # If today is a rest day but the user has already been off since their last workout,
    # they've naturally rested — auto-advance program_day to the next training day.
    if day_type == "Отдых" and not training_rows and days_off >= 2:
        conn = await get_db()
        new_pd = (user["program_day"] or 0) + 1
        await conn.execute("UPDATE users SET program_day = ? WHERE id = ?", (new_pd, user["id"]))
        await conn.commit()
        await clear_rest_row(user["id"], today_str)
        if new_pd % 7 == 0:
            await _run_cycle_progressions(uid, user["id"])
        user = await get_user(uid)
        day_type = day_type_for(user)[0]

    # Rest day (normal case)
    if day_type == "Отдых":
        # Ensure a record exists so this rest day appears in stats history
        await mark_rest_day(user["id"], today_str)
        await message.answer(t("rest_day_prompt", lang), reply_markup=rest_day_kb(lang))
        await state.update_data(rest_day_lang=lang)
        await state.set_state(Training.rest_day)
        return

    await _show_exercise_picker(message, state, user, lang, today_str, day_type,
                                was_rest_override=False)


async def _show_exercise_picker(message, state, user, lang, today_str, day_type,
                                was_rest_override: bool):
    """Show the 'what are we training today' menu with per-exercise targets."""
    coeff = _coeff_for_day_type(user, day_type)
    labels = []
    label_map: dict[str, str] = {}
    for ex in EXERCISES:
        row = await get_workout(user["id"], today_str, ex)
        base = user_base(user, ex)
        label = ex_label(ex, lang)
        if row and (row["completed"] or 0) > 0:
            label += f" ✅ {row['completed']}/{row['planned']}"
        elif row and (row["planned"] or 0) > 0:
            label += f" · {row['planned']}"
        elif base > 0:
            label += f" · {int(base * coeff)}"
        labels.append(label)
        label_map[label] = ex

    day_display = day_name(day_type, lang)
    await state.set_state(Training.pick_exercise)
    await state.update_data(date=today_str, pick_day_type=day_type,
                            ex_label_map=label_map, lang=lang,
                            was_rest_override=was_rest_override)
    await message.answer(f"🟢 *{day_display}*\n\n{t('train_pick_exercise', lang)}",
                         parse_mode="Markdown",
                         reply_markup=exercise_picker_kb(labels, lang))


@router.message(Training.pick_exercise, text_filter("btn_back"))
async def pick_exercise_back(message: types.Message, state: FSMContext):
    """Leave the exercise picker and return to the main menu."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.clear()
    await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))


@router.message(Training.pick_exercise)
async def pick_exercise(message: types.Message, state: FSMContext):
    """Handle the exercise choice: start the session or ask for a first-time max."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    label_map = data.get("ex_label_map", {})
    exercise = label_map.get((message.text or "").strip())
    if not exercise:
        await message.answer(t("train_pick_exercise", lang),
                             reply_markup=exercise_picker_kb(list(label_map.keys()), lang))
        return
    user = await get_user(message.from_user.id)
    if not user:
        await state.clear()
        await message.answer(t("register_first", "ru"))
        return
    if user_base(user, exercise) <= 0:
        await state.set_state(Training.setup_base)
        await state.update_data(setup_exercise=exercise)
        await message.answer(
            t("ex_setup_prompt", lang, ex=t(f"ex_gen_{exercise}", lang)),
            parse_mode="Markdown")
        return
    await _begin_training(message, state, user, lang, data["date"], exercise,
                          data.get("pick_day_type", "Средний"),
                          data.get("was_rest_override", False))


@router.message(Training.setup_base, text_filter("btn_back"))
async def setup_base_back(message: types.Message, state: FSMContext):
    """Cancel first-time exercise setup and return to the picker."""
    user = await get_user(message.from_user.id)
    if not user:
        await state.clear()
        await message.answer(t("register_first", "ru"))
        return
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await _show_exercise_picker(message, state, user, lang, data["date"],
                                data.get("pick_day_type", "Средний"),
                                data.get("was_rest_override", False))


@router.message(Training.setup_base)
async def setup_base(message: types.Message, state: FSMContext):
    """Accept the first-time max rep count and derive the exercise's daily base."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    exercise = data.get("setup_exercise")
    if not exercise:
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))
        return
    try:
        max_reps = int((message.text or "").strip())
        if not (1 <= max_reps <= 200):
            raise ValueError
    except ValueError:
        await message.answer(t("enter_number", lang, example="10"))
        return
    base = max(5, max_reps * 3)
    conn = await get_db()
    await conn.execute(f"UPDATE users SET {BASE_COLS[exercise]}=? WHERE tg_id=?",
                       (base, message.from_user.id))
    await conn.commit()
    await message.answer(t("ex_setup_ok", lang, base=base), parse_mode="Markdown")
    user = await get_user(message.from_user.id)
    await _begin_training(message, state, user, lang, data["date"], exercise,
                          data.get("pick_day_type", "Средний"),
                          data.get("was_rest_override", False))


@router.message(Training.rest_day, text_filter("rest_day_train"))
async def rest_override_train(message: types.Message, state: FSMContext):
    """Handle 'Train anyway' on a rest day: pick an exercise for a Medium session."""
    user = await get_user(message.from_user.id)
    if not user:
        await state.clear()
        await message.answer(t("register_first", "ru"))
        return
    lang = user["lang"] or "ru"
    today_str = date.today().isoformat()
    await _show_exercise_picker(message, state, user, lang, today_str, "Средний",
                                was_rest_override=True)


@router.message(Training.rest_day, text_filter("rest_day_rest"))
async def rest_override_rest(message: types.Message, state: FSMContext):
    """Handle 'Keep resting' on a rest day: advance program_day silently."""
    data = await state.get_data()
    lang = data.get("rest_day_lang", "ru")
    user = await get_user(message.from_user.id)
    if user:
        today = date.today().isoformat()
        if user["last_workout"] != today:
            conn = await get_db()
            new_pd = (user["program_day"] or 0) + 1
            await conn.execute(
                "UPDATE users SET program_day=?, last_workout=? WHERE tg_id=?",
                (new_pd, today, message.from_user.id)
            )
            await conn.commit()
            if new_pd % 7 == 0:
                progressed = await _run_cycle_progressions(message.from_user.id, user["id"])
                for ex, new_base in progressed:
                    await message.answer(
                        t("train_progression", lang, base=new_base,
                          ex=t(f"ex_gen_{ex}", lang)),
                        parse_mode="Markdown")
        await mark_rest_day(user["id"], today)
    await state.clear()
    await message.answer(t("reminder_rest", lang), reply_markup=main_kb(lang))


async def _begin_training(message, state, user, lang, today_str, exercise, day_type,
                          was_rest_override=False):
    """Initialise FSM state and send the training prompt with today's target and quick-rep keyboard."""
    coeff = _coeff_for_day_type(user, day_type)
    planned = int(user_base(user, exercise) * coeff)
    days_off = _days_since_last(user)

    existing = await get_workout(user["id"], today_str, exercise)
    done_today = existing["completed"] if existing else 0
    done_before = done_today
    session_sets: list = []

    break_note = ""
    if existing and existing["planned"]:
        # Keep the target that was already set for this exercise today
        planned = existing["planned"]
    elif 3 <= days_off < 999:
        # After a long break, reduce load and warn
        reduction = 0.6 if days_off >= 7 else 0.75
        planned = int(planned * reduction)
        break_note = (f"⚠️ _Перерыв {days_off} дн. — нагрузка снижена до {int(reduction*100)}% для плавного возвращения._\n\n"
                      if lang == "ru" else
                      f"⚠️ _Break of {days_off} days — load reduced to {int(reduction*100)}% for a smooth return._\n\n")

    if was_rest_override:
        # The day stops being a rest day the moment an override session starts.
        # Cancelling restores the rest row via _cleanup_cancelled_workout.
        await clear_rest_row(user["id"], today_str)

    if existing:
        await upsert_workout(user["id"], today_str, exercise,
                             planned=planned, day_type=day_type)
    else:
        await upsert_workout(user["id"], today_str, exercise,
                             planned=planned, day_type=day_type,
                             sets_json=json.dumps([]), completed=0)

    if break_note:
        await message.answer(break_note, parse_mode="Markdown")

    await state.set_state(Training.active)
    await state.update_data(date=today_str, exercise=exercise, planned=planned,
                            sets=session_sets, done_before=done_before, lang=lang,
                            was_rest_override=was_rest_override,
                            orig_set_record=user[SET_RECORD_COLS[exercise]] or 0)

    day_display = day_name(day_type, lang)
    density_note = ("\n\n" + t("density_hint", lang)) if day_type == "Плотность" else ""
    hint = "\n_Нажми на число или введи вручную:_" if lang == "ru" else "\n_Tap a number or enter manually:_"
    await message.answer(
        f"🟢 *{day_display}* — {ex_label(exercise, lang)}\n\n"
        f"{t('train_goal', lang, planned=planned, ex=t(f'ex_gen_{exercise}', lang))}\n"
        f"{t('train_done_today', lang, done=done_today)}\n"
        f"{t('train_done_now', lang, done=0)}"
        f"{density_note}{hint}",
        parse_mode="Markdown", reply_markup=training_kb(session_sets, planned, lang))


async def _training_status(message: types.Message, state: FSMContext):
    """Refresh the live progress message: the previous status is deleted and a new
    one is sent, so the chat keeps a single up-to-date status with rest-timer buttons."""
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
    old_id = data.get("status_msg_id")
    if old_id:
        try:
            await message.bot.delete_message(message.chat.id, old_id)
        except Exception:
            pass  # already gone or too old — a leftover status is harmless
    new_msg = await message.answer(
        f"{t('train_in_progress', lang)}\n\n"
        f"{t('train_done_now', lang, done=done_now)}\n"
        f"✅ {today_line}\n"
        f"[{bar}] {pd}\n"
        f"📦 {sets_line}\n"
        f"{last_line}",
        parse_mode="Markdown", reply_markup=rest_timer_kb(lang))
    await state.update_data(status_msg_id=new_msg.message_id)


async def _delete_status_message(message: types.Message, data: dict):
    """Remove the live status message once the session ends — the summary supersedes it."""
    mid = data.get("status_msg_id")
    if mid:
        try:
            await message.bot.delete_message(message.chat.id, mid)
        except Exception:
            pass


# One live rest timer per user; starting a new one replaces the previous.
_rest_tasks: dict[int, asyncio.Task] = {}


async def _rest_timer_ping(bot, chat_id: int, uid: int, seconds: int, lang: str):
    """Sleep out the rest interval, then ping the user if they are still mid-session."""
    try:
        await asyncio.sleep(seconds)
        from ..main import dp  # local import: main.py imports this module at startup
        key = StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=uid)
        current = await dp.storage.get_state(key)
        if current == Training.active.state:
            await bot.send_message(chat_id, t("rest_timer_done", lang))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"[rest_timer] {uid}: {e}")
    finally:
        _rest_tasks.pop(uid, None)


@router.callback_query(F.data.startswith("rest:"))
async def rest_timer_start(callback: types.CallbackQuery, state: FSMContext):
    """Start (or restart) a rest countdown from the buttons under the live status."""
    try:
        seconds = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer()
        return
    if seconds not in REST_TIMER_CHOICES or not callback.message:
        await callback.answer()
        return
    current = await state.get_state()
    if current != Training.active:
        await callback.answer()  # stale button from an already-finished session
        return
    data = await state.get_data()
    lang = data.get("lang", "ru")
    uid = callback.from_user.id
    old = _rest_tasks.get(uid)
    if old and not old.done():
        old.cancel()
    _rest_tasks[uid] = asyncio.create_task(
        _rest_timer_ping(callback.bot, callback.message.chat.id, uid, seconds, lang))
    await callback.answer(t("rest_timer_toast", lang, sec=seconds))


@router.message(text_filter("btn_undo"), Training.active)
async def undo_set(message: types.Message, state: FSMContext):
    """Remove the last recorded set from the current training session."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    sets = data.get("sets", [])
    if not sets:
        await message.answer(t("train_no_sets", lang))
        return
    sets.pop()
    await state.update_data(sets=sets)
    # If the undone set was a session PR, roll the set record back to what it
    # should be without it (pre-session record vs remaining session sets).
    orig_record = data.get("orig_set_record")
    if orig_record is not None:
        exercise = data.get("exercise", "pullups")
        desired = max([orig_record] + sets)
        user = await get_user(message.from_user.id)
        rec_col = SET_RECORD_COLS[exercise]
        if user and (user[rec_col] or 0) > desired:
            conn = await get_db()
            await conn.execute(f"UPDATE users SET {rec_col}=? WHERE tg_id=?",
                               (desired, message.from_user.id))
            await conn.commit()
        session_pr = max(sets) if sets and max(sets) > orig_record else None
        await state.update_data(session_set_pr=session_pr)
    await _training_status(message, state)


@router.message(text_filter("btn_manual"), Training.active)
async def prompt_custom_set(message: types.Message, state: FSMContext):
    """Prompt the user to type a custom rep count manually."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await message.answer(t("train_enter_reps", lang))


@router.message(text_filter("btn_finish"), Training.active)
async def finish_training_btn(message: types.Message, state: FSMContext):
    """Transition from active training to the RPE rating step."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await message.answer(t("train_rate_rpe", lang), reply_markup=rpe_menu_kb(lang))
    await state.set_state(Training.rpe)


@router.message(text_filter("btn_back"), Training.rpe)
async def rpe_back(message: types.Message, state: FSMContext):
    """Go back from the RPE rating step to the active training session."""
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
    exercise = state_data.get("exercise", "pullups")
    was_rest_override = state_data.get("was_rest_override", False)
    user = await get_user(tg_id)
    if not user:
        return
    # Roll back any set record earned by the now-cancelled session's sets
    orig_record = state_data.get("orig_set_record")
    if orig_record is not None:
        rec_col = SET_RECORD_COLS[exercise]
        if (user[rec_col] or 0) > orig_record:
            conn = await get_db()
            await conn.execute(f"UPDATE users SET {rec_col}=? WHERE tg_id=?",
                               (orig_record, tg_id))
            await conn.commit()
    if done_before == 0:
        # No prior progress — delete the ghost record entirely
        conn = await get_db()
        await conn.execute(
            "DELETE FROM workouts WHERE user_id=? AND date=? AND exercise=?",
            (user["id"], d, exercise)
        )
        await conn.commit()
        if was_rest_override:
            # Restore the rest day row that existed before the user chose to train
            await mark_rest_day(user["id"], d)
    # If done_before > 0, the DB record still holds the previous completed value — no action needed


@router.message(text_filter("btn_cancel_train"), Training.active)
async def cancel_training_btn(message: types.Message, state: FSMContext):
    """Handle the Cancel button during training: confirm if reps were already logged, else cancel silently."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    sets = data.get("sets", [])
    done = sum(sets)
    if done == 0:
        await _cleanup_cancelled_workout(message.from_user.id, data)
        await _delete_status_message(message, data)
        await state.clear()
        await message.answer(t("train_cancelled", lang), reply_markup=main_kb(lang))
        return
    await message.answer(
        t("train_confirm_cancel", lang, done=done, sets=len(sets)),
        parse_mode="Markdown", reply_markup=cancel_confirm_kb(lang))
    await state.set_state(Training.cancel_confirm)


@router.message(Training.cancel_confirm, text_filter("train_yes_cancel"))
async def cancel_confirm(message: types.Message, state: FSMContext):
    """Confirm cancellation of the current training session and clean up any unsaved workout record."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await _cleanup_cancelled_workout(message.from_user.id, data)
    await _delete_status_message(message, data)
    await state.clear()
    await message.answer(t("train_cancelled", lang), reply_markup=main_kb(lang))


@router.message(Training.cancel_confirm, text_filter("train_continue"))
async def cancel_back_msg(message: types.Message, state: FSMContext):
    """Return to the active training session after the user chose not to cancel."""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    sets = data.get("sets", [])
    planned = data.get("planned", 0)
    await state.set_state(Training.active)
    await message.answer(t("train_lets_go", lang), reply_markup=training_kb(sets, planned, lang))


@router.message(Training.active, F.text.regexp(r"^\s*\d+\s*$"))
async def custom_set_input(message: types.Message, state: FSMContext):
    """Accept a numeric rep count from the user and append it to the current session's set list."""
    uid = message.from_user.id
    lock = _get_lock(uid)
    if lock.locked():
        return  # duplicate rapid message — drop silently
    async with lock:
        current_state = await state.get_state()
        if current_state != Training.active:
            return
        reps = int(message.text.strip())
        if reps < 1 or reps > 500:
            data = await state.get_data()
            lang = data.get("lang", "ru")
            await message.answer(t("enter_number", lang, example="10"))
            return
        data = await state.get_data()
        lang = data.get("lang", "ru")
        exercise = data.get("exercise", "pullups")
        sets = data.get("sets", [])
        sets.append(reps)
        await state.update_data(sets=sets)
        await _training_status(message, state)

        # Check for per-set personal record (per exercise)
        user = await get_user(uid)
        rec_col = SET_RECORD_COLS[exercise]
        if user and reps > (user[rec_col] or 0):
            conn = await get_db()
            await conn.execute(f"UPDATE users SET {rec_col}=? WHERE tg_id=?", (reps, uid))
            await conn.commit()
            await state.update_data(session_set_pr=reps)
            await answer_with_effect(
                message,
                t("set_pr_congrats", lang, reps=reps, ex=t(f"ex_gen_{exercise}", lang)),
                EFFECT_CONFETTI, parse_mode="Markdown")


@router.message(Training.rpe)
async def set_rpe_msg(message: types.Message, state: FSMContext):
    """Parse the user's RPE selection and save the workout immediately."""
    uid = message.from_user.id
    lock = _get_lock(uid)
    if lock.locked():
        return  # duplicate rapid message — drop silently
    async with lock:
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
        processing_msg = await message.answer(t("train_saving", lang))
        await _save_workout(message, state, uid, processing_msg)


async def _check_weekly_progression(tg_id: int, user_id: int, exercise: str,
                                    current_base: int):
    """After a 7-day cycle, bump the exercise's base +5% if its last 5 sessions averaged ≥80% and avg RPE < 7."""
    conn = await get_db()
    async with conn.execute(
        "SELECT date, completed, planned, rpe FROM workouts "
        "WHERE user_id=? AND exercise=? AND planned > 0 ORDER BY date DESC LIMIT 5",
        (user_id, exercise)
    ) as cur:
        rows = await cur.fetchall()
    if len(rows) < 5:
        return None
    # Only progress exercises the user actually trains — the newest of those
    # 5 sessions must be recent, otherwise a long-abandoned exercise would keep
    # progressing on stale data every cycle.
    try:
        newest = date.fromisoformat(rows[0]["date"])
        if (date.today() - newest).days > 14:
            return None
    except Exception:
        return None
    avg = sum(r["completed"] / r["planned"] for r in rows if r["planned"] > 0) / len(rows)
    rpe_rows = [r["rpe"] for r in rows if r["rpe"] and r["rpe"] > 0]
    avg_rpe = sum(rpe_rows) / len(rpe_rows) if rpe_rows else 0
    if avg >= 0.8 and (avg_rpe == 0 or avg_rpe < 7.0):
        new_base = int(current_base * 1.05)
        await conn.execute(
            f"UPDATE users SET {BASE_COLS[exercise]}=? WHERE tg_id=?",
            (new_base, tg_id)
        )
        await conn.commit()
        return new_base
    return None


async def _run_cycle_progressions(tg_id: int, user_id: int) -> list:
    """Run the weekly progression check for every set-up exercise; return [(exercise, new_base)]."""
    user = await get_user(tg_id)
    if not user:
        return []
    progressed = []
    for ex in EXERCISES:
        base = user[BASE_COLS[ex]] or 0
        if base <= 0:
            continue
        new_base = await _check_weekly_progression(tg_id, user_id, ex, base)
        if new_base:
            progressed.append((ex, new_base))
    return progressed


async def _apply_rpe_adjustment(tg_id: int, user_id: int, exercise: str,
                                current_base: int):
    """
    Rolling average of the exercise's last 3 RPE readings — 4 zones:
      <= 5.5              : base +3% (training feels easy)
      5.5 < avg < 7.0     : no change (normal zone)
      7.0 <= avg < 8.5    : base −2% (high effort, ease back slightly)
      >= 8.5              : base −5% (too hard)
    """
    conn = await get_db()
    async with conn.execute(
        "SELECT rpe, completed, planned FROM workouts "
        "WHERE user_id=? AND exercise=? AND rpe > 0 AND planned > 0 "
        "ORDER BY date DESC LIMIT 3",
        (user_id, exercise)
    ) as cur:
        rows = await cur.fetchall()
    if len(rows) < 3:
        return None, None
    avg_rpe = sum(r["rpe"] for r in rows) / 3
    all_hit = all(r["completed"] >= r["planned"] for r in rows)
    base_col = BASE_COLS[exercise]
    if avg_rpe >= 8.5:
        new_base = max(10, int(current_base * 0.95))
        await conn.execute(f"UPDATE users SET {base_col}=? WHERE tg_id=?", (new_base, tg_id))
        await conn.commit()
        return new_base, avg_rpe
    if avg_rpe >= 7.0:
        new_base = max(10, int(current_base * 0.98))
        await conn.execute(f"UPDATE users SET {base_col}=? WHERE tg_id=?", (new_base, tg_id))
        await conn.commit()
        return new_base, avg_rpe
    if avg_rpe <= 5.5 and all_hit:
        new_base = int(current_base * 1.03)
        await conn.execute(f"UPDATE users SET {base_col}=? WHERE tg_id=?", (new_base, tg_id))
        await conn.commit()
        return new_base, avg_rpe
    return None, None


async def _save_workout(msg, state: FSMContext, tg_id: int, processing_msg=None):
    """Persist the completed workout, update XP/streak/program_day, apply progressions, and send summary."""
    if processing_msg:
        try:
            await processing_msg.delete()
        except Exception:
            pass
    data = await state.get_data()
    sets = data.get("sets", [])
    lang = data.get("lang", "ru")
    exercise = data.get("exercise", "pullups")
    done_now = sum(sets)
    done_before = data.get("done_before", 0)
    done = done_before + done_now
    planned = data.get("planned", 0)
    rpe = data.get("rpe", 0)
    d = data.get("date", date.today().isoformat())
    ex_gen = t(f"ex_gen_{exercise}", lang)

    # Capture state before any updates
    user_before = await get_user(tg_id)
    is_first_today = (user_before["last_workout"] != d)

    existing = await get_workout(user_before["id"], d, exercise)
    try:
        old_sets = json.loads(existing["sets_json"]) if existing else []
    except (json.JSONDecodeError, TypeError):
        old_sets = []
        logger.warning(f"[WARN] Corrupted sets_json for user {tg_id} on {d} ({exercise})")
    all_sets = old_sets + sets
    await upsert_workout(user_before["id"], d, exercise, completed=done,
                         sets_json=json.dumps(all_sets), rpe=rpe)

    # Personal record check (per exercise)
    pr_col = PR_COLS[exercise]
    pr_broken = done > (user_before[pr_col] or 0) and done > 0
    if pr_broken:
        conn = await get_db()
        await conn.execute(f"UPDATE users SET {pr_col}=? WHERE tg_id=?", (done, tg_id))
        await conn.commit()

    level_before = user_before["level"] or 0
    xp_gained = xp_for(exercise, done_now)
    await add_xp(tg_id, xp_gained)

    progressed = []
    if done > 0:
        if is_first_today:
            conn = await get_db()
            new_pd = (user_before["program_day"] or 0) + 1
            await conn.execute("UPDATE users SET program_day=? WHERE tg_id=?", (new_pd, tg_id))
            await conn.commit()
            if new_pd % 7 == 0:
                progressed = await _run_cycle_progressions(tg_id, user_before["id"])
        await update_streak(tg_id, d)
        await sync_max_streak(tg_id)

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

    # Smoothed RPE adjustment (per exercise)
    rpe_new_base, avg_rpe = await _apply_rpe_adjustment(
        tg_id, user["id"], exercise, user[BASE_COLS[exercise]])
    if rpe_new_base or progressed:
        user = await get_user(tg_id)

    # Build RPE comment
    rpe_comment = ""
    if rpe_new_base and avg_rpe is not None:
        if avg_rpe >= 8.5:
            rpe_comment = t("train_rpe_trending_high", lang, avg=avg_rpe,
                            base=rpe_new_base, ex=ex_gen)
        elif avg_rpe >= 7.0:
            rpe_comment = t("train_rpe_trending_moderate", lang, avg=avg_rpe,
                            base=rpe_new_base, ex=ex_gen)
        else:
            rpe_comment = t("train_rpe_trending_low", lang, avg=avg_rpe,
                            base=rpe_new_base, ex=ex_gen)

    em = "💥" if done > planned else ("🎯" if done == planned else ("✅" if done >= planned * 0.8 else "📉"))
    summary = t("train_complete", lang,
                em=em, ex=t(f"ex_{exercise}", lang), done=done, planned=planned, pct=pd,
                sets=len(all_sets), rpe=rpe, rpe_comment=rpe_comment,
                xp_gained=xp_gained, xp_total=user["xp"],
                level=lname, bar=bar, to_next=to_nxt,
                streak=user["streak"])
    for ex2, new_base in progressed:
        summary += t("train_progression", lang, base=new_base,
                     ex=t(f"ex_gen_{ex2}", lang))
    if pr_broken:
        summary += t("new_pr", lang, done=done, ex=ex_gen)
    if "level" in tokens_earned:
        summary += t("token_earned_level", lang, tokens=user["freeze_tokens"])
    if "streak" in tokens_earned:
        summary += t("token_earned_streak", lang, streak=user["streak"], tokens=user["freeze_tokens"])
    if "pr" in tokens_earned:
        summary += t("token_earned_pr", lang, tokens=user["freeze_tokens"])

    # Smart base recommendation (only if no automatic adjustment was made)
    if not rpe_new_base and not progressed and planned > 0:
        ratio = done / planned
        if ratio >= 1.3 and len(all_sets) <= 5:
            rec = ("\n\n💡 *Рекомендация:* Ты выполнил задание с запасом за мало подходов. "
                   "Рассмотри увеличение нормы в ⚙️ Настройки → Изменить базу."
                   if lang == "ru" else
                   "\n\n💡 *Recommendation:* You crushed the goal in few sets. "
                   "Consider raising your target in ⚙️ Settings → Change Base.")
            summary += rec
        elif ratio < 0.6 and done > 0:
            rec = ("\n\n💡 *Рекомендация:* Цель выполнена менее чем на 60%. "
                   "Рассмотри снижение нормы в ⚙️ Настройки → Изменить базу."
                   if lang == "ru" else
                   "\n\n💡 *Recommendation:* You hit less than 60% of target. "
                   "Consider lowering your target in ⚙️ Settings → Change Base.")
            summary += rec

    await _delete_status_message(msg, data)
    # Celebration effect: confetti for records/rank-ups, fire for hitting the target
    if pr_broken or level_up:
        await answer_with_effect(msg, summary, EFFECT_CONFETTI,
                                 parse_mode="Markdown", reply_markup=main_kb(lang))
    elif planned > 0 and done >= planned:
        await answer_with_effect(msg, summary, EFFECT_FIRE,
                                 parse_mode="Markdown", reply_markup=main_kb(lang))
    else:
        await msg.answer(summary, parse_mode="Markdown", reply_markup=main_kb(lang))
    session_set_pr = data.get("session_set_pr")
    await _notify_friends(tg_id, exercise, done, planned, len(sets), lang,
                          set_pr=session_set_pr)
    await state.clear()


async def _notify_friends(tg_id: int, exercise: str, done: int, planned: int,
                          sets_count: int, lang: str = "ru", set_pr=None):
    """Send a workout completion notification to all users who opted in to workout alerts."""
    from ..main import bot
    user = await get_user(tg_id)
    if not user:
        return
    conn = await get_db()
    # Only notify users who opted in to workout notifications
    async with conn.execute(
        "SELECT * FROM users WHERE tg_id != ? AND notify_workouts = 1", (tg_id,)
    ) as cur:
        participants = await cur.fetchall()
    emoji = "🔥" if done >= planned else "💪"
    for p in participants:
        try:
            p_lang = p["lang"] or "ru"
            text = t("train_friend_notify", p_lang,
                     name=md_escape(display(user)), ex=t(f"ex_{exercise}", p_lang).lower(),
                     emoji=emoji, done=done, planned=planned, sets=sets_count)
            if set_pr:
                text += t("set_pr_friend_line", p_lang, reps=set_pr,
                          ex=t(f"ex_gen_{exercise}", p_lang))
            await bot.send_message(p["tg_id"], text, parse_mode="Markdown")
        except Exception as e:
            logger.debug(f"[notify_friends] {p['tg_id']}: {e}")
