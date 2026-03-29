import os
import sys
from datetime import datetime

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..config import ADMIN_TG_ID, ADMIN_USERNAMES, logger


def _is_admin(message) -> bool:
    if message.from_user.id == ADMIN_TG_ID:
        return True
    uname = (message.from_user.username or "").lower()
    return uname in {u.lower() for u in ADMIN_USERNAMES}
from ..db import get_db, get_lang, get_user
from ..i18n import t, text_filter
from ..keyboards import main_kb
from ..states import BugReport
from ..services.xp import md_escape

router = Router()


@router.message(Command("version"))
async def show_version(message: types.Message):
    if not _is_admin(message):
        await message.answer("⛔ Нет доступа.")
        return
    await message.answer(
        f"🧾 *Версия бота*\nPID: `{os.getpid()}`\nPython: `{sys.version.split()[0]}`\n"
        f"Время: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        parse_mode="Markdown")


@router.message(text_filter("btn_bug"))
async def bug_report_start(message: types.Message, state: FSMContext):
    from aiogram.types import ReplyKeyboardRemove
    lang = await get_lang(message.from_user.id)
    await message.answer(t("bug_prompt", lang), parse_mode="Markdown",
                         reply_markup=ReplyKeyboardRemove())
    await state.set_state(BugReport.enter_text)


@router.message(BugReport.enter_text)
async def bug_report_send(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    lang = user["lang"] or "ru" if user else "ru"
    if not user:
        await message.answer(t("register_first", "ru"))
        await state.clear()
        return
    bug_text = (message.text or "").strip()
    if not bug_text:
        await message.answer(t("bug_enter_text", lang))
        return
    conn = await get_db()
    await conn.execute("INSERT INTO bug_reports (user_id, username, text) VALUES (?,?,?)",
                       (user["id"], user["username"], bug_text))
    await conn.commit()
    try:
        def html_escape(s):
            return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe = html_escape(bug_text)
        safe_name = html_escape(user['username'] or user['first_name'] or 'unknown')
        from ..main import bot
        await bot.send_message(ADMIN_TG_ID,
            f"🐛 <b>Баг</b> от <b>{safe_name}</b>\n\n{safe}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"[bug_report] {e}")
    await message.answer(t("bug_ok", lang), parse_mode="Markdown",
                         reply_markup=main_kb(lang))
    await state.clear()


@router.message(Command("bugs"))
async def show_bugs(message: types.Message):
    if not _is_admin(message):
        await message.answer("⛔ Нет доступа.")
        return
    conn = await get_db()
    try:
        async with conn.execute("SELECT * FROM bug_reports ORDER BY created DESC LIMIT 20") as cur:
            reports = await cur.fetchall()
    except Exception as e:
        logger.warning(f"[show_bugs] {e}")
        await message.answer("Ошибка при загрузке отчётов.")
        return
    if not reports:
        await message.answer("🎉 Багов нет!")
        return
    text = "🐛 *Последние баг-репорты:*\n\n"
    for r in reports:
        e = "🔴" if r["status"] == "new" else "✅"
        safe_user = md_escape(r['username'] or 'unknown')
        safe_text = md_escape((r['text'] or '')[:100])
        text += f"{e} #{r['id']} — *{safe_user}*\n{safe_text}\n_{r['created']}_\n\n"
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("fixbug"))
async def fix_bug(message: types.Message):
    if not _is_admin(message):
        await message.answer("⛔ Нет доступа.")
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /fixbug 5")
        return
    try:
        bug_id = int(parts[1])
        conn = await get_db()
        await conn.execute("UPDATE bug_reports SET status='fixed' WHERE id=?", (bug_id,))
        await conn.commit()
        await message.answer(f"✅ Баг #{bug_id} исправлен.")
    except ValueError:
        await message.answer("❌ Введи числовой ID.")
