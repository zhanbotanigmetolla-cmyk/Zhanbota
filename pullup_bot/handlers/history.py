from datetime import date, timedelta

from aiogram import F, Router, types

from ..db import get_db, get_user
from ..i18n import t, text_filter, day_name
from ..keyboards import history_nav_kb, main_kb
from ..services.xp import md_escape

router = Router()

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAYS_EN = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def _week_dates(offset: int):
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _format_week(rows_by_date: dict, monday: date, sunday: date, lang: str) -> str:
    weekdays = WEEKDAYS_RU if lang == "ru" else WEEKDAYS_EN
    lines = []
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
            if planned == 0:
                em = "😴"
            elif done >= planned:
                em = "✅"
            else:
                em = "❌"
            note_str = f"\n  📝 {md_escape(r['notes'])}" if r["notes"] else ""
            lines.append(f"`{em} {d.strftime('%d.%m.%Y')} {wd}  {dtype:<9} {done}/{planned}{rpe_str}`{note_str}")
            total_done += done
            total_planned += planned
        else:
            empty_label = t("history_empty_day", lang)
            lines.append(f"`—  {d.strftime('%d.%m.%Y')} {wd}  {empty_label}`")
    history_text = "\n".join(lines)
    pct = int(total_done / total_planned * 100) if total_planned else 0
    week_total = t("history_week_total", lang, done=total_done, planned=total_planned, pct=pct)
    return history_text + f"\n\n{week_total}"


async def _show_week(target, user, offset: int, edit: bool = False):
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


@router.message(text_filter("btn_history"))
async def show_history(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    await _show_week(message, user, offset=0)


@router.callback_query(F.data.startswith("hist_"))
async def history_nav(callback: types.CallbackQuery):
    offset = int(callback.data[5:])
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    await _show_week(callback.message, user, offset=offset, edit=True)
    await callback.answer()
