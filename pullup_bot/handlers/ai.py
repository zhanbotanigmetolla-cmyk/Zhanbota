import asyncio
import random

from aiogram import Router, types as aiogram_types
from aiogram.fsm.context import FSMContext

from ..config import logger
from ..db import get_db, get_user, log_ai_usage
from ..i18n import t, text_filter
from ..keyboards import ai_chat_kb, back_only_kb, main_kb
from ..services.xp import display, level_info, planned_for_day
from ..services.gemini import get_manager, RATE_LIMIT_DAILY, RATE_LIMIT_MINUTE
from ..states import AIChat

router = Router()

MAX_HISTORY_TURNS = 10

# ---------------------------------------------------------------------------
# Funny waiting phrases — shown randomly while Gemini thinks
# ---------------------------------------------------------------------------

_WAITING_RU = [
    "🌌 Жду ответа от космоса...",
    "⚡ Ещё пару фемтосекунд, принимаю лазерные сигналы...",
    "🐕 Оказывается, ждать приходится дольше, чем Хатико...",
    "🍳 Готовлю еду, ещё пару секунд, пожалуйста...",
    "🧠 Нейроны перегрелись, охлаждаю...",
    "🔭 Ищу ответ в параллельной вселенной...",
    "☕ Завариваю кофе, пока жду ответа...",
    "🚀 Сигнал летит туда-обратно несколько раз...",
    "🎲 Считаю нейроны вручную, не торопи...",
    "📡 Связь установлена, данные передаются...",
    "🐢 Быстрее черепахи, медленнее света — нормально...",
    "🌀 Завис в квантовой суперпозиции, скоро определюсь...",
    "🛸 Жду ответа от международной космической станции...",
    "🧩 Складываю пазл из твоих тренировок по кусочку...",
    "📊 Перебираю 100500 возможных ответов, выбираю лучший...",
    "🌊 Медитирую над твоим вопросом у воображаемого океана...",
    "🐌 Быстрее уже не могу, это физически невозможно...",
    "🦾 Качаю бицепс пока думаю над ответом...",
    "🎵 Напеваю себе под нос чтоб лучше думалось...",
    "⚙️ Прогреваю двигатели интеллекта...",
    "🌙 Консультируюсь с луной по твоему вопросу...",
    "📚 Листаю 100500 страниц по теме подтягиваний...",
    "🏋️ Сам подтягиваюсь пока жду ответа от серверов...",
    "🤔 Думаю так усердно, что дым пошёл...",
    "⏰ Тик-так, тик-так... нет, серьёзно, уже скоро...",
    "🔬 Провожу анализ на молекулярном уровне...",
    "💫 Звёзды выстраиваются в нужную конфигурацию...",
    "🎯 Прицеливаюсь в идеальный ответ с лазерной точностью...",
    "🧊 Замёрз ненадолго, уже оттаиваю...",
    "🌍 Запрашиваю консультацию у всех континентов...",
    "🔭 Определяюсь с теорией неопределённости. А пока, придётся подождать неопределённое время...",
]

