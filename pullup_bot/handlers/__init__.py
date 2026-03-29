from aiogram import Dispatcher

from . import admin, ai, fallback, friends, help, history, settings, start, stats, training


def register_all(dp: Dispatcher):
    dp.include_router(help.router)
    dp.include_router(friends.router)   # state-specific back before generic
    dp.include_router(settings.router)  # state-specific back before generic
    dp.include_router(start.router)
    dp.include_router(training.router)
    dp.include_router(stats.router)
    dp.include_router(history.router)
    dp.include_router(ai.router)
    dp.include_router(admin.router)
    dp.include_router(fallback.router)  # must be last
