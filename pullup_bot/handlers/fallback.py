import time
from datetime import datetime

from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from ..config import logger
from ..db import get_user
from ..services import monitoring
from ..services.gemini import get_manager, RATE_LIMIT_DAILY, RATE_LIMIT_MINUTE
from .. import globals as g

router = Router()

# Cooldown: 1 fallback Gemini call per user per 60 seconds max
_fallback_cooldown: dict[int, float] = {}
_FALLBACK_COOLDOWN_SECS = 60

_FALLBACK_SYSTEM = (
    "You are Turnikmen Bot — a Telegram pull-up training bot assistant. "
    "The user sent a free-form message outside the bot's normal flow. "
    "Give a short, helpful response (1-3 sentences). "
    "If the message looks like a bug report or feature request, suggest they use the 🐛 button in the main menu. "
    "If it looks like a question about training or the bot, answer briefly. "
    "Match the user's language. Be friendly and concise."
)


@router.message()
async def unhandled_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    text = message.text or f"[{message.content_type}]"
    if current_state:
        logger.warning(
            f"[STATE GAP] user={message.from_user.id} "
            f"state={current_state!r} unexpected text={text!r}"
        )
    else:
        logger.warning(
            f"[UNHANDLED] user={message.from_user.id} "
            f"no-state text={text!r}"
        )
    monitoring.inc("unhandled")
    g.security_events.appendleft({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "uid": message.from_user.id if message.from_user else "?",
        "type": "state_gap" if current_state else "unhandled",
        "text": text[:50],
    })

    # Smart fallback: reply via Gemini only when user sends actual text with no active state
    if (not current_state
            and message.text
            and len(message.text) >= 3
            and not message.text.startswith("/")):
        uid = message.from_user.id if message.from_user else 0
        now = time.monotonic()
        last = _fallback_cooldown.get(uid, 0)
        if now - last < _FALLBACK_COOLDOWN_SECS:
            return  # cooldown active — stay silent
        manager = get_manager()
        if manager.is_daily_exhausted():
            return  # no quota left — stay silent
        _fallback_cooldown[uid] = now
        try:
            raw, _ = await manager.chat(_FALLBACK_SYSTEM, [], message.text)
            if raw and raw not in (RATE_LIMIT_DAILY, RATE_LIMIT_MINUTE):
                await message.answer(raw)
        except Exception as e:
            logger.warning(f"[fallback_gemini] {e}")


@router.callback_query()
async def unhandled_callback(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    logger.warning(
        f"[UNHANDLED CALLBACK] user={callback.from_user.id} "
        f"state={current_state!r} "
        f"data={callback.data!r}"
    )
    monitoring.inc("unhandled")
    await callback.answer()
