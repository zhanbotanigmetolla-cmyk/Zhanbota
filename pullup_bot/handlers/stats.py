from datetime import date, timedelta

from aiogram import F, Router, types

from ..db import get_db, get_today_workout, get_user
from ..i18n import t, text_filter, day_name
from ..keyboards import main_kb, stats_analytics_kb, stats_back_kb
from ..config import LEVEL_NAMES, LEVEL_THRESHOLDS, WAVE, PROGRAMS
from ..services.xp import display, level_info, md_escape, planned_for_day, progress_bar

router = Router()


@router.message(text_filter("btn_stats"))
async def show_stats(message: types.Message):
    """Show the user's full stats: rank, XP bar, streak, weekly summary, last/next 7-day schedule."""
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
            # Infer from the most recent previous record whether this was a rest day.
            # Advance the wave index by the gap in days so consecutive unrecorded
            # days are each assigned the correct cycle slot (not all the same).
            prev_ds = max((d for d in wave_after if d < ds), default=None)
            if prev_ds:
                gap = (d_obj - date.fromisoformat(prev_ds)).days
                inferred_idx = (wave_after[prev_ds] + (gap - 1)) % 7
                if WAVE[inferred_idx][1] == 0:
                    history += f"😴 {date_label} {rest_label}: 0/0\n"
                else:
                    history += f"—  {date_label} {no_data_label}\n"
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
    # After today's session is recorded, program_day already points to *tomorrow's* slot,
    # so offset is i-1. If today hasn't been logged yet, program_day still points to today,
    # so offset is i (tomorrow = today+1 in cycle).
    pd_offset = -1 if today_w else 0
    user_wave = PROGRAMS.get(user.get("program_type") or "standard", PROGRAMS["standard"])
    schedule_lines = []
    for i in range(1, 8):
        future_pd = ((user["program_day"] or 0) + i + pd_offset) % 7
        day_type_name, coeff = user_wave[future_pd]
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
    await message.answer("📈", reply_markup=stats_analytics_kb(lang))


WEEKDAYS_RU = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
WEEKDAYS_EN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


@router.callback_query(F.data == "stats_analytics")
async def stats_analytics_view(callback: types.CallbackQuery):
    """Show the advanced analytics screen with monthly volume, day-type breakdown, and records."""
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    lang = user["lang"] or "ru"
    conn = await get_db()

    # 1. Monthly volume — last 6 months, ASCII bar chart
    async with conn.execute(
        """SELECT strftime('%Y-%m', date) AS month, SUM(completed) AS vol
           FROM workouts WHERE user_id=? GROUP BY month ORDER BY month DESC LIMIT 6""",
        (user["id"],)
    ) as cur:
        monthly_rows = list(reversed(await cur.fetchall()))

    max_vol = max((r["vol"] or 0 for r in monthly_rows), default=1) or 1
    BAR = 8
    chart_lines = []
    for r in monthly_rows:
        vol = r["vol"] or 0
        filled = round(vol / max_vol * BAR)
        bar = "█" * filled + "░" * (BAR - filled)
        chart_lines.append(f"`{r['month']}  [{bar}]  {vol}`")
    monthly_chart = "\n".join(chart_lines) if chart_lines else "—"

    # 2. Completion % by day type
    async with conn.execute(
        """SELECT day_type,
                  AVG(CASE WHEN planned > 0 THEN CAST(completed AS REAL) / planned * 100 ELSE NULL END) AS avg_pct,
                  COUNT(*) AS cnt
           FROM workouts
           WHERE user_id=? AND day_type != '' AND day_type IS NOT NULL
           GROUP BY day_type ORDER BY cnt DESC""",
        (user["id"],)
    ) as cur:
        day_type_rows = await cur.fetchall()

    dtype_lines = []
    for r in day_type_rows:
        dtype_display = day_name(r["day_type"], lang)
        pct_str = f"{r['avg_pct']:.0f}%" if r["avg_pct"] is not None else "—"
        count_label = "тр." if lang == "ru" else "sess."
        dtype_lines.append(f"  {dtype_display}: {pct_str} ({r['cnt']} {count_label})")
    dtype_text = "\n".join(dtype_lines) if dtype_lines else "—"

    # 3. Records from user row
    pr = user["personal_record"] or 0
    set_pr = user["set_record"] or 0
    max_streak_val = user.get("max_streak") or 0

    # 4. Most trained weekday
    async with conn.execute(
        """SELECT strftime('%w', date) AS wd, COUNT(*) AS cnt
           FROM workouts WHERE user_id=? AND completed > 0
           GROUP BY wd ORDER BY cnt DESC LIMIT 1""",
        (user["id"],)
    ) as cur:
        wd_row = await cur.fetchone()

    if wd_row:
        wd_idx = int(wd_row["wd"])
        wd_name = WEEKDAYS_RU[wd_idx] if lang == "ru" else WEEKDAYS_EN[wd_idx]
        weekday_text = t("analytics_weekday", lang, day=wd_name, count=wd_row["cnt"])
    else:
        weekday_text = "—"

    records_text = t("analytics_records", lang, pr=pr, set_pr=set_pr, max_streak=max_streak_val)

    text = (
        f"{t('analytics_title', lang)}\n\n"
        f"{t('analytics_monthly_vol', lang)}\n{monthly_chart}\n\n"
        f"{t('analytics_day_type', lang)}\n{dtype_text}\n\n"
        f"{records_text}\n\n"
        f"{weekday_text}"
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=stats_back_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "stats_back")
async def stats_analytics_back(callback: types.CallbackQuery):
    """Restore the analytics placeholder message to its button form."""
    user = await get_user(callback.from_user.id)
    lang = (user["lang"] or "ru") if user else "ru"
    await callback.message.edit_text("📈", reply_markup=stats_analytics_kb(lang))
    await callback.answer()
