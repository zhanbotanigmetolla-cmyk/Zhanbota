import time

from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from ..config import logger
from ..db import get_user
from ..i18n import t
from ..keyboards import landing_kb, main_kb
from ..services import monitoring
from ..timeutils import now
from .. import globals as g

router = Router()

# Avoid repeating the same navigation hint during a burst of messages.
_fallback_cooldown: dict[int, float] = {}
_FALLBACK_COOLDOWN_SECS = 60


@router.message()
async def unhandled_message(message: types.Message, state: FSMContext):
    """Log unhandled messages and offer local navigation without sending text to AI."""
    current_state = await state.get_state()
    text = message.text or f"[{message.content_type}]"
    uid = message.from_user.id if message.from_user else None
    if current_state:
        logger.warning(
            f"[STATE GAP] user={uid} "
            f"state={current_state!r} unexpected text={text!r}"
        )
    else:
        logger.warning(
            f"[UNHANDLED] user={uid} "
            f"no-state text={text!r}"
        )
    monitoring.inc("unhandled")
    g.security_events.appendleft({
        "ts": now().isoformat(timespec="seconds"),
        "uid": uid if uid is not None else "?",
        "type": "state_gap" if current_state else "unhandled",
        "text": text[:50],
    })

    if current_state or not message.text or uid is None:
        return

    tick = time.monotonic()
    last = _fallback_cooldown.get(uid)
    if last is not None and tick - last < _FALLBACK_COOLDOWN_SECS:
        return
    if len(_fallback_cooldown) > 200:
        for key in [key for key, value in _fallback_cooldown.items()
                    if tick - value >= _FALLBACK_COOLDOWN_SECS]:
            del _fallback_cooldown[key]
    _fallback_cooldown[uid] = tick

    user = await get_user(uid)
    language_code = (message.from_user.language_code or "ru").lower()
    lang = (user["lang"] or "ru") if user else ("ru" if language_code.startswith("ru") else "en")
    if not user:
        await message.answer(t("register_first", lang), reply_markup=landing_kb(lang))
    elif user["is_logged_out"]:
        reply = (f"Чтобы продолжить, нажми «{t('btn_login', lang)}»." if lang == "ru" else
                 f"To continue, tap {t('btn_login', lang)}.")
        await message.answer(reply, reply_markup=landing_kb(lang))
    else:
        reply = (f"Выбери действие в меню. Для вопросов открой «{t('btn_ai', lang)}»." if lang == "ru" else
                 f"Choose an action from the menu. For questions, open {t('btn_ai', lang)}.")
        await message.answer(reply, reply_markup=main_kb(lang))


@router.callback_query()
async def unhandled_callback(callback: types.CallbackQuery, state: FSMContext):
    """Catch-all for callback queries that no other handler claimed; logs and acks the event."""
    current_state = await state.get_state()
    logger.warning(
        f"[UNHANDLED CALLBACK] user={callback.from_user.id} "
        f"state={current_state!r} "
        f"data={callback.data!r}"
    )
    monitoring.inc("unhandled")
    await callback.answer()
