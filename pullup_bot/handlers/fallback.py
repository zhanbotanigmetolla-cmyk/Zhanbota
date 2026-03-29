from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from ..config import logger
from ..services import monitoring

router = Router()


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
