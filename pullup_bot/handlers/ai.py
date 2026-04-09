import asyncio

import google.generativeai as genai
from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from ..config import GEMINI_KEY, GEMINI_MODEL, LEVEL_NAMES, WAVE, logger
from ..db import get_db, get_user
from ..i18n import t, text_filter, day_name
from ..keyboards import back_only_kb, main_kb
from ..services.xp import display, level_info, planned_for_day
from ..states import AIChat

router = Router()

genai.configure(api_key=GEMINI_KEY)

MAX_HISTORY_TURNS = 10  # keep last 10 exchanges in memory

# ---------------------------------------------------------------------------
# System prompt — comprehensive bot knowledge + dynamic user data block
# ---------------------------------------------------------------------------

_SYSTEM_TEMPLATE = """You are Turnikmen AI — the built-in intelligent assistant for the Turnikmen / Pullup Bot, a Telegram-based pullup training application.

## BOT KNOWLEDGE BASE

### What Turnikmen does
Turnikmen helps users systematically increase their pullup count through smart progressive overload and wave periodization. Users log workouts daily and the bot auto-adjusts their training plan based on performance and effort ratings.

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
- RPE too low (+3% base): triggers when 3-session rolling avg RPE ≤4.5 AND all sessions were fully completed
- Extra activity reduction: if a user logs running/cardio/gym after training, tomorrow's planned load is reduced proportionally (capped per activity type)

### RPE — Rate of Perceived Exertion
After each workout the user rates effort from 1 to 10.
1–3 = very easy, 4–6 = moderate, 7–8 = hard, 9–10 = near maximum / total failure.
The bot uses a rolling 3-session average to adjust load smoothly.

### XP and CS:GO-style ranks
XP is earned two ways:
- +1 XP per pullup completed
- +50 XP per consecutive streak day (each day trained or rest acknowledged in a row)

There are 18 ranks in total:
Silver I (0 XP) → Silver II (500) → Silver III (1,000) → Silver IV (1,800) → Silver Elite (2,800) → Silver Elite Master (4,000) → Gold Nova I (5,500) → Gold Nova II (7,500) → Gold Nova III (10,000) → Gold Nova Master (13,500) → Master Guardian I (18,000) → Master Guardian II (23,000) → Master Guardian Elite (29,000) → Distinguished Master Guardian / DMG (36,000) → Legendary Eagle (44,000) → Legendary Eagle Master / LEM (53,000) → Supreme Master First Class / SMFC (63,000) → The Global Elite (70,000 XP)

Road to Global Elite: approximately 1.5 years and ~40,000 pullups for a user averaging 70 pullups/day with an active streak.

### Streak & Freeze tokens
- Streak: counts consecutive days where the user trained OR acknowledged a scheduled rest day
- If a day is missed without a freeze token, the streak resets to 0
- Freeze tokens: spending one protects the streak for one missed day
- How to earn: every 7-day streak milestone (auto), on each rank-up (after workout), when setting a new single-day personal record
- Maximum 5 tokens can be held at once

### Кочка недели / Beast of the Week
Every Monday at 08:00, the user with the most pullups in the past 7 days is automatically crowned champion. All users receive an announcement with the winner's name and a top-3 leaderboard. The champion displays a 👑 badge in their stats and on the leaderboard until the following Monday.

### Friends vs Leaderboard (they are different)
- Friends button (👥 Друзья): shows ALL participants' current day status — what today's target is, how many they've done so far, and their streak count. It's a live daily view of who's active today.
- Leaderboard button (🏆 Рейтинг): shows weekly ranking sorted by total pullups done this week. It's the competitive weekly scoreboard.

### Editing past days
Users can edit any past workout via Edit Day in Settings: change reps, RPE, extra activity, and notes. Entering 0 reps deletes the record and reverses the XP.

### Registration
New users provide: secret code (from the organizer), name, weight in kg, and their daily pullup base. Everyone starts at Silver I, program day 0.

### Bot is in beta
Some features may have minor bugs. Users can report bugs or suggest improvements using the 🐛 button.

---

## THIS USER'S CURRENT DATA

{user_data_block}

---

## INSTRUCTIONS
- Respond in the user's preferred language shown above, unless they write to you in a different language — then match theirs
- Be conversational, direct, and motivating
- When giving training advice, reference the user's actual numbers (their base, streak, recent RPE, rank)
- Keep responses concise (2–4 sentences) unless the user explicitly asks for a detailed plan or explanation
- If asked something outside your knowledge, say so honestly
- Never fabricate training data — only reference what is in the user data block
- You can answer questions about the bot's features, the user's progress, general pullup technique, and recovery advice
"""


