import aiohttp

from aiogram import Router, types

from ..config import GROQ_KEY, LEVEL_NAMES, logger
from ..db import get_db, get_user
from ..i18n import t, text_filter, day_name
from ..keyboards import main_kb
from ..services.xp import display, planned_for_day

router = Router()


async def groq_advice(prompt: str, system: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}",
                         "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 300, "temperature": 0.7
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                choices = data.get("choices")
                if not choices:
                    return ""
                return choices[0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"[Groq] {e}")
        return ""


@router.message(text_filter("btn_ai"))
async def ai_advice(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(t("register_first", "ru"))
        return
    lang = user["lang"] or "ru"
    await message.answer(t("ai_thinking", lang), reply_markup=main_kb(lang))
    conn = await get_db()
    async with conn.execute(
        "SELECT date, completed, planned, rpe, day_type FROM workouts "
        "WHERE user_id=? ORDER BY date DESC LIMIT 5", (user["id"],)
    ) as cur:
        last5 = await cur.fetchall()
    if not last5:
        await message.answer(t("ai_no_data", lang), reply_markup=main_kb(lang))
        return
    summary = "\n".join([
        f"{r['date'][5:]}: {r['completed']}/{r['planned']} RPE={r['rpe']} ({r['day_type']})"
        for r in last5
    ])
    # Compute tomorrow's day type
    next_user = dict(user)
    next_user["program_day"] = (user["program_day"] or 0) + 1
    _, next_day_type = planned_for_day(next_user)
    next_day_display = day_name(next_day_type, lang)
    system_prompt = t("ai_system_prompt", lang)
    user_prompt = t("ai_user_prompt", lang,
                    name=display(user), weight=user["weight_kg"],
                    streak=user["streak"], level=LEVEL_NAMES[user["level"]],
                    base=user["base_pullups"],
                    program_day=user["program_day"] or 0,
                    next_day=next_day_display,
                    summary=summary)
    advice = await groq_advice(user_prompt, system_prompt)
    if not advice:
        advice = t("ai_unavailable", lang)
    try:
        await message.answer(f"🤖 *{'ИИ-тренер' if lang == 'ru' else 'AI Coach'}:*\n\n{advice}",
                             parse_mode="Markdown", reply_markup=main_kb(lang))
    except Exception:
        await message.answer(f"🤖\n\n{advice}", reply_markup=main_kb(lang))
