from datetime import date, timedelta

from aiogram import Router, types

from ..db import get_db, get_today_workout, get_user
from ..i18n import t, text_filter, day_name
from ..keyboards import main_kb
from ..config import WAVE
from ..services.xp import display, level_info, md_escape, planned_for_day, progress_bar, weekly_chart

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
    history = ""
    no_data_label = "нет тренировок" if lang == "ru" else "no workout"
    for i in range(6, -1, -1):
        d_obj = today - timedelta(days=i)
        ds = d_obj.isoformat()
        r = rows_by_date.get(ds)
        date_label = d_obj.strftime("%d.%m.%Y")
        if r:
            done_v = r["completed"]; p = r["planned"]
            dtype = day_name(r["day_type"] or "—", lang)
            e = "✅" if done_v >= p and p > 0 else ("😴" if p == 0 else "❌")
            history += f"{e} {date_label} {dtype}: {done_v}/{p}\n"
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

    # Personal record
    pr = user["personal_record"] or 0

    # Upcoming 7-day schedule
    schedule_lines = []
    for i in range(1, 8):
        future_pd = ((user["program_day"] or 0) + i) % 7
        day_type_name, coeff = WAVE[future_pd]
        if coeff == 0:
            planned_label = t("stats_schedule_rest", lang)
        else:
            planned_n = int(user["base_pullups"] * coeff)
            planned_label = f"{planned_n}"
        dt_display = day_name(day_type_name, lang)
        future_date = (today + timedelta(days=i)).strftime("%d.%m.%Y")
        schedule_lines.append(f"`{future_date}  {dt_display:<9} {planned_label}`")
    schedule = "\n".join(schedule_lines)

    # Progress chart (last 7 days, oldest first)
    chart_rows = [rows_by_date[ds] for ds in sorted(rows_by_date)[-7:]]
    chart = weekly_chart(chart_rows, lang)

    week_label = "Неделя" if lang == "ru" else "Week"
    total_label = "Всего" if lang == "ru" else "Total"
    today_label = "Сегодня" if lang == "ru" else "Today"
    history_label = "Последние 7 дней" if lang == "ru" else "Last 7 days"
    streak_label = "Стрик" if lang == "ru" else "Streak"
    freeze_label = "Заморозок" if lang == "ru" else "Freezes"
    level_label = "Уровень" if lang == "ru" else "Level"
    xp_label = "XP"
    pr_label = t("personal_best", lang)

    chart_section = f"\n\n{t('stats_chart_title', lang)}\n{chart}" if chart else ""
    schedule_section = f"\n\n{t('stats_schedule_title', lang)}\n{schedule}"

    await message.answer(
        f"📊 *{md_escape(display(user))}*\n\n"
        f"🏅 {level_label}: *{lname}* (lvl {lvl})\n"
        f"⭐ {xp_label}: {user['xp']} [{bar}] → {to_nxt}\n"
        f"🔥 {streak_label}: *{user['streak']}* | 🧊 {freeze_label}: {user['freeze_tokens']}\n"
        f"{pr_label}: *{pr}*\n\n"
        f"📅 {today_label} ({today_type_display}): *{today_done}/{today_plan}*\n"
        f"📆 {week_label}: {week_done}/{week_planned} ({week_pct}%)\n"
        f"🏋️ {total_label}: *{total}*\n\n"
        f"📋 *{history_label}:*\n{history}"
        f"{chart_section}"
        f"{schedule_section}",
        parse_mode="Markdown",
        reply_markup=main_kb(lang))