def _user_data_block(user, workouts) -> str:
    lang = user["lang"] or "ru"
    lvl, lname, to_nxt, _ = level_info(user["xp"] or 0)
    next_user = dict(user)
    next_user["program_day"] = ((user["program_day"] or 0) + 1) % 7
    next_plan, next_type = planned_for_day(next_user)
    today_plan, today_type = planned_for_day(user)
    lang_label = "Russian" if lang == "ru" else "English"

    history_lines = []
    for r in workouts:
        rpe = str(r["rpe"]) if r["rpe"] else "—"
        history_lines.append(
            f"  {r['date'][5:]}  {(r['day_type'] or '?'):10s}  {r['completed']}/{r['planned']}  RPE={rpe}"
        )

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


async def _gemini_chat(system_prompt: str, history: list, user_msg: str) -> str:
    def _call():
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system_prompt,
        )
        gemini_history = [
            {"role": h["role"], "parts": [h["content"]]}
            for h in history
        ]
        session = model.start_chat(history=gemini_history)
        return session.send_message(user_msg).text

    try:
        return await asyncio.to_thread(_call)
    except Exception as e:
        logger.error(f"[Gemini] {e}")
        return ""


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@router.message(text_filter("btn_ai"))
async def ai_chat_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    lang = user["lang"] or "ru"

    conn = await get_db()
    async with conn.execute(
        "SELECT date, completed, planned, rpe, day_type FROM workouts "
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
            "Спрашивай всё что хочешь — про свои тренировки, план, ранги, технику или как работает бот. "
            "Я знаю всю твою историю.\n\n"
            "_◀️ Назад — выйти из чата_"
        )
    else:
        intro = (
            "🤖 *Turnikmen AI*\n\n"
            "Ask me anything — about your training, plan, ranks, technique, or how the bot works. "
            "I have your full history.\n\n"
            "_◀️ Back — exit chat_"
        )
    await message.answer(intro, parse_mode="Markdown", reply_markup=back_only_kb(lang))


@router.message(AIChat.chatting, text_filter("btn_back"))
async def ai_chat_exit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("ai_lang", "ru")
    await state.clear()
    await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))


@router.message(AIChat.chatting)
async def ai_chat_message(message: types.Message, state: FSMContext):
    if not message.text:
        return
    data = await state.get_data()
    lang = data.get("ai_lang", "ru")
    system_prompt = data.get("ai_system", "")
    history = data.get("ai_history", [])

    thinking = await message.answer(t("ai_thinking", lang))

    reply = await _gemini_chat(system_prompt, history, message.text)
    if not reply:
        reply = t("ai_unavailable", lang)

    # Update and trim history
    history = history + [
        {"role": "user", "content": message.text},
        {"role": "model", "content": reply},
    ]
    if len(history) > MAX_HISTORY_TURNS * 2:
        history = history[-(MAX_HISTORY_TURNS * 2):]
    await state.update_data(ai_history=history)

    try:
        await thinking.delete()
    except Exception:
        pass

    try:
        await message.answer(f"🤖 {reply}", parse_mode="Markdown",
                             reply_markup=back_only_kb(lang))
    except Exception:
        await message.answer(f"🤖 {reply}", reply_markup=back_only_kb(lang))
