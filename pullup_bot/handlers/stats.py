from datetime import date, timedelta

from aiogram import F, Router, types
from aiogram.filters import Command

from ..db import get_db, get_user
from ..i18n import t, text_filter, day_name
from ..keyboards import stats_analytics_kb, stats_back_kb
from ..config import (EXERCISES, EXERCISE_EMOJI, LEVEL_NAMES,
                      LEVEL_THRESHOLDS, PR_COLS, PROGRAMS, SET_RECORD_COLS,
                      XP_CASE_SQL)
from ..services.xp import (day_type_for, display, level_info, md_escape,
                           progress_bar, user_base)

router = Router()


def _ex_tag(ex: str) -> str:
    """Short language-neutral cell tag for compact tables."""
    return EXERCISE_EMOJI[ex]


@router.message(Command("stats"))
@router.message(text_filter("btn_stats"))
async def show_stats(message: types.Message):
    """Show the user's full stats with the analytics button attached inline."""
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    lang = user["lang"] or "ru"
    text = await _build_stats_text(user, lang)
    await message.answer(text, parse_mode="Markdown",
                         reply_markup=stats_analytics_kb(lang))


async def _build_stats_text(user, lang: str) -> str:
    """Build the full stats message: rank, XP bar, streak, per-exercise summary, last/next 7 days."""
    today = date.today()
    today_str = today.isoformat()
    week_ago = (today - timedelta(days=7)).isoformat()
    conn = await get_db()
    async with conn.execute(
        "SELECT * FROM workouts WHERE user_id=? AND date>=? ORDER BY date DESC",
        (user["id"], week_ago)
    ) as cur:
        rows = await cur.fetchall()
    async with conn.execute(
        "SELECT exercise, SUM(completed) as total FROM workouts "
        "WHERE user_id=? AND exercise != 'rest' GROUP BY exercise",
        (user["id"],)
    ) as cur:
        alltime_rows = await cur.fetchall()
    alltime = {r["exercise"]: r["total"] or 0 for r in alltime_rows}

    lvl, lname, to_nxt, pct = level_info(user["xp"])
    bar = progress_bar(pct)

    # Group week rows by date
    rows_by_date: dict = {}
    for r in rows:
        rows_by_date.setdefault(r["date"], []).append(r)

    today_rows = rows_by_date.get(today_str, [])
    today_training = [r for r in today_rows if r["exercise"] != "rest"]

    # Resolve today's day type the same way the training handler does
    if today_training:
        today_type = today_training[0]["day_type"] or day_type_for(user)[0]
    elif today_rows:
        today_type = "Отдых"
    else:
        today_type = day_type_for(user)[0]

    user_wave = PROGRAMS.get(user["program_type"] or "standard", PROGRAMS["standard"])
    coeff_today = next((c for n, c in user_wave.values() if n == today_type), 1.0)

    # Which exercises to show: any with a base set or any recorded volume
    shown = [ex for ex in EXERCISES
             if user_base(user, ex) > 0 or alltime.get(ex, 0) > 0]
    if not shown:
        shown = ["pullups"]

    week_totals = {}
    for r in rows:
        if r["exercise"] == "rest":
            continue
        d_, p_ = week_totals.get(r["exercise"], (0, 0))
        week_totals[r["exercise"]] = (d_ + (r["completed"] or 0), p_ + (r["planned"] or 0))

    # Build a wave-index timeline from available records so we can infer,
    # for the last 7 days, whether a date with no workout row at all was a
    # scheduled rest day or a training day the user skipped entirely.
    def _wave_idx(day_type: str, expected: int | None) -> int:
        matches = [k for k, (n, _) in user_wave.items() if n == day_type]
        if not matches:
            return 0
        if expected is not None and expected in matches:
            return expected
        return matches[0]

    wave_after: dict = {}   # date_str → wave index AFTER that date's training
    prev_after: int | None = None
    for ds_r in sorted(rows_by_date):
        first = rows_by_date[ds_r][0]
        idx = _wave_idx(first["day_type"] or "", prev_after)
        wave_after[ds_r] = (idx + 1) % 7
        prev_after = wave_after[ds_r]

    # date_str → inferred wave index, for last-7-days dates with no workout
    # row at all (neither training nor an explicit rest marker).
    missing_idx: dict = {}
    for i in range(6, -1, -1):
        ds = (today - timedelta(days=i)).isoformat()
        if ds in rows_by_date:
            continue
        prev_ds = max((d for d in wave_after if d < ds), default=None)
        if prev_ds is None:
            continue
        gap = (date.fromisoformat(ds) - date.fromisoformat(prev_ds)).days
        missing_idx[ds] = (wave_after[prev_ds] + (gap - 1)) % 7

    # A skipped (non-rest) day still had a plan — count it toward this
    # week's planned total so "done/planned" reflects what was actually
    # missed instead of quietly shrinking to match what was logged.
    for idx in missing_idx.values():
        coeff_missed = user_wave[idx][1]
        if coeff_missed == 0:
            continue
        for ex in shown:
            if user_base(user, ex) > 0:
                d_, p_ = week_totals.get(ex, (0, 0))
                week_totals[ex] = (d_, p_ + int(user_base(user, ex) * coeff_missed))

    today_word = "сегодня" if lang == "ru" else "today"
    week_word = "неделя" if lang == "ru" else "week"
    total_word = "всего" if lang == "ru" else "total"
    ex_lines = []
    for ex in shown:
        today_row = next((r for r in today_training if r["exercise"] == ex), None)
        if today_row:
            today_cell = f"{today_row['completed']}/{today_row['planned']}"
        elif today_type != "Отдых" and user_base(user, ex) > 0:
            today_cell = f"—/{int(user_base(user, ex) * coeff_today)}"
        else:
            today_cell = "—"
        w_done, w_planned = week_totals.get(ex, (0, 0))
        ex_lines.append(
            f"{EXERCISE_EMOJI[ex]} {t('ex_' + ex, lang)}: "
            f"{today_word} {today_cell} · {week_word} {w_done}/{w_planned} · "
            f"{total_word} {alltime.get(ex, 0)}"
        )

    # ── Last 7 days ──────────────────────────────────────────────────────────
    history = ""
    no_data_label = "нет тренировок" if lang == "ru" else "no workout"
    rest_label = day_name("Отдых", lang)
    for i in range(6, -1, -1):
        d_obj = today - timedelta(days=i)
        ds = d_obj.isoformat()
        day_rows = rows_by_date.get(ds)
        date_label = d_obj.strftime("%d.%m")
        if day_rows:
            training = [r for r in day_rows if r["exercise"] != "rest"]
            if training:
                cells = " ".join(
                    f"{_ex_tag(r['exercise'])}{r['completed']}/{r['planned']}"
                    for r in training)
                dtype = day_name(training[0]["day_type"] or "—", lang)
                targets = [r for r in training if (r["planned"] or 0) > 0]
                all_hit = targets and all(r["completed"] >= r["planned"] for r in targets)
                e = "✅" if all_hit else "❌"
                history += f"{e} {date_label} {dtype}: {cells}\n"
            else:
                history += f"😴 {date_label} {rest_label}\n"
        else:
            inferred_idx = missing_idx.get(ds)
            if inferred_idx is not None and user_wave[inferred_idx][1] == 0:
                history += f"😴 {date_label} {rest_label}\n"
            else:
                history += f"—  {date_label} {no_data_label}\n"

    # ── Next 7 days ──────────────────────────────────────────────────────────
    # After today's session is recorded, program_day already points to *tomorrow's*
    # slot, so offset is i-1. If today hasn't been logged yet, program_day still
    # points to today, so offset is i (tomorrow = today+1 in cycle).
    pd_offset = -1 if user["last_workout"] == today_str else 0
    schedule_lines = []
    for i in range(1, 8):
        future_pd = ((user["program_day"] or 0) + i + pd_offset) % 7
        day_type_name, coeff = user_wave[future_pd]
        dt_display = day_name(day_type_name, lang)
        if coeff == 0:
            planned_label = t("stats_schedule_rest", lang)
        else:
            planned_label = " ".join(
                f"{_ex_tag(ex)}{int(user_base(user, ex) * coeff)}"
                for ex in shown if user_base(user, ex) > 0) or "—"
        future_date = (today + timedelta(days=i)).strftime("%d.%m")
        schedule_lines.append(f"`{future_date}  {dt_display:<9} {planned_label}`")
    schedule = "\n".join(schedule_lines)

    champ_line = ("👑 *Кочка недели*\n" if lang == "ru" else "👑 *Beast of the Week*\n") if user["is_weekly_champ"] else ""

    # XP: show progress within current level
    cur_threshold = LEVEL_THRESHOLDS[lvl]
    nxt_threshold = LEVEL_THRESHOLDS[lvl + 1]
    next_lname = LEVEL_NAMES[lvl + 1] if lvl + 1 < len(LEVEL_NAMES) else "—"
    xp_in_level = user["xp"] - cur_threshold
    xp_needed = nxt_threshold - cur_threshold

    best_streak = user["max_streak"] or user["streak"] or 0
    level_line = f"🏅 *{lname}* → {next_lname}   {bar}   {xp_in_level}/{xp_needed} XP"
    if lang == "ru":
        streak_line = f"🔥 Стрик: *{user['streak']}* дн. (лучший: {best_streak})  |  🧊 Заморозок: {user['freeze_tokens']}"
        today_line = f"📅 Сегодня: *{day_name(today_type, lang)}*"
        history_header = "📋 *Последние 7 дней:*"
        schedule_header = "📅 *Следующие 7 дней:*"
    else:
        streak_line = f"🔥 Streak: *{user['streak']}* days (best: {best_streak})  |  🧊 Freezes: {user['freeze_tokens']}"
        today_line = f"📅 Today: *{day_name(today_type, lang)}*"
        history_header = "📋 *Last 7 days:*"
        schedule_header = "📅 *Next 7 days:*"

    return (
        f"📊 *{md_escape(display(user))}*\n"
        f"{champ_line}"
        f"{level_line}\n"
        f"{streak_line}\n\n"
        f"{today_line}\n"
        + "\n".join(ex_lines) + "\n\n"
        f"{history_header}\n{history}\n"
        f"{schedule_header}\n{schedule}"
    )


