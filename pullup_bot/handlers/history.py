from datetime import date, timedelta

from aiogram import F, Router, types

from ..db import get_db, get_user
from ..i18n import t, text_filter, day_name
from ..keyboards import history_nav_kb, main_kb


router = Router()

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAYS_EN = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def _week_dates(offset: int):
    """Return (monday, sunday) date objects for the week at the given offset from the current week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _format_week(rows_by_date: dict, monday: date, sunday: date, lang: str) -> str:
    """Format one week of workout data as a Markdown code-block table with a weekly total footer."""
    weekdays = WEEKDAYS_RU if lang == "ru" else WEEKDAYS_EN
    blocks = []
    total_done = 0
    total_planned = 0
    for i in range(7):
        d = monday + timedelta(days=i)
        ds = d.isoformat()
        wd = weekdays[i]
        r = rows_by_date.get(ds)
        if r:
            done = r["completed"]
            planned = r["planned"]
            dtype = day_name(r["day_type"] or "", lang)
            rpe_str = f"  RPE {r['rpe']}" if r["rpe"] else ""
            main_line = f"`{d.strftime('%d.%m.%Y')} {wd}  {dtype:<9} {done}/{planned}{rpe_str}`"
            if r["notes"]:
                note_line = f"   📝 {r['notes']}"
                blocks.append(f"{main_line}\n{note_line}")
            else:
                blocks.append(main_line)
            total_done += done
            total_planned += planned
        else:
            empty_label = t("history_empty_day", lang)
            blocks.append(f"`{d.strftime('%d.%m.%Y')} {wd}  {empty_label}`")
    history_text = "\n\n".join(blocks)
    pct = int(total_done / total_planned * 100) if total_planned else 0
    week_total = t("history_week_total", lang, done=total_done, planned=total_planned, pct=pct)
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
    rows_by_date = {r["date"]: r for r in rows}

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


async def _show_monthly(target, user, edit: bool = False):
    """Fetch and display the monthly history summary (last 12 months)."""
    lang = user["lang"] or "ru"
    conn = await get_db()
    async with conn.execute(
        """SELECT strftime('%Y-%m', date) AS month,
                  SUM(completed) AS total_completed,
                  SUM(planned) AS total_planned,
                  COUNT(CASE WHEN completed > 0 AND day_type != 'Отдых' THEN 1 END) AS days_trained
           FROM workouts WHERE user_id=?
           GROUP BY month ORDER BY month DESC LIMIT 12""",
        (user["id"],)
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        text = t("history_no_data", lang)
    else:
        lines = [t("history_monthly_title", lang)]
        lines.append("")
        for r in rows:
            done = r["total_completed"] or 0
            planned = r["total_planned"] or 0
            pct = int(done / planned * 100) if planned else 0
            days = r["days_trained"] or 0
            lines.append(t("history_monthly_row", lang,
                           month=r["month"], done=done,
                           planned=planned, pct=pct, days=days))
        text = "\n".join(lines)

    kb = history_nav_kb(0, lang, monthly=True)
    if edit:
        await target.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="Markdown", reply_markup=kb)


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
