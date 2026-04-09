import asyncio

from google import genai
from google.genai import types
from aiogram import Router, types as aiogram_types
from aiogram.fsm.context import FSMContext

from ..config import GEMINI_KEY, GEMINI_MODEL, logger
from ..db import get_db, get_user
from ..i18n import t, text_filter
from ..keyboards import ai_chat_kb, back_only_kb, main_kb
from ..services.xp import display, level_info, planned_for_day
from ..states import AIChat

router = Router()

_client = genai.Client(api_key=GEMINI_KEY)

MAX_HISTORY_TURNS = 10

# ---------------------------------------------------------------------------
# Progressive loading: update the "thinking" message while waiting
# ---------------------------------------------------------------------------
# (seconds after which to update, i18n key for the new text)
_PROGRESS_STEPS = [
    (8,  "ai_thinking_long"),
    (6,  "ai_thinking_longer"),
    (6,  "ai_thinking_almost"),
]


async def _wait_with_updates(task: asyncio.Task, thinking_msg, lang: str) -> str:
    """Await *task*, editing *thinking_msg* at each timeout milestone."""
    for delay, key in _PROGRESS_STEPS:
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=delay)
        except asyncio.TimeoutError:
            try:
                await thinking_msg.edit_text(t(key, lang))
            except Exception:
                pass
    return await task  # final wait — no more updates


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
    lang = user["lang"] or "ru"
    lvl, lname, to_nxt, _ = level_info(user["xp"] or 0)
    next_user = {**dict(user), "program_day": ((user["program_day"] or 0) + 1) % 7}
    next_plan, next_type = planned_for_day(next_user)
    today_plan, today_type = planned_for_day(user)
    lang_label = "Russian" if lang == "ru" else "English"

    history_lines = []
    for r in workouts:
        line = f"  {r['date'][5:]}  {(r['day_type'] or '?'):10s}  {r['completed']}/{r['planned']}  RPE={r['rpe'] or '—'}"
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
        f"Today: {today_type} — {today_plan} pullups planned\n"
        f"Tomorrow: {next_type} — {next_plan} pullups planned\n\n"
        f"Last {len(workouts)} workouts (newest first):\n"
        + ("\n".join(history_lines) if history_lines else "  No workouts yet.") + "\n\n"
        f"Preferred language: {lang_label}"
    )


def _to_gemini_history(history: list) -> list:
    return [
        types.Content(role=h["role"], parts=[types.Part(text=h["content"])])
        for h in history
    ]


_RATE_LIMIT_DAILY  = "__LIMIT_DAILY__"
_RATE_LIMIT_MINUTE = "__LIMIT_MINUTE__"


async def _chat(system_prompt: str, history: list, user_msg: str) -> str:
    try:
        chat_session = _client.aio.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
            history=_to_gemini_history(history),
        )
        response = await chat_session.send_message(user_msg)
        return response.text or ""
    except Exception as e:
        err = str(e).lower()
        if "429" in err or "quota" in err or "resource_exhausted" in err or "rate" in err:
            if "per_minute" in err or "per minute" in err or "minute" in err:
                return _RATE_LIMIT_MINUTE
            return _RATE_LIMIT_DAILY
        logger.error(f"[Gemini] {e}")
        return ""


def _resolve_reply(raw: str, lang: str) -> str:
    if raw == _RATE_LIMIT_DAILY:
        return t("ai_limit_daily", lang)
    if raw == _RATE_LIMIT_MINUTE:
        return t("ai_limit_minute", lang)
    if not raw:
        return t("ai_unavailable", lang)
    return raw


async def _send_reply(message, thinking_msg, reply: str, lang: str, history: list,
                      user_text: str, state: FSMContext):
    """Update history, delete thinking indicator, send the AI reply."""
    new_history = history + [
        {"role": "user",  "content": user_text},
        {"role": "model", "content": reply},
    ]
    if len(new_history) > MAX_HISTORY_TURNS * 2:
        new_history = new_history[-(MAX_HISTORY_TURNS * 2):]
    await state.update_data(ai_history=new_history)

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

    thinking = await message.answer(t("ai_thinking", lang))
    task = asyncio.create_task(_chat(system_prompt, history, auto_prompt))
    raw = await _wait_with_updates(task, thinking, lang)
    reply = _resolve_reply(raw, lang)
    await _send_reply(message, thinking, reply, lang, history, auto_prompt, state)


@router.message(AIChat.chatting)
async def ai_chat_message(message: aiogram_types.Message, state: FSMContext):
    if not message.text:
        return
    data = await state.get_data()
    lang = data.get("ai_lang", "ru")
    system_prompt = data.get("ai_system", "")
    history = data.get("ai_history", [])

    thinking = await message.answer(t("ai_thinking_chat", lang))
    task = asyncio.create_task(_chat(system_prompt, history, message.text))
    raw = await _wait_with_updates(task, thinking, lang)
    reply = _resolve_reply(raw, lang)
    await _send_reply(message, thinking, reply, lang, history, message.text, state)