_WAITING_EN = [
    "🌌 Waiting for a signal from outer space...",
    "⚡ Just a few femtoseconds, receiving laser data...",
    "🐕 Turns out the wait is longer than Hachiko's...",
    "🍳 Cooking dinner, just a couple more seconds please...",
    "🧠 Neurons overheated, cooling down...",
    "🔭 Searching for the answer in a parallel universe...",
    "☕ Brewing coffee while waiting for the reply...",
    "🚀 Signal bouncing off the server a few times...",
    "🎲 Counting neurons manually, don't rush me...",
    "📡 Connection established, transmitting...",
    "🐢 Faster than a turtle, slower than light — it's fine...",
    "🌀 Stuck in quantum superposition, deciding soon...",
    "🛸 Waiting for a reply from the International Space Station...",
    "🧩 Assembling your training data piece by piece...",
    "📊 Scanning through 100500 possible answers, picking the best...",
    "🌊 Meditating on your question by an imaginary ocean...",
    "🐌 Can't go faster, this is physically impossible...",
    "🦾 Doing curls while thinking about your answer...",
    "🎵 Humming to myself to think better...",
    "⚙️ Warming up the intelligence engines...",
    "🌙 Consulting the moon about your question...",
    "📚 Flipping through 100500 pages on pull-up training...",
    "🏋️ Doing pull-ups myself while waiting for the server...",
    "🤔 Thinking so hard smoke is starting to come out...",
    "⏰ Tick-tock, tick-tock... seriously though, almost there...",
    "🔬 Running analysis at the molecular level...",
    "💫 Stars aligning in the right configuration...",
    "🎯 Laser-targeting the perfect answer...",
    "🧊 Froze for a moment, thawing now...",
    "🌍 Consulting all continents for advice...",
    "🔭 Figuring out the uncertainty principle. In the meantime, you'll have to wait an indeterminate amount of time...",
]


