import asyncio
import os
import re
import sys
import time
from datetime import datetime, timedelta

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..config import ADMIN_TG_ID, ADMIN_USERNAMES, logger
from ..db import (ban_user, delete_user_by_tg_id, get_db, get_lang, get_user,
                  give_freeze_tokens, is_muted, mute_user, reset_streak,
                  reset_xp, search_users, unban_user, unmute_user,
                  get_all_users_paginated, get_bot_stats)
from ..i18n import t, text_filter
from ..keyboards import (admin_bugs_kb, admin_confirm_kb, admin_confirm_restart_kb,
                         admin_panel_main_kb, admin_user_profile_kb, admin_users_kb,
                         main_kb)
from ..states import AdminPanel, BugReport, Settings
from ..services.xp import md_escape
from .. import globals as g


def _is_admin(message) -> bool:
    if message.from_user.id == ADMIN_TG_ID:
        return True
    uname = (message.from_user.username or "").lower()
    return uname in {u.lower() for u in ADMIN_USERNAMES}


def _is_admin_cb(callback: types.CallbackQuery) -> bool:
    if callback.from_user.id == ADMIN_TG_ID:
        return True
    uname = (callback.from_user.username or "").lower()
    return uname in {u.lower() for u in ADMIN_USERNAMES}

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


# ── Admin Panel ──────────────────────────────────────────────────────────────

async def _build_main_panel_view() -> tuple:
    stats = await get_bot_stats()
    uptime_secs = int(time.monotonic() - g.BOT_START_TIME)
    h = uptime_secs // 3600
    m = (uptime_secs % 3600) // 60
    s = uptime_secs % 60
    recent = list(g.security_events)[:5]
    sec_text = ""
    if recent:
        sec_text = "\n\n<b>⚠️ Последние события безопасности:</b>\n"
        for ev in recent:
            sec_text += f"  [{ev['ts']}] {ev['type']} uid={ev['uid']} {ev.get('text','')[:30]}\n"
    text = (
        f"<b>🛡 Панель администратора</b>\n\n"
        f"⏱ Аптайм: {h}ч {m}м {s}с\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"🏋️ Активных сегодня: {stats['active_today']}\n"
        f"📋 Тренировок всего: {stats['total_workouts']}\n"
        f"🚫 Заблокировано: {stats['banned_count']}\n"
        f"Режим: {'🔧 ТЕХОБСЛУЖИВАНИЕ' if g.maintenance_mode else '✅ Работает'}"
        f"{sec_text}"
    )
    kb = admin_panel_main_kb(g.maintenance_mode)
    return text, kb


