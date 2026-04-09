from datetime import date, timedelta

from aiogram import Router, types

from ..db import get_db, get_today_workout, get_user
from ..i18n import t, text_filter, day_name
from ..keyboards import main_kb
from ..config import LEVEL_NAMES, LEVEL_THRESHOLDS, WAVE
from ..services.xp import display, level_info, md_escape, planned_for_day, progress_bar

router = Router()


@router.message(text_filter("btn_stats"))
async def show_stats(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return

    lang = user["lang"] or "ru"
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()
    conn = await get_db()
    async with conn.execute(
        "SELECT * FROM workouts WHERE user_id=? AND date>=? ORDER BY date DESC",
        (user["id"], week_ago)
    ) as cur:
        rows = await cur.fetchall()
    async with conn.execute(
        "SELECT SUM(completed) as total FROM workouts WHERE user_id=?",
        (user["id"],)
    ) as cur:
        total_row = await cur.fetchone()

    total = (total_row[0] or 0) if total_row else 0
    lvl, lname, to_nxt, pct = level_info(user["xp"])
    bar = progress_bar(pct)
    week_done = sum(r["completed"] for r in rows)
    week_planned = sum(r["planned"] for r in rows if r["planned"] > 0)
    week_pct = int(week_done / week_planned * 100) if week_planned else 0

    rows_by_date = {r["date"]: r for r in rows}

    # Build a wave-index timeline from available records so we can infer
    # whether missing days were scheduled rest days.
    # For each record we know day_type → WAVE index before that training.
    # After training the index advances by 1. For unrecorded days the index
    # stays the same (no advancement without interaction).
    def _wave_idx(day_type: str, expected: int | None) -> int:
        matches = [k for k, (n, _) in WAVE.items() if n == day_type]
        if not matches:
            return 0
        if expected is not None and expected in matches:
            return expected
        return matches[0]

    wave_after: dict[str, int] = {}   # date_str → wave index AFTER that date's training
    prev_after: int | None = None
    for ds_r, rec in sorted(rows_by_date.items()):
        idx = _wave_idx(rec["day_type"] or "", prev_after)
        wave_after[ds_r] = (idx + 1) % 7
        prev_after = wave_after[ds_r]

    history = ""
    no_data_label = "нет тренировок" if lang == "ru" else "no workout"
    rest_label = day_name("Отдых", lang)
    for i in range(6, -1, -1):
        d_obj = today - timedelta(days=i)
        ds = d_obj.isoformat()
        r = rows_by_date.get(ds)
        date_label = d_obj.strftime("%d.%m")
        if r:
            done_v = r["completed"]; p = r["planned"]
            dtype = day_name(r["day_type"] or "—", lang)
            e = "✅" if done_v >= p and p > 0 else ("😴" if p == 0 else "❌")
            history += f"{e} {date_label} {dtype}: {done_v}/{p}\n"
        else:
            # Infer from the most recent previous record whether this was a rest day
            prev_ds = max((d for d in wave_after if d < ds), default=None)
            if prev_ds and WAVE[wave_after[prev_ds]][1] == 0:
                history += f"😴 {date_label} {rest_label}: 0/0\n"
            else:
                history += f"—  {date_label} {no_data_label}\n"

    today_w = await get_today_workout(user["id"])
    today_done = today_w["completed"] if today_w else 0
    if today_w:
        today_plan = today_w["planned"] if today_w["planned"] is not None else 0
        today_type = today_w["day_type"] or planned_for_day(user)[1]
    else:
        today_plan, today_type = planned_for_day(user)
    today_type_display = day_name(today_type, lang)

    pr = user["personal_record"] or 0

    # XP: show progress within current level
    cur_threshold = LEVEL_THRESHOLDS[lvl]
    nxt_threshold = LEVEL_THRESHOLDS[lvl + 1]
    next_lname = LEVEL_NAMES[lvl + 1] if lvl + 1 < len(LEVEL_NAMES) else "—"
    xp_in_level = user["xp"] - cur_threshold
    xp_needed = nxt_threshold - cur_threshold

    # Upcoming 7-day schedule
    schedule_lines = []
    for i in range(1, 8):
        future_pd = ((user["program_day"] or 0) + i) % 7
        day_type_name, coeff = WAVE[future_pd]
        planned_label = t("stats_schedule_rest", lang) if coeff == 0 else str(int(user["base_pullups"] * coeff))
        dt_display = day_name(day_type_name, lang)
        future_date = (today + timedelta(days=i)).strftime("%d.%m")
        schedule_lines.append(f"`{future_date}  {dt_display:<9} {planned_label}`")
    schedule = "\n".join(schedule_lines)

    champ_line = ("👑 *Кочка недели*\n" if lang == "ru" else "👑 *Beast of the Week*\n") if user["is_weekly_champ"] else ""

    if lang == "ru":
        level_line = f"🏅 *{lname}* → {next_lname}   {bar}   {xp_in_level}/{xp_needed} XP"
        streak_line = f"🔥 Стрик: *{user['streak']}* дн.  |  🧊 Заморозок: {user['freeze_tokens']}  |  🏆 Рекорд: {pr}"
        today_line = f"📅 Сегодня ({today_type_display}): *{today_done}/{today_plan}*"
        week_line = f"📆 Эта неделя: {week_done}/{week_planned} подтяг. ({week_pct}%)"
        total_line = f"🏋️ За всё время: *{total}* подтягиваний"
        history_header = "📋 *Последние 7 дней:*"
        schedule_header = "📅 *Следующие 7 дней:*"
    else:
        level_line = f"🏅 *{lname}* → {next_lname}   {bar}   {xp_in_level}/{xp_needed} XP"
        streak_line = f"🔥 Streak: *{user['streak']}* days  |  🧊 Freezes: {user['freeze_tokens']}  |  🏆 Best: {pr}"
        today_line = f"📅 Today ({today_type_display}): *{today_done}/{today_plan}*"
        week_line = f"📆 This week: {week_done}/{week_planned} pullups ({week_pct}%)"
        total_line = f"🏋️ All time: *{total}* pullups"
        history_header = "📋 *Last 7 days:*"
        schedule_header = "📅 *Next 7 days:*"

    await message.answer(
        f"📊 *{md_escape(display(user))}*\n"
        f"{champ_line}"
        f"{level_line}\n"
        f"{streak_line}\n\n"
        f"{today_line}\n"
        f"{week_line}\n"
        f"{total_line}\n\n"
        f"{history_header}\n{history}\n\n"
        f"{schedule_header}\n{schedule}",
        parse_mode="Markdown",
        reply_markup=main_kb(lang))