async def _wait_with_updates(task: asyncio.Task, thinking_msg, lang: str) -> tuple:
    """
    Phase 1: keep original 'thinking' message for 3 seconds.
    Phase 2: cycle through ALL funny phrases in shuffled order (no repeats
             until the full pool is exhausted), then reshuffle and repeat.
    """
    # Phase 1 — original message, 3 seconds
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=3)
    except asyncio.TimeoutError:
        pass

    # Phase 2 — smart-random phrase cycling
    pool = (_WAITING_RU if lang == "ru" else _WAITING_EN)[:]
    random.shuffle(pool)
    idx = 0

    while not task.done():
        phrase = pool[idx % len(pool)]
        idx += 1
        # Reshuffle only after the entire pool has been shown
        if idx % len(pool) == 0:
            random.shuffle(pool)
        try:
            await thinking_msg.edit_text(phrase)
        except Exception:
            pass
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=6)
        except asyncio.TimeoutError:
            pass

    return await task


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_TEMPLATE = """You are Turnikmen AI — the built-in intelligent assistant for the Turnikmen / Pullup Bot, a Telegram-based pullup training application.

## BOT KNOWLEDGE BASE

### What Turnikmen does
Turnikmen helps users systematically increase their pullup count through smart progressive overload and wave periodization. Users log workouts daily and the bot auto-adjusts their training plan based on performance and RPE ratings.

### 7-day wave training cycle
Every user follows a repeating weekly pattern based on their personal daily base pullup count:
- Day 1 Medium: 100% of base — standard effort day
- Day 2 Light: 50% of base — active recovery
- Day 3 Heavy: 115% of base — push day
- Day 4 Rest: 0 pullups — mandatory recovery
- Day 5 Density: 100% spread across many short sets throughout the day
- Day 6 Light: 50% of base — easy day
- Day 7 Rest: 0 pullups — mandatory recovery

### Automatic progression rules
- Cycle progression (+5% base): fires every 7-day cycle when avg completion ≥90% across the last 5 real training sessions
- RPE too high (−5% base): triggers when the 3-session rolling avg RPE ≥8.5
- RPE too low (+3% base): triggers when 3-session rolling avg RPE ≤4.5 AND all sessions fully completed
- Extra activity reduction: logging running/cardio/gym after training reduces tomorrow's load proportionally

### RPE — Rate of Perceived Exertion
After each workout the user rates effort 1–10.
1–3 = very easy, 4–6 = moderate, 7–8 = hard, 9–10 = near maximum / failure.
The bot uses a rolling 3-session average to adjust load smoothly.

### XP and CS:GO-style ranks
XP earned: +1 XP per pullup completed, +50 XP per consecutive streak day.
18 ranks:
Silver I (0 XP) → Silver II (500) → Silver III (1,000) → Silver IV (1,800) → Silver Elite (2,800) → Silver Elite Master (4,000) → Gold Nova I (5,500) → Gold Nova II (7,500) → Gold Nova III (10,000) → Gold Nova Master (13,500) → Master Guardian I (18,000) → Master Guardian II (23,000) → Master Guardian Elite (29,000) → Distinguished Master Guardian / DMG (36,000) → Legendary Eagle (44,000) → Legendary Eagle Master / LEM (53,000) → Supreme Master First Class / SMFC (63,000) → The Global Elite (70,000 XP)

### Streak & Freeze tokens
- Streak: consecutive days the user trained OR acknowledged a rest day
- Missed day without a token → streak resets to 0
- Freeze tokens: spending one saves the streak for a missed day
- Earn: every 7-day streak milestone, on each rank-up, on a new personal record; max 5

### Кочка недели / Beast of the Week
Every Monday 08:00 the user with the most pullups in the past 7 days is crowned champion. 👑 badge in stats and leaderboard until next Monday.

### Friends vs Leaderboard
- Friends (👥): everyone's today status — target, done so far, streak. Live daily view.
- Leaderboard (🏆): weekly ranking by total pullups. Competitive weekly scoreboard.

### Navigation & UI — Main menu buttons
After logging in the user sees these buttons:
- 🏋️ Тренировка / Training — starts or continues today's training session
- 📊 Статистика / Statistics — shows rank, XP progress bar, streak, today's target, 7-day history, next 7-day schedule
- 📋 История / History — full workout history browsable by week (← → navigation)
- 👥 Друзья / Friends — all participants with today's live progress
- 🤖 Турникмен AI / Turnikmen AI — opens this AI chat
- ⚙️ Настройки / Settings — user settings panel
- 🐛 Сообщить о баге / Report a Bug — submit a bug report or feature suggestion
- 🏆 Рейтинг / Leaderboard — weekly pullup ranking
- ◀️ Назад / Back — returns to the landing screen

### Navigation & UI — Settings menu
Opened via ⚙️ Настройки / Settings:
- 🔔 Время уведомлений / Notification Time — set daily reminder time, format HH:MM (e.g. 08:00)
- 📊 Изменить базу / Change Base — update the daily pullup target (the number the wave cycle is based on)
- ⚖️ Изменить вес / Change Weight — update body weight in kg
- ✏️ Изменить имя / Change Name — change the display name shown in the friends list and leaderboard
- 📝 Редактировать день / Edit Day — edit any past workout: enter date as DD.MM, then corrected reps, RPE, activity, notes; entering 0 reps deletes the record
- 📅 Причина пропуска / Skip Reason — log a reason for a missed day (illness, travel, etc.) which can restore the streak
- 🚪 Выйти из системы / Log Out — pauses the bot; data and streak are preserved
- 🌐 Язык / Language — switch interface language between Russian and English
- 🗑 Удалить аккаунт / Delete Account — permanently erases all data

### Guide and About
- 📖 Как начать / Getting Started — multi-page beginner guide (accessible from the landing screen before login and from the main menu)
- ℹ️ О боте / About — 3-page overview of the bot's features, XP system, and rank table

### Bug reports and underdeveloped features
If the user describes something that sounds like a bug, unexpected behavior, missing functionality, or an improvement they'd like to see, gently mention: «Если хочешь сообщить об этом — нажми 🐛 в главном меню, там можно описать баг или предложить улучшение» / "If you'd like to report this, tap 🐛 in the main menu — you can describe the bug or suggest an improvement there."

---

## THIS USER'S CURRENT DATA

{user_data_block}

---

## INSTRUCTIONS
- Respond in the user's preferred language (shown above), unless they write in a different language — then match theirs
- Be conversational, direct, and motivating
- When giving training advice, use the user's actual numbers (base, streak, recent RPE, rank, notes)
- Keep responses concise (2–4 sentences) unless the user asks for a detailed plan or explanation
- If asked how to do something in the bot, describe the exact button path (e.g. "open ⚙️ Settings → ✏️ Изменить имя")
- Never fabricate training data — only reference what is in the user data block above
"""