WEEKDAYS_RU = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
WEEKDAYS_EN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


@router.callback_query(F.data == "stats_analytics")
async def stats_analytics_view(callback: types.CallbackQuery):
    """Show the advanced analytics screen with monthly XP volume, day-type breakdown, and records."""
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    lang = user["lang"] or "ru"
    conn = await get_db()

    # 1. Monthly volume in XP — last 6 months, ASCII bar chart
    async with conn.execute(
        f"""SELECT strftime('%Y-%m', date) AS month, SUM({XP_CASE_SQL}) AS vol
           FROM workouts WHERE user_id=? GROUP BY month ORDER BY month DESC LIMIT 6""",
        (user["id"],)
    ) as cur:
        monthly_rows = list(reversed(await cur.fetchall()))

    max_vol = max((r["vol"] or 0 for r in monthly_rows), default=1) or 1
    BAR = 8
    chart_lines = []
    for r in monthly_rows:
        vol = int(round(r["vol"] or 0))
        filled = round(vol / max_vol * BAR)
        bar = "█" * filled + "░" * (BAR - filled)
        chart_lines.append(f"`{r['month']}  [{bar}]  {vol}`")
    monthly_chart = "\n".join(chart_lines) if chart_lines else "—"

    # 2. Completion % by day type (training rows only)
    async with conn.execute(
        """SELECT day_type,
                  AVG(CASE WHEN planned > 0 THEN CAST(completed AS REAL) / planned * 100 ELSE NULL END) AS avg_pct,
                  COUNT(*) AS cnt
           FROM workouts
           WHERE user_id=? AND exercise != 'rest' AND day_type != '' AND day_type IS NOT NULL
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

    # 3. Records per exercise from the user row
    record_lines = []
    for ex in EXERCISES:
        pr = user[PR_COLS[ex]] or 0
        set_pr = user[SET_RECORD_COLS[ex]] or 0
        if pr == 0 and set_pr == 0 and user_base(user, ex) <= 0:
            continue
        record_lines.append(
            f"  {EXERCISE_EMOJI[ex]} {t('ex_' + ex, lang)}: {pr} / {set_pr}")
    records_block = "\n".join(record_lines) if record_lines else "  —"
    max_streak_val = user["max_streak"] or 0

    # 4. Most trained weekday
    async with conn.execute(
        """SELECT strftime('%w', date) AS wd, COUNT(DISTINCT date) AS cnt
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

    records_text = t("analytics_records", lang, records=records_block,
                     max_streak=max_streak_val)

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
    """Swap the analytics view back to the full stats message in place."""
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    lang = user["lang"] or "ru"
    text = await _build_stats_text(user, lang)
    await callback.message.edit_text(text, parse_mode="Markdown",
                                     reply_markup=stats_analytics_kb(lang))
    await callback.answer()
