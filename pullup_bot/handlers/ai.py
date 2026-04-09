from google import genai
from google.genai import types
from aiogram import Router, types as aiogram_types
from aiogram.fsm.context import FSMContext

from ..config import GEMINI_KEY, GEMINI_MODEL, logger
from ..db import get_db, get_user
from ..i18n import t, text_filter
from ..keyboards import back_only_kb, main_kb
from ..services.xp import display, level_info, planned_for_day
from ..states import AIChat

router = Router()

_client = genai.Client(api_key=GEMINI_KEY)

MAX_HISTORY_TURNS = 10  # keep last N user+model exchanges

# ---------------------------------------------------------------------------
# System prompt — complete bot knowledge base + dynamic user data
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
- RPE too low (+3% base): triggers when 3-session rolling avg RPE ≤4.5 AND all sessions were fully completed
- Extra activity reduction: logging running/cardio/gym after training reduces tomorrow's load proportionally to prevent overtraining

### RPE — Rate of Perceived Exertion
After each workout the user rates effort from 1 to 10.
1–3 = very easy, 4–6 = moderate, 7–8 = hard, 9–10 = near maximum / total failure.
The bot uses a rolling 3-session average to adjust load smoothly.

### XP and CS:GO-style ranks
XP earned: +1 XP per pullup completed, +50 XP per consecutive streak day.
18 ranks in total:
Silver I (0 XP) → Silver II (500) → Silver III (1,000) → Silver IV (1,800) → Silver Elite (2,800) → Silver Elite Master (4,000) → Gold Nova I (5,500) → Gold Nova II (7,500) → Gold Nova III (10,000) → Gold Nova Master (13,500) → Master Guardian I (18,000) → Master Guardian II (23,000) → Master Guardian Elite (29,000) → Distinguished Master Guardian / DMG (36,000) → Legendary Eagle (44,000) → Legendary Eagle Master / LEM (53,000) → Supreme Master First Class / SMFC (63,000) → The Global Elite (70,000 XP)
Road to Global Elite: approximately 1.5 years and ~40,000 pullups at 70/day with an active streak.

### Streak & Freeze tokens
- Streak: consecutive days where the user trained OR acknowledged a scheduled rest day
- Missed day without a token: streak resets to 0
- Freeze tokens: spending one protects the streak for one missed day
- How to earn: every 7-day streak milestone (automatic), on each rank-up (after workout), when setting a new personal record
- Maximum 5 tokens at once

### Кочка недели / Beast of the Week
Every Monday at 08:00, the user with the most pullups in the past 7 days is crowned champion. All users receive an announcement with top-3. The champion gets a 👑 badge in stats and on the leaderboard until next Monday.

### Friends vs Leaderboard (different features)
- Friends button (👥): shows all participants' current day status — today's target, how many done, streak count. Live daily view.
- Leaderboard button (🏆): weekly ranking by total pullups. Competitive weekly scoreboard.

### Editing past days
Via Edit Day in Settings: change reps, RPE, extra activity, notes for any past date. Entering 0 reps deletes the record and reverses XP.

### Registration
Users provide: secret code (from organizer), name, weight in kg, daily pullup base. Starts at Silver I, program day 0.

### AI (you)
Powered by Google Gemini 3 Flash. Full multi-turn chat with access to the user's training history and live data below.

---

## THIS USER'S CURRENT DATA

{user_data_block}

---

## INSTRUCTIONS
- Respond in the user's preferred language shown above, unless they write in a different language — then match theirs
- Be conversational, direct, and motivating
- When giving training advice, use the user's actual numbers (base, streak, recent RPE, rank)
- Keep responses concise (2–4 sentences) unless the user asks for a detailed plan or explanation
- If asked something outside your knowledge, say so honestly
- Never fabricate training data — only reference what is in the user data block above
"""


def _user_data_block(user, workouts) -> str:
    lang = user["lang"] or "ru"
    lvl, lname, to_nxt, _ = level_info(user["xp"] or 0)
    next_user = {**dict(user), "program_day": ((user["program_day"] or 0) + 1) % 7}
    next_plan, next_type = planned_for_day(next_user)
    today_plan, today_type = planned_for_day(user)
    lang_label = "Russian" if lang == "ru" else "English"

    history_lines = [
        f"  {r['date'][5:]}  {(r['day_type'] or '?'):10s}  {r['completed']}/{r['planned']}  RPE={r['rpe'] or '—'}"
        for r in workouts
    ]

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
    """Convert stored [{role, content}] list to google.genai Content objects."""
    return [
        types.Content(role=h["role"], parts=[types.Part(text=h["content"])])
        for h in history
    ]


_RATE_LIMIT_DAILY = "__LIMIT_DAILY__"
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
async def ai_chat_exit(message: aiogram_types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("ai_lang", "ru")
    await state.clear()
    await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))


@router.message(AIChat.chatting)
async def ai_chat_message(message: aiogram_types.Message, state: FSMContext):
    if not message.text:
        return
    data = await state.get_data()
    lang = data.get("ai_lang", "ru")
    system_prompt = data.get("ai_system", "")
    history = data.get("ai_history", [])

    thinking = await message.answer(t("ai_thinking", lang))

    reply = await _chat(system_prompt, history, message.text)
    if reply == _RATE_LIMIT_DAILY:
        reply = t("ai_limit_daily", lang)
    elif reply == _RATE_LIMIT_MINUTE:
        reply = t("ai_limit_minute", lang)
    elif not reply:
        reply = t("ai_unavailable", lang)

    # Append and trim history
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
