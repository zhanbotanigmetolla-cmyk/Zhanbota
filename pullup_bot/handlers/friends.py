import random
from datetime import date, timedelta

from aiogram import Router, types
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext

from ..db import get_db, get_today_workout, get_user
from ..i18n import t, text_filter
from ..keyboards import main_kb
from ..services.xp import display, level_info, md_escape, planned_for_day
from ..config import logger
from ..states import Friends

router = Router()

PAGE_SIZE = 8


async def _show_friends_page(message: types.Message, state: FSMContext, user, page: int):
    lang = user["lang"] or "ru"
    conn = await get_db()
    async with conn.execute("SELECT * FROM users ORDER BY id ASC") as cur:
        all_users = await cur.fetchall()

    if not all_users:
        await message.answer(t("friends_empty", lang), parse_mode="Markdown")
        return

    total_pages = max(1, (len(all_users) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    page_users = all_users[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    today_str = date.today().isoformat()
    you_label = "Вы" if lang == "ru" else "You"

    header = t("friends_title", lang)
    if total_pages > 1:
        header += f"  _{t('friends_page', lang, page=page + 1, total=total_pages)}_"
    text = header + "\n\n"

    for f in page_users:
        today_w = await get_today_workout(f["id"])
        done = today_w["completed"] if today_w else 0
        if today_w:
            plan = today_w["planned"] if today_w["planned"] is not None else 0
        elif f["last_workout"] == today_str:
            plan = 0
        else:
            plan, _ = planned_for_day(f)
        _, lname, _, _ = level_info(f["xp"])
        today_label = "Сегодня" if lang == "ru" else "Today"
        is_me = f["id"] == user["id"]
        me_marker = f" *({you_label})*" if is_me else ""
        text += f"👤 *{md_escape(display(f))}*{me_marker} — {lname}\n   {today_label}: {done}/{plan} | 🔥{f['streak']}\n\n"

    poke_prefix = "💪 Пнуть " if lang == "ru" else "💪 Poke "
    b = ReplyKeyboardBuilder()
    for f in page_users:
        if f["id"] == user["id"]:
            continue
        label = f"{poke_prefix}{display(f)} (#{f['id']})"
        b.button(text=label)
    b.adjust(2)

    nav = []
    if page > 0:
        nav.append(KeyboardButton(text=t("btn_friends_prev", lang)))
    if page < total_pages - 1:
        nav.append(KeyboardButton(text=t("btn_friends_next", lang)))
    if nav:
        b.row(*nav)
    b.row(KeyboardButton(text=t("btn_back", lang)))

    await state.set_state(Friends.viewing)
    await state.update_data(friends_page=page, friends_lang=lang)
    await message.answer(text, parse_mode="Markdown",
                         reply_markup=b.as_markup(resize_keyboard=True))


@router.message(Friends.viewing, text_filter("btn_friends_prev"))
async def friends_prev(message: types.Message, state: FSMContext):
    data = await state.get_data()
    page = data.get("friends_page", 0)
    user = await get_user(message.from_user.id)
    if not user:
        return
    await _show_friends_page(message, state, user, page - 1)


@router.message(Friends.viewing, text_filter("btn_friends_next"))
async def friends_next(message: types.Message, state: FSMContext):
    data = await state.get_data()
    page = data.get("friends_page", 0)
    user = await get_user(message.from_user.id)
    if not user:
        return
    await _show_friends_page(message, state, user, page + 1)


@router.message(Friends.viewing, text_filter("btn_back"))
async def friends_back(message: types.Message, state: FSMContext):
    await state.clear()
    from ..db import get_lang
    lang = await get_lang(message.from_user.id)
    await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))


@router.message(text_filter("btn_friends"))
async def friends_menu(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    await _show_friends_page(message, state, user, 0)


@router.message(text_filter("btn_leaderboard"))
async def leaderboard(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    lang = user["lang"] or "ru"
    conn = await get_db()
    async with conn.execute("SELECT * FROM users", ()) as cur:
        all_users = await cur.fetchall()

    if not all_users:
        await message.answer(t("leaderboard_empty", lang), parse_mode="Markdown",
                             reply_markup=main_kb(lang))
        return

    week_ago = (date.today() - timedelta(days=7)).isoformat()
    entries = []
    for u in all_users:
        async with conn.execute(
            "SELECT COALESCE(SUM(completed), 0) as week_done FROM workouts "
            "WHERE user_id=? AND date>=?", (u["id"], week_ago)
        ) as cur:
            row = await cur.fetchone()
        week_done = row["week_done"] if row else 0
        _, lname, _, _ = level_info(u["xp"])
        entries.append((u, week_done, lname))

    entries.sort(key=lambda x: x[1], reverse=True)

    text = t("leaderboard_title", lang) + "\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (u, week_done, lname) in enumerate(entries):
        medal = medals[i] if i < 3 else f"{i+1}."
        you = t("leaderboard_you_marker", lang) if u["tg_id"] == message.from_user.id else ""
        crown = " 👑" if u["is_weekly_champ"] else ""
        text += f"{medal} *{md_escape(display(u))}*{crown} — {week_done} | 🔥{u['streak']}{you}\n"

    await message.answer(text, parse_mode="Markdown", reply_markup=main_kb(lang))


@router.message(lambda m: m.text and (m.text.startswith("💪 Пнуть ") or m.text.startswith("💪 Poke ")))
async def poke_friend(message: types.Message, state: FSMContext):
    import re
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    lang = user["lang"] or "ru"
    raw = message.text
    for prefix in ("💪 Пнуть ", "💪 Poke "):
        if raw.startswith(prefix):
            raw = raw[len(prefix):].strip()
            break
    conn = await get_db()
    m_user = re.search(r"\(@([A-Za-z0-9_]{1,32})\)$", raw)
    m_id = re.search(r"\(#(\d+)\)$", raw)
    if m_user:
        async with conn.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE",
                                (m_user.group(1),)) as cur:
            friend = await cur.fetchone()
    elif m_id:
        async with conn.execute("SELECT * FROM users WHERE id=?",
                                (int(m_id.group(1)),)) as cur:
            friend = await cur.fetchone()
    else:
        async with conn.execute("SELECT * FROM users WHERE first_name=? OR username=?",
                                (raw, raw)) as cur:
            friend = await cur.fetchone()
    if not friend:
        await message.answer(t("friends_not_found", lang))
        return

    today = date.today().isoformat()
    async with conn.execute(
        "SELECT 1 FROM pokes WHERE from_user_id=? AND to_user_id=? AND date=?",
        (user["id"], friend["id"], today)
    ) as cur:
        already_poked = await cur.fetchone()
    if already_poked:
        await message.answer(t("poke_already_today", lang, name=md_escape(display(friend))))
        return

    friend_lang = friend["lang"] or "ru"
    poke_msgs = t("poke_msgs", friend_lang)
    from ..main import bot
    try:
        poke_text = random.choice(poke_msgs) if isinstance(poke_msgs, list) else poke_msgs
        await bot.send_message(friend["tg_id"],
            f"📣 *{md_escape(display(user))}* {'пнул тебя' if friend_lang == 'ru' else 'poked you'}:\n\n{poke_text}",
            parse_mode="Markdown")
        await conn.execute(
            "INSERT OR IGNORE INTO pokes (from_user_id, to_user_id, date) VALUES (?,?,?)",
            (user["id"], friend["id"], today)
        )
        await conn.commit()
        await message.answer(t("friends_poke_sent", lang, name=md_escape(display(friend))))
    except TelegramForbiddenError:
        await message.answer(t("friends_blocked", lang))
    except Exception:
        await message.answer(t("friends_error", lang))