def _user_data_block(user, workouts) -> str:
    from datetime import date as _date
    lang = user["lang"] or "ru"
    lvl, lname, to_nxt, _ = level_info(user["xp"] or 0)
    lang_label = "Russian" if lang == "ru" else "English"

    # Use today's actual DB row if it exists (program_day may already be advanced
    # past a rest day that was just acknowledged, making planned_for_day lie).
    today_str = str(_date.today())
    today_row = next((r for r in workouts if r["date"] == today_str), None)
    if today_row:
        today_type = today_row["day_type"] or "?"
        today_summary = f"{today_type} — {today_row['completed']}/{today_row['planned']} pullups (done/planned)"
    else:
        today_plan, today_type = planned_for_day(user)
        today_summary = f"{today_type} — {today_plan} pullups planned"

    # Tomorrow: mirror stats.py — if today's row already exists, program_day has already
    # advanced to tomorrow's slot, so no extra +1 is needed (pd_offset cancels it).
    pd_offset = -1 if today_row else 0
    next_user = {**dict(user), "program_day": ((user["program_day"] or 0) + 1 + pd_offset) % 7}
    next_plan, next_type = planned_for_day(next_user)

    history_lines = []
    for r in workouts:
        d = r['date']  # YYYY-MM-DD → DD.MM
        date_fmt = f"{d[8:10]}.{d[5:7]}"
        line = f"  {date_fmt}  {(r['day_type'] or '?'):10s}  {r['completed']}/{r['planned']}  RPE={r['rpe'] or '—'}"
        if r["extra_activity"]:
            line += f"  activity={r['extra_activity']}"
        if r["notes"]:
            line += f"  note: {r['notes']}"
        history_lines.append(line)

    return (
        f"Name: {display(user)}\n"
        f"Rank: {lname}  ({user['xp'] or 0} XP — {to_nxt} XP to next rank)\n"
        f"Streak: {user['streak'] or 0} days  |  Freeze tokens: {user['freeze_tokens'] or 0}  |  Personal record: {user['personal_record'] or 0} pullups\n"
        f"Daily base: {user['base_pullups']} pullups/day  |  Weight: {user['weight_kg']} kg\n"
        f"Today: {today_summary}\n"
        f"Tomorrow: {next_type} — {next_plan} pullups planned\n\n"
        f"Last {len(workouts)} workouts (newest first):\n"
        + ("\n".join(history_lines) if history_lines else "  No workouts yet.") + "\n\n"
        f"Preferred language: {lang_label}"
    )



def _resolve_reply(raw: str, lang: str) -> str:
    if raw == RATE_LIMIT_DAILY:
        return t("ai_limit_daily", lang)
    if raw == RATE_LIMIT_MINUTE:
        return t("ai_limit_minute", lang)
    if not raw:
        return t("ai_unavailable", lang)
    return raw


