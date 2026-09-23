from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from pullup_bot import db
from pullup_bot.handlers import settings
from pullup_bot.states import EditDay, SetNotify
from .conftest import insert_test_user


def make_message(text):
    return SimpleNamespace(text=text, from_user=SimpleNamespace(id=12345), answer=AsyncMock())


def make_state():
    return FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=12345, user_id=12345))


@pytest.mark.asyncio
@pytest.mark.parametrize("entered,expected", [
    ("8:00", "08:00"), ("8:0", "08:00"), (" 23:5 ", "23:05"), ("0:0", "00:00"),
])
async def test_notify_time_is_saved_in_scheduler_format(test_db, entered, expected):
    await insert_test_user(test_db)
    state = make_state()
    await state.set_state(SetNotify.enter_time)

    await settings.save_notify_time(make_message(entered), state)

    assert (await db.get_user(12345))["notify_time"] == expected
    assert await state.get_state() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("entered", ["24:00", "08:60", "-1:00", "invalid"])
async def test_invalid_notify_time_preserves_previous_value(test_db, entered):
    await insert_test_user(test_db, notify_time="09:30")
    state = make_state()
    await state.set_state(SetNotify.enter_time)

    await settings.save_notify_time(make_message(entered), state)

    assert (await db.get_user(12345))["notify_time"] == "09:30"
    assert await state.get_state() == SetNotify.enter_time.state


@pytest.mark.asyncio
@pytest.mark.parametrize("entered", ["-100", "10001", "999999999999999999999999", "not a number"])
async def test_edit_rejects_invalid_rep_count_before_rpe(test_db, entered):
    await insert_test_user(test_db)
    state = make_state()
    await state.set_state(EditDay.pick_done)

    await settings.edit_pick_done(make_message(entered), state)

    assert await state.get_state() == EditDay.pick_done.state
    assert "edit_done" not in await state.get_data()


@pytest.mark.asyncio
@pytest.mark.parametrize("done", [-1, 10001, "20", 1.5, True])
async def test_invalid_persisted_edit_cannot_write_workout_or_xp(test_db, done):
    await insert_test_user(test_db, xp=100)
    state = make_state()
    await state.set_state(EditDay.pick_rpe)
    await state.update_data(edit_date="2026-01-01", edit_exercise="pullups", edit_done=done, edit_rpe=5)

    await settings._save_edit(make_message("5"), state)

    user = await db.get_user(12345)
    assert user["xp"] == 100
    assert await db.get_workout(user["id"], "2026-01-01", "pullups") is None
    assert await state.get_state() == EditDay.pick_done.state


@pytest.mark.asyncio
async def test_valid_edit_saves_reps_and_zero_still_deletes(test_db):
    await insert_test_user(test_db)
    state = make_state()
    await state.update_data(edit_date="2026-01-01", edit_exercise="pullups", edit_done=25, edit_rpe=5)

    await settings._save_edit(make_message("5"), state)

    user = await db.get_user(12345)
    assert (await db.get_workout(user["id"], "2026-01-01", "pullups"))["completed"] == 25
    assert user["xp"] == 25

    await state.update_data(edit_date="2026-01-01", edit_exercise="pullups")
    await settings.edit_pick_done(make_message("0"), state)

    assert await db.get_workout(user["id"], "2026-01-01", "pullups") is None
    assert (await db.get_user(12345))["xp"] == 0
    assert await state.get_state() is None