@router.message(F.text == "🛡 Панель администратора", Settings.viewing)
async def open_admin_panel(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    await state.set_state(AdminPanel.main)
    text, kb = await _build_main_panel_view()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def _show_user_profile(callback: types.CallbackQuery, state: FSMContext, tg_id: int):
    user = await get_user(tg_id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден.", reply_markup=admin_confirm_restart_kb())
        await callback.answer()
        return
    muted = await is_muted(tg_id)
    muted_until = user["muted_until"] or "—"
    text = (
        f"<b>👤 Профиль пользователя</b>\n\n"
        f"ID: <code>{user['tg_id']}</code>\n"
        f"Username: @{user['username'] or '—'}\n"
        f"Имя: {user['first_name'] or '—'}\n"
        f"Зарегистрирован: {user['joined'] or '—'}\n"
        f"Уровень: {user['level']} | XP: {user['xp']}\n"
        f"Стрик: {user['streak']} дней\n"
        f"Последняя тренировка: {user['last_workout'] or '—'}\n"
        f"Заморозок: {user['freeze_tokens']}\n"
        f"Язык: {user['lang']}\n"
        f"Статус: {'🔴 Забанен' if user['is_banned'] else ('🔇 Замучен до ' + muted_until if muted else '🟢 Активен')}"
    )
    kb = admin_user_profile_kb(tg_id, bool(user["is_banned"]), muted)
    await state.set_state(AdminPanel.user_profile)
    await state.update_data(ap_target_tg_id=tg_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("ap:"))
async def admin_panel_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin_cb(callback):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    data = callback.data
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    # ── Main dashboard ──────────────────────────────────────────────────────
    if action == "main":
        await state.set_state(AdminPanel.main)
        text, kb = await _build_main_panel_view()
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await callback.answer()

    # ── User list ───────────────────────────────────────────────────────────
    elif action == "users":
        page = int(parts[2]) if len(parts) > 2 else 0
        fsm_data = await state.get_data()
        search_query = fsm_data.get("ap_search")
        if search_query:
            all_results = await search_users(search_query)
            total = len(all_results)
            per_page = 10
            users = all_results[page * per_page:(page + 1) * per_page]
        else:
            users, total = await get_all_users_paginated(page)
        await state.set_state(AdminPanel.user_list)
        await state.update_data(ap_page=page)
        per_page = 10
        header = f"🔍 Поиск: <i>{search_query}</i>\n" if search_query else ""
        text = f"<b>👥 Пользователи</b>\n{header}Всего: {total}\n\nНажми на пользователя для управления:"
        kb = admin_users_kb(users, page, total, per_page)
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await callback.answer()

    # ── User search prompt ──────────────────────────────────────────────────
    elif action == "search":
        await state.set_state(AdminPanel.user_search)
        await state.update_data(ap_search=None)
        try:
            await callback.message.edit_text(
                "🔍 Введи имя пользователя или Telegram ID:",
                reply_markup=admin_confirm_kb("cancel_search", 0)
            )
        except TelegramBadRequest:
            pass
        await callback.answer()

    # ── User profile ────────────────────────────────────────────────────────
    elif action == "user":
        tg_id = int(parts[2])
        await _show_user_profile(callback, state, tg_id)

    # ── Ban ─────────────────────────────────────────────────────────────────
    elif action == "ban":
        tg_id = int(parts[2])
        if tg_id == ADMIN_TG_ID:
            await callback.answer("Нельзя применить к себе.", show_alert=True)
            return
        await state.update_data(ap_target_tg_id=tg_id)
        try:
            await callback.message.edit_text(
                f"🚫 Забанить пользователя <code>{tg_id}</code>?\nОн больше не сможет пользоваться ботом.",
                reply_markup=admin_confirm_kb("ban", tg_id), parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        await callback.answer()

    elif action == "confirm" and len(parts) > 3 and parts[2] == "ban":
        tg_id = int(parts[3])
        await ban_user(tg_id)
        await callback.answer("✅ Пользователь заблокирован.", show_alert=True)
        await _show_user_profile(callback, state, tg_id)

    # ── Unban ───────────────────────────────────────────────────────────────
    elif action == "unban":
        tg_id = int(parts[2])
        await state.update_data(ap_target_tg_id=tg_id)
        try:
            await callback.message.edit_text(
                f"✅ Разбанить пользователя <code>{tg_id}</code>?",
                reply_markup=admin_confirm_kb("unban", tg_id), parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        await callback.answer()

    elif action == "confirm" and len(parts) > 3 and parts[2] == "unban":
        tg_id = int(parts[3])
        await unban_user(tg_id)
        await callback.answer("✅ Пользователь разбанен.", show_alert=True)
        await _show_user_profile(callback, state, tg_id)

    # ── Mute ────────────────────────────────────────────────────────────────
    elif action == "mute":
        tg_id = int(parts[2])
        if tg_id == ADMIN_TG_ID:
            await callback.answer("Нельзя применить к себе.", show_alert=True)
            return
        await state.set_state(AdminPanel.mute_duration)
        await state.update_data(ap_target_tg_id=tg_id)
        try:
            await callback.message.edit_text(
                f"🔇 Мут пользователя <code>{tg_id}</code>\n\nВведи срок мута:\nПримеры: <code>30m</code>, <code>24h</code>, <code>7d</code>",
                reply_markup=None, parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        await callback.answer()

    # ── Unmute ──────────────────────────────────────────────────────────────
    elif action == "unmute":
        tg_id = int(parts[2])
        await unmute_user(tg_id)
        await callback.answer("✅ Мут снят.", show_alert=True)
        await _show_user_profile(callback, state, tg_id)

    # ── Reset streak ────────────────────────────────────────────────────────
    elif action == "rst_streak":
        tg_id = int(parts[2])
        if tg_id == ADMIN_TG_ID:
            await callback.answer("Нельзя применить к себе.", show_alert=True)
            return
        await state.update_data(ap_target_tg_id=tg_id)
        try:
            await callback.message.edit_text(
                f"💧 Сбросить стрик пользователя <code>{tg_id}</code> до нуля?",
                reply_markup=admin_confirm_kb("rst_streak", tg_id), parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        await callback.answer()

    elif action == "confirm" and len(parts) > 3 and parts[2] == "rst_streak":
        tg_id = int(parts[3])
        await reset_streak(tg_id)
        await callback.answer("✅ Стрик сброшен.", show_alert=True)
        await _show_user_profile(callback, state, tg_id)

    # ── Reset XP ────────────────────────────────────────────────────────────
    elif action == "rst_xp":
        tg_id = int(parts[2])
        if tg_id == ADMIN_TG_ID:
            await callback.answer("Нельзя применить к себе.", show_alert=True)
            return
        await state.update_data(ap_target_tg_id=tg_id)
        try:
            await callback.message.edit_text(
                f"📉 Сбросить XP и уровень пользователя <code>{tg_id}</code>?",
                reply_markup=admin_confirm_kb("rst_xp", tg_id), parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        await callback.answer()

    elif action == "confirm" and len(parts) > 3 and parts[2] == "rst_xp":
        tg_id = int(parts[3])
        await reset_xp(tg_id)
        await callback.answer("✅ XP и уровень сброшены.", show_alert=True)
        await _show_user_profile(callback, state, tg_id)

    # ── Give/remove freeze tokens ───────────────────────────────────────────
    elif action == "tokens":
        tg_id = int(parts[2])
        await state.set_state(AdminPanel.give_tokens)
        await state.update_data(ap_target_tg_id=tg_id)
        try:
            await callback.message.edit_text(
                f"🧊 Токены заморозки для <code>{tg_id}</code>\n\nВведи число (+ добавить, - убрать):\nПример: <code>3</code> или <code>-1</code>",
                reply_markup=None, parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        await callback.answer()

    # ── Delete user ─────────────────────────────────────────────────────────
    elif action == "delete":
        tg_id = int(parts[2])
        if tg_id == ADMIN_TG_ID:
            await callback.answer("Нельзя применить к себе.", show_alert=True)
            return
        await state.update_data(ap_target_tg_id=tg_id)
        try:
            await callback.message.edit_text(
                f"🗑 Удалить аккаунт <code>{tg_id}</code>?\nВсе данные будут стёрты, пользователь не сможет перерегистрироваться.",
                reply_markup=admin_confirm_kb("delete", tg_id), parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        await callback.answer()

    elif action == "confirm" and len(parts) > 3 and parts[2] == "delete":
        tg_id = int(parts[3])
        await delete_user_by_tg_id(tg_id, permanent_ban=True)
        await callback.answer("✅ Аккаунт удалён и заблокирован.", show_alert=True)
        await state.set_state(AdminPanel.user_list)
        fsm_data = await state.get_data()
        page = fsm_data.get("ap_page", 0)
        users, total = await get_all_users_paginated(page)
        text = f"<b>👥 Пользователи</b>\nВсего: {total}"
        kb = admin_users_kb(users, page, total)
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            pass

    # ── Stats ───────────────────────────────────────────────────────────────
    elif action == "stats":
        stats = await get_bot_stats()
        uptime_secs = int(time.monotonic() - g.BOT_START_TIME)
        h = uptime_secs // 3600
        m_up = (uptime_secs % 3600) // 60
        s_up = uptime_secs % 60
        sec_list = list(g.security_events)[:10]
        sec_text = ""
        if sec_list:
            sec_text = "\n\n<b>⚠️ События безопасности:</b>\n"
            for ev in sec_list:
                sec_text += f"  [{ev['ts']}] {ev['type']} uid={ev['uid']} {ev.get('text','')[:25]}\n"
        text = (
            f"<b>📊 Статистика бота</b>\n\n"
            f"⏱ Аптайм: {h}ч {m_up}м {s_up}с\n"
            f"👥 Всего пользователей: {stats['total_users']}\n"
            f"🏋️ Активных сегодня: {stats['active_today']}\n"
            f"📋 Тренировок всего: {stats['total_workouts']}\n"
            f"🚫 Заблокировано: {stats['banned_count']}"
            f"{sec_text}"
        )
        from aiogram.utils.keyboard import InlineKeyboardBuilder as _IKB
        b_back = _IKB()
        b_back.button(text="◀◀ Главная", callback_data="ap:main")
        try:
            await callback.message.edit_text(text, reply_markup=b_back.as_markup(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await callback.answer()

    # ── Bug reports ─────────────────────────────────────────────────────────
    elif action == "bugs":
        page = int(parts[2]) if len(parts) > 2 else 0
        per_page = 10
        conn = await get_db()
        async with conn.execute(
            "SELECT * FROM bug_reports ORDER BY created DESC LIMIT ? OFFSET ?",
            (per_page + 1, page * per_page)
        ) as cur:
            reports = await cur.fetchall()
        has_more = len(reports) > per_page
        reports = reports[:per_page]
        await state.set_state(AdminPanel.bug_list)
        text = f"<b>🐛 Баг-репорты</b> (стр. {page + 1})\nНажми на баг чтобы пометить исправленным:"
        kb = admin_bugs_kb(reports, page, has_more)
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await callback.answer()

    elif action == "fix_bug":
        bug_id = int(parts[2])
        conn = await get_db()
        async with conn.execute("SELECT status FROM bug_reports WHERE id=?", (bug_id,)) as cur:
            row = await cur.fetchone()
        if row:
            new_status = "fixed" if row["status"] == "new" else "new"
            await conn.execute("UPDATE bug_reports SET status=? WHERE id=?", (new_status, bug_id))
            await conn.commit()
        await callback.answer(f"✅ Баг #{bug_id} обновлён.", show_alert=False)
        # Reload bug list
        per_page = 10
        async with conn.execute(
            "SELECT * FROM bug_reports ORDER BY created DESC LIMIT ?", (per_page + 1,)
        ) as cur:
            reports = await cur.fetchall()
        has_more = len(reports) > per_page
        reports = reports[:per_page]
        kb = admin_bugs_kb(reports, 0, has_more)
        try:
            await callback.message.edit_reply_markup(reply_markup=kb)
        except TelegramBadRequest:
            pass

    # ── Broadcast prompt ────────────────────────────────────────────────────
    elif action == "broadcast":
        await state.set_state(AdminPanel.broadcast)
        try:
            await callback.message.edit_text(
                "📢 <b>Рассылка</b>\n\nВведи текст сообщения для отправки всем активным пользователям:",
                reply_markup=None, parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        await callback.answer()

    # ── Restart ─────────────────────────────────────────────────────────────
    elif action == "restart":
        try:
            await callback.message.edit_text(
                "🔄 Перезапустить бот?\nВсе текущие сессии будут прерваны.",
                reply_markup=admin_confirm_restart_kb()
            )
        except TelegramBadRequest:
            pass
        await callback.answer()

    elif action == "confirm_restart":
        try:
            await callback.message.edit_text("🔄 Перезапуск бота...")
        except TelegramBadRequest:
            pass
        await callback.answer("Перезапуск...")
        from ..db import close_db
        await close_db()
        os.execv(sys.executable, [sys.executable, "-m", "pullup_bot"])

    # ── Maintenance toggle ──────────────────────────────────────────────────
    elif action == "maintenance":
        g.maintenance_mode = not g.maintenance_mode
        await callback.answer(
            f"{'🔧 Техобслуживание включено' if g.maintenance_mode else '✅ Бот снова в работе'}",
            show_alert=True
        )
        text, kb = await _build_main_panel_view()
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            pass

    # ── Navigation ──────────────────────────────────────────────────────────
    elif action == "back_to_users":
        fsm_data = await state.get_data()
        page = fsm_data.get("ap_page", 0)
        users, total = await get_all_users_paginated(page)
        await state.set_state(AdminPanel.user_list)
        text = f"<b>👥 Пользователи</b>\nВсего: {total}"
        kb = admin_users_kb(users, page, total)
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await callback.answer()

    elif action == "cancel_confirm":
        fsm_data = await state.get_data()
        tg_id = fsm_data.get("ap_target_tg_id")
        if tg_id:
            await _show_user_profile(callback, state, tg_id)
        else:
            await state.set_state(AdminPanel.main)
            text, kb = await _build_main_panel_view()
            try:
                await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except TelegramBadRequest:
                pass
            await callback.answer()

    elif action == "close":
        await state.clear()
        try:
            await callback.message.edit_text("🛡 Панель закрыта.", reply_markup=None)
        except TelegramBadRequest:
            pass
        await callback.answer()

    else:
        await callback.answer()


# ── Admin panel text input handlers ─────────────────────────────────────────

@router.message(AdminPanel.user_search)
async def admin_search_input(message: types.Message, state: FSMContext):
    query = (message.text or "").strip()
    if not query:
        await message.answer("Введи имя или ID.")
        return
    results = await search_users(query)
    await state.update_data(ap_search=query, ap_page=0)
    await state.set_state(AdminPanel.user_list)
    total = len(results)
    per_page = 10
    page_results = results[:per_page]
    text = f"<b>🔍 Результаты поиска: {query}</b>\nНайдено: {total}"
    kb = admin_users_kb(page_results, 0, total, per_page)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(AdminPanel.broadcast)
async def admin_broadcast_input(message: types.Message, state: FSMContext):
    text = message.text or ""
    if not text.strip():
        await message.answer("Текст не может быть пустым.")
        return
    from ..main import bot
    conn = await get_db()
    async with conn.execute(
        "SELECT tg_id FROM users WHERE is_logged_out=0 AND is_banned=0"
    ) as cur:
        users = await cur.fetchall()
    sent = failed = 0
    for u in users:
        try:
            await bot.send_message(u["tg_id"], text)
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            failed += 1
        except Exception:
            failed += 1
    await state.set_state(AdminPanel.main)
    report_text, kb = await _build_main_panel_view()
    await message.answer(
        f"📢 Рассылка завершена.\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}",
    )
    await message.answer(report_text, reply_markup=kb, parse_mode="HTML")


@router.message(AdminPanel.mute_duration)
async def admin_mute_duration_input(message: types.Message, state: FSMContext):
    text = (message.text or "").strip().lower()
    m = re.match(r'^(\d+)(h|d|m)$', text)
    if not m:
        await message.answer("Неверный формат. Примеры: 30m, 24h, 7d")
        return
    amount = int(m.group(1))
    unit = m.group(2)
    if unit == "m":
        delta = timedelta(minutes=amount)
    elif unit == "h":
        delta = timedelta(hours=amount)
    else:
        delta = timedelta(days=amount)
    if delta.total_seconds() > 30 * 24 * 3600:
        await message.answer("Максимальный срок мута — 30 дней.")
        return
    until = (datetime.now() + delta).isoformat()
    fsm_data = await state.get_data()
    tg_id = fsm_data.get("ap_target_tg_id")
    if tg_id:
        await mute_user(tg_id, until)
        await message.answer(f"🔇 Пользователь <code>{tg_id}</code> замучен до {until[:16]}", parse_mode="HTML")
    await state.set_state(AdminPanel.main)
    text_panel, kb = await _build_main_panel_view()
    await message.answer(text_panel, reply_markup=kb, parse_mode="HTML")


@router.message(AdminPanel.give_tokens)
async def admin_give_tokens_input(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    try:
        delta = int(text)
    except ValueError:
        await message.answer("Введи целое число (например: 3 или -1).")
        return
    fsm_data = await state.get_data()
    tg_id = fsm_data.get("ap_target_tg_id")
    if tg_id:
        await give_freeze_tokens(tg_id, delta)
        action_word = "добавлено" if delta >= 0 else "убрано"
        await message.answer(f"🧊 {abs(delta)} токенов {action_word} пользователю <code>{tg_id}</code>", parse_mode="HTML")
    await state.set_state(AdminPanel.main)
    text_panel, kb = await _build_main_panel_view()
    await message.answer(text_panel, reply_markup=kb, parse_mode="HTML")