async def _send_reply(message, thinking_msg, reply: str, lang: str, history: list,
                      user_text: str, state: FSMContext,
                      user_id: int = 0, model_used: str = ""):
    """Update history, delete thinking indicator, send the AI reply."""
    new_history = history + [
        {"role": "user",  "content": user_text},
        {"role": "model", "content": reply},
    ]
    if len(new_history) > MAX_HISTORY_TURNS * 2:
        new_history = new_history[-(MAX_HISTORY_TURNS * 2):]
    await state.update_data(ai_history=new_history)

    if model_used and reply not in (RATE_LIMIT_DAILY, RATE_LIMIT_MINUTE, ""):
        try:
            await log_ai_usage(user_id, model_used, question=user_text, answer=reply)
        except Exception as e:
            logger.warning(f"[ai] failed to log usage: {e}")

    try:
        await thinking_msg.delete()
    except Exception:
        pass

    try:
        await message.answer(f"🤖 {reply}", parse_mode="Markdown",
                             reply_markup=ai_chat_kb(lang))
    except Exception:
        await message.answer(f"🤖 {reply}", reply_markup=ai_chat_kb(lang))


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@router.message(text_filter("btn_ai"))
async def ai_chat_start(message: aiogram_types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    lang = user["lang"] or "ru"

    if get_manager().is_daily_exhausted():
        await message.answer(t("ai_limit_daily", lang))
        return

    conn = await get_db()
    async with conn.execute(
        "SELECT date, completed, planned, rpe, day_type, extra_activity, notes FROM workouts "
        "WHERE user_id=? ORDER BY date DESC LIMIT 14",
        (user["id"],),
    ) as cur:
        workouts = await cur.fetchall()

    system_prompt = _SYSTEM_TEMPLATE.format(
        user_data_block=_user_data_block(user, workouts)
    )

    await state.set_state(AIChat.chatting)
    await state.update_data(ai_history=[], ai_system=system_prompt, ai_lang=lang)

    if lang == "ru":
        intro = (
            "🤖 *Турникмен AI*\n\n"
            "Спрашивай всё что хочешь — про тренировки, план, ранги, технику или как работает бот.\n\n"
            "У меня есть вся информация о твоих тренировках, поэтому я базируюсь на ней и даю тебе "
            "персонализированные советы. Нажми *💡 Получить совет* — и я сразу разберу твои данные."
        )
    else:
        intro = (
            "🤖 *Turnikmen AI*\n\n"
            "Ask me anything — about your training, plan, ranks, technique, or how the bot works.\n\n"
            "I have all your training data and base my answers on it, so every response is personalised to you. "
            "Tap *💡 Get Advice* and I'll break down your data right away."
        )
    await message.answer(intro, parse_mode="Markdown", reply_markup=ai_chat_kb(lang))


@router.message(AIChat.chatting, text_filter("btn_back"))
async def ai_chat_exit(message: aiogram_types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("ai_lang", "ru")
    await state.clear()
    await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))


@router.message(AIChat.chatting, text_filter("btn_ai_advice"))
async def ai_chat_advice(message: aiogram_types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("ai_lang", "ru")
    auto_prompt = (
        "Посмотри на мои последние тренировки и дай конкретный персонализированный совет: "
        "как я прогрессирую, всё ли идёт по плану, что стоит скорректировать и что делать завтра?"
    ) if lang == "ru" else (
        "Look at my recent workouts and give me a specific personalised recommendation: "
        "how am I progressing, is everything on track, what should I adjust, and what should I focus on tomorrow?"
    )

    system_prompt = data.get("ai_system", "")
    history = data.get("ai_history", [])

    user = await get_user(message.from_user.id)
    thinking = await message.answer(t("ai_thinking", lang))
    manager = get_manager()
    task = asyncio.create_task(manager.chat(system_prompt, history, auto_prompt))
    raw, model_used = await _wait_with_updates(task, thinking, lang)
    reply = _resolve_reply(raw, lang)
    user_id = user["id"] if user else 0
    await _send_reply(message, thinking, reply, lang, history, auto_prompt, state,
                      user_id=user_id, model_used=model_used)


@router.message(AIChat.chatting)
async def ai_chat_message(message: aiogram_types.Message, state: FSMContext):
    if not message.text:
        return
    data = await state.get_data()
    lang = data.get("ai_lang", "ru")
    system_prompt = data.get("ai_system", "")
    history = data.get("ai_history", [])

    user = await get_user(message.from_user.id)
    thinking = await message.answer(t("ai_thinking_chat", lang))
    manager = get_manager()
    task = asyncio.create_task(manager.chat(system_prompt, history, message.text))
    raw, model_used = await _wait_with_updates(task, thinking, lang)
    reply = _resolve_reply(raw, lang)
    user_id = user["id"] if user else 0
    await _send_reply(message, thinking, reply, lang, history, message.text, state,
                      user_id=user_id, model_used=model_used)
