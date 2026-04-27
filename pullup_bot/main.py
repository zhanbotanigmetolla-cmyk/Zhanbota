import asyncio
import time as _time
import traceback

from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import ADMIN_TG_ID, BOT_TOKEN, FSM_DB_PATH, WEBHOOK_SECRET, WEBHOOK_URL, is_admin_id, logger
from .db import close_db, get_user, init_db, is_muted, is_permanently_banned
from .handlers import register_all
from .storage import SqliteStorage
from .services.scheduler import (auto_acknowledge_rest_days, auto_cleanup_inactive,
                                  daily_health_summary, daily_reminder,
                                  db_integrity_check, watchdog_health_check,
                                  weekly_summary)
from .services import monitoring
from . import globals as g

g.BOT_START_TIME = _time.monotonic()

bot = Bot(token=BOT_TOKEN)
storage = SqliteStorage(db_path=FSM_DB_PATH)
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler()


@dp.errors()
async def errors_handler(event: types.ErrorEvent) -> bool:
    """Log all unhandled exceptions, alert the admin, and return True to suppress re-raise."""
    update = event.update
    exc = event.exception
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    context = ""
    if update:
        msg = update.message or (update.callback_query and update.callback_query.message)
        if update.message and update.message.text:
            context += f" text={update.message.text!r}"
        if update.callback_query:
            context += f" callback={update.callback_query.data!r}"
        uid = (update.message.from_user.id if update.message and update.message.from_user
               else update.callback_query.from_user.id if update.callback_query else "?")
        context = f"user={uid}{context}"

    logger.error(
        f"[ERROR] update={update.update_id if update else '?'} {context}\n"
        f"{type(exc).__name__}: {exc}\n{tb}"
    )
    monitoring.inc("errors")
    alert = (
        f"🚨 Ошибка бота\n{context}\n"
        f"{type(exc).__name__}: {exc}\n\n"
        f"{tb[-800:] if len(tb) > 800 else tb}"
    )
    try:
        await bot.send_message(ADMIN_TG_ID, alert)
    except Exception as e:
        logger.warning(f"[errors_handler] failed to notify admin: {e}")


async def _check_ban_and_mute(uid: int) -> str | None:
    """Return a reason string if user is blocked/muted, or None if OK."""
    if await is_permanently_banned(uid):
        return "banned"
    user = await get_user(uid)
    if user and user["is_banned"]:
        return "banned"
    if user and await is_muted(uid):
        return "muted"
    return None


@dp.message.middleware()
async def ban_check_middleware(handler, event: types.Message, data):
    """Drop messages from banned users; silently ignore messages from muted users."""
    uid = event.from_user.id if event.from_user else None
    if uid and not is_admin_id(uid):
        try:
            reason = await _check_ban_and_mute(uid)
            if reason == "banned":
                await event.answer("⛔ Ваш аккаунт заблокирован.")
                return
            if reason == "muted":
                return  # silently drop messages from muted users
        except Exception as e:
            logger.warning(f"[ban_check] user={uid}: {e}")
    return await handler(event, data)


@dp.callback_query.middleware()
async def ban_check_cb_middleware(handler, event: types.CallbackQuery, data):
    """Alert banned/muted users on callback queries and suppress the event."""
    uid = event.from_user.id if event.from_user else None
    if uid and not is_admin_id(uid):
        try:
            reason = await _check_ban_and_mute(uid)
            if reason == "banned":
                await event.answer("⛔ Заблокирован.", show_alert=True)
                return
            if reason == "muted":
                await event.answer("🔇 Вы временно заглушены.", show_alert=True)
                return
        except Exception as e:
            logger.warning(f"[ban_check_cb] user={uid}: {e}")
    return await handler(event, data)


@dp.message.middleware()
async def maintenance_middleware(handler, event: types.Message, data):
    """Block non-admin messages while maintenance mode is active."""
    if g.maintenance_mode:
        uid = event.from_user.id if event.from_user else None
        if uid and not is_admin_id(uid):
            await event.answer("🔧 Бот на техническом обслуживании. Скоро вернёмся!")
            return
    return await handler(event, data)


@dp.message.middleware()
async def logging_middleware(handler, event: types.Message, data):
    """Log every incoming message with user ID, FSM state, and text; increment action counter."""
    uid = event.from_user.id if event.from_user else "-"
    state_obj = data.get("state")
    current_state = await state_obj.get_state() if state_obj else None
    text = event.text or f"[{event.content_type}]"
    logger.info(f"[ACTION] user={uid} state={current_state!r} text={text!r}")
    monitoring.inc("actions")
    return await handler(event, data)


@dp.callback_query.middleware()
async def callback_logging_middleware(handler, event: types.CallbackQuery, data):
    """Log every callback query with user ID, FSM state, and callback data; increment action counter."""
    uid = event.from_user.id if event.from_user else "-"
    state_obj = data.get("state")
    current_state = await state_obj.get_state() if state_obj else None
    logger.info(f"[ACTION] user={uid} state={current_state!r} callback={event.data!r}")
    monitoring.inc("actions")
    return await handler(event, data)


register_all(dp)


async def main():
    """Initialize the DB, register scheduled jobs, and start polling or webhook mode."""
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)

    scheduler.add_job(daily_reminder, "interval", minutes=1, args=[bot])
    scheduler.add_job(daily_health_summary, "cron", hour=8, minute=0, args=[bot])
    scheduler.add_job(db_integrity_check, "cron", hour=3, minute=0, args=[bot])
    scheduler.add_job(weekly_summary, "cron", day_of_week="mon", hour=8, minute=0, args=[bot])
    scheduler.add_job(auto_cleanup_inactive, "cron", hour=4, minute=0, args=[bot])
    scheduler.add_job(watchdog_health_check, "interval", minutes=5, args=[bot])
    scheduler.add_job(auto_acknowledge_rest_days, "cron", hour=23, minute=55, args=[bot])
    scheduler.start()
    logger.info("✅ Turnikmen Bot запущен!")

    if WEBHOOK_URL:
        if not WEBHOOK_URL.startswith("https://"):
            raise RuntimeError("WEBHOOK_URL must use HTTPS")
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        await bot.set_webhook(WEBHOOK_URL, secret_token=WEBHOOK_SECRET)
        app = web.Application()
        handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET)
        handler.register(app, path="/webhook")
        setup_application(app, dp, bot=bot)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        await site.start()
        logger.info(f"Webhook mode on {WEBHOOK_URL}")
        await asyncio.Event().wait()
    else:
        await dp.start_polling(bot)

    await close_db()
    await storage.close()
