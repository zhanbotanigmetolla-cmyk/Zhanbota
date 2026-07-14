import calendar
from datetime import date, timedelta

from aiogram import F, Router, types
from aiogram.filters import Command

from ..config import EXERCISES, EXERCISE_EMOJI
from ..db import get_db, get_user
from ..i18n import t, text_filter, day_name
from ..keyboards import history_nav_kb


router = Router()

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAYS_EN = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def _week_dates(offset: int):
    """Return (monday, sunday) date objects for the week at the given offset from the current week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _ex_totals_line(totals: dict) -> str:
    """Render per-exercise done/planned totals as compact emoji-tagged cells."""
    cells = []
    for ex in EXERCISES:
        if ex not in totals:
            continue
        done, planned = totals[ex]
        cells.append(f"{EXERCISE_EMOJI[ex]}{done}/{planned}")
    return " ".join(cells) if cells else "0/0"


def _format_week(rows_by_date: dict, monday: date, sunday: date, lang: str) -> str:
    """Format one week of workout data as a Markdown code-block table with a weekly total footer."""
    weekdays = WEEKDAYS_RU if lang == "ru" else WEEKDAYS_EN
    blocks = []
    week_totals: dict = {}
    for i in range(7):
        d = monday + timedelta(days=i)
        ds = d.isoformat()
        wd = weekdays[i]
        day_rows = rows_by_date.get(ds, [])
        training = [r for r in day_rows if r["exercise"] != "rest"]
        if training:
            dtype = day_name(training[0]["day_type"] or "", lang)
            cells = []
            rpe_vals = []
            for r in training:
                cells.append(f"{EXERCISE_EMOJI.get(r['exercise'], '')}{r['completed']}/{r['planned']}")
                if r["rpe"]:
                    rpe_vals.append(r["rpe"])
                d_, p_ = week_totals.get(r["exercise"], (0, 0))
                week_totals[r["exercise"]] = (d_ + (r["completed"] or 0),
                                              p_ + (r["planned"] or 0))
            rpe_str = f"  RPE {max(rpe_vals)}" if rpe_vals else ""
            main_line = f"`{d.strftime('%d.%m.%Y')} {wd}  {dtype:<9} {' '.join(cells)}{rpe_str}`"
            notes = [r["notes"] for r in training if r["notes"]]
            if notes:
                note_lines = "\n".join(f"   📝 {n}" for n in notes)
                blocks.append(f"{main_line}\n{note_lines}")
            else:
                blocks.append(main_line)
        elif day_rows:
            rest_label = day_name("Отдых", lang)
            blocks.append(f"`{d.strftime('%d.%m.%Y')} {wd}  😴 {rest_label}`")
        else:
            empty_label = t("history_empty_day", lang)
            blocks.append(f"`{d.strftime('%d.%m.%Y')} {wd}  {empty_label}`")
    history_text = "\n\n".join(blocks)
    week_total = t("history_week_total", lang, totals=_ex_totals_line(week_totals))
    return history_text + f"\n\n{week_total}"


async def _show_week(target, user, offset: int, edit: bool = False):
    """Fetch and display the weekly history for the given offset; edit the message if edit=True."""
    lang = user["lang"] or "ru"
    monday, sunday = _week_dates(offset)
    conn = await get_db()
    async with conn.execute(
        "SELECT * FROM workouts WHERE user_id=? AND date>=? AND date<=? ORDER BY date ASC",
        (user["id"], monday.isoformat(), sunday.isoformat())
    ) as cur:
        rows = await cur.fetchall()
    rows_by_date: dict = {}
    for r in rows:
        rows_by_date.setdefault(r["date"], []).append(r)

    mo_str = monday.strftime("%d.%m.%Y")
    su_str = sunday.strftime("%d.%m.%Y")

    title = t("history_title", lang, date_from=mo_str, date_to=su_str)
    body = _format_week(rows_by_date, monday, sunday, lang)
    text = f"{title}\n\n{body}"
    kb = history_nav_kb(offset, lang)

    if edit:
        await target.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="Markdown", reply_markup=kb)


def _day_cell(day_rows: list) -> str:
    """Emoji status for one calendar day: hit / partial / no data / rest."""
    training = [r for r in day_rows if r["exercise"] != "rest"]
    if training:
        targets = [r for r in training if (r["planned"] or 0) > 0]
        done_any = any((r["completed"] or 0) > 0 for r in training)
        if targets and all((r["completed"] or 0) >= r["planned"] for r in targets):
            return "🟩"
        return "🟨" if done_any else "⬜"
    if day_rows:
        return "😴"
    return "⬜"


def _month_heatmap(rows_by_date: dict, year: int, month: int, lang: str) -> str:
    """Emoji calendar for one month: one row per Mon–Sun week, up to today."""
    today = date.today()
    days_in_month = calendar.monthrange(year, month)[1]
    last_shown = today.day if (year, month) == (today.year, today.month) else days_in_month
    first_wd = date(year, month, 1).weekday()  # 0 = Monday
    cells = ["▫️"] * first_wd  # out-of-month padding so weeks stay aligned
    for day in range(1, last_shown + 1):
        ds = date(year, month, day).isoformat()
        cells.append(_day_cell(rows_by_date.get(ds, [])))
    lines = ["".join(cells[i:i + 7]) for i in range(0, len(cells), 7)]
    month_label = t("month_names", lang)[month - 1]
    return f"*{month_label} {year}*\n" + "\n".join(lines)


async def _show_monthly(target, user, edit: bool = False):
    """Fetch and display the monthly history summary (last 12 months)."""
    lang = user["lang"] or "ru"
    conn = await get_db()
    async with conn.execute(
        """SELECT strftime('%Y-%m', date) AS month, exercise,
                  SUM(completed) AS total_completed,
                  SUM(planned) AS total_planned
           FROM workouts WHERE user_id=? AND exercise != 'rest'
           GROUP BY month, exercise ORDER BY month DESC""",
        (user["id"],)
    ) as cur:
        rows = await cur.fetchall()
    async with conn.execute(
        """SELECT strftime('%Y-%m', date) AS month,
                  COUNT(DISTINCT date) AS days_trained
           FROM workouts WHERE user_id=? AND completed > 0
           GROUP BY month""",
        (user["id"],)
    ) as cur:
        days_rows = await cur.fetchall()
    days_map = {r["month"]: r["days_trained"] or 0 for r in days_rows}

    if not rows:
        text = t("history_no_data", lang)
    else:
        # Current-month emoji calendar at the top
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        async with conn.execute(
            "SELECT * FROM workouts WHERE user_id=? AND date>=? ORDER BY date ASC",
            (user["id"], month_start)
        ) as cur:
            month_rows = await cur.fetchall()
        heatmap_by_date: dict = {}
        for r in month_rows:
            heatmap_by_date.setdefault(r["date"], []).append(r)
        heatmap = _month_heatmap(heatmap_by_date, today.year, today.month, lang)

        months: dict = {}
        for r in rows:
            months.setdefault(r["month"], {})[r["exercise"]] = (
                r["total_completed"] or 0, r["total_planned"] or 0)
        lines = [t("history_monthly_title", lang), "", heatmap,
                 f"_{t('heatmap_legend', lang)}_", ""]
        for month in sorted(months, reverse=True)[:12]:
            lines.append(t("history_monthly_row", lang,
                           month=month, totals=_ex_totals_line(months[month]),
                           days=days_map.get(month, 0)))
        text = "\n".join(lines)

    kb = history_nav_kb(0, lang, monthly=True)
    if edit:
        await target.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="Markdown", reply_markup=kb)


@router.message(Command("history"))
@router.message(text_filter("btn_history"))
async def show_history(message: types.Message):
    """Show the current week's workout history when the user taps the History button."""
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    await _show_week(message, user, offset=0)


@router.callback_query(F.data == "hist_mode_monthly")
async def history_switch_monthly(callback: types.CallbackQuery):
    """Switch the history view to the monthly summary mode."""
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    await _show_monthly(callback.message, user, edit=True)
    await callback.answer()


@router.callback_query(F.data == "hist_mode_weekly")
async def history_switch_weekly(callback: types.CallbackQuery):
    """Switch the history view back to the weekly mode (current week)."""
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    await _show_week(callback.message, user, offset=0, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("hist_"))
async def history_nav(callback: types.CallbackQuery):
    """Handle prev/next week navigation callbacks and update the history message in place."""
    offset = int(callback.data[5:])
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    await _show_week(callback.message, user, offset=offset, edit=True)
    await callback.answer()
