"""Workout commits survive retries, restarts and concurrent sessions."""

import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

import pullup_bot.db as db
import pullup_bot.handlers.training as training
from pullup_bot.states import Training
from pullup_bot.timeutils import today
from .conftest import insert_test_user


class FakeMessage:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.answers = []
        self.text = "5"
        self.from_user = SimpleNamespace(id=1)

    async def answer(self, text, **kwargs):
        if self.fail:
            raise RuntimeError("Telegram delivery failed")
        self.answers.append(text)
        return SimpleNamespace(message_id=len(self.answers))


@pytest.fixture(autouse=True)
def no_external_notifications(monkeypatch):
    monkeypatch.setattr(training, "_notify_friends", AsyncMock())


async def session_state(data):
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1))
    await state.set_state(Training.rpe)
    await state.set_data(data)
    return state


async def prepare_session(connection):
    await insert_test_user(connection, tg_id=1, personal_record=100)
    user = await db.get_user(1)
    d = today().isoformat()
    await db.upsert_workout(user["id"], d, "pullups", planned=100, day_type="Средний")
    return {"session_id": "session-1", "date": d, "exercise": "pullups",
            "sets": [10], "done_before": 0, "planned": 100, "rpe": 6,
            "weight": 0, "lang": "en"}


async def assert_one_completion(data):
    user = await db.get_user(1)
    row = await db.get_workout(user["id"], data["date"], "pullups")
    assert user["xp"] == 10
    assert user["streak"] == 1
    assert user["program_day"] == 1
    assert row["completed"] == 10
    assert json.loads(row["sets_json"]) == [10]
    connection = await db.get_db()
    async with connection.execute("SELECT COUNT(*) FROM workout_completions") as cursor:
        assert (await cursor.fetchone())[0] == 1


@pytest.mark.asyncio
async def test_delivery_failure_cannot_award_the_session_again(test_db):
    data = await prepare_session(test_db)
    state = await session_state(data)
    with pytest.raises(RuntimeError, match="Telegram delivery"):
        await training._save_workout(FakeMessage(fail=True), state, 1)
    assert await state.get_state() is None
    await assert_one_completion(data)

    # A stale delivery or recovered FSM gets the receipt, not another award.
    await training._save_workout(FakeMessage(), await session_state(data), 1)
    await assert_one_completion(data)
    training._notify_friends.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_crash_before_clearing_fsm_replays_durable_receipt(test_db, monkeypatch, legacy):
    data = await prepare_session(test_db)
    if legacy:
        data.pop("session_id")
    state = await session_state(data)
    monkeypatch.setattr(state, "clear", AsyncMock(side_effect=RuntimeError("FSM unavailable")))
    with pytest.raises(RuntimeError, match="FSM unavailable"):
        await training._save_workout(FakeMessage(), state, 1)
    assert await state.get_state() == Training.rpe.state
    await assert_one_completion(data)

    # Changing the rating on retry must still identify the same legacy session.
    data["rpe"] = 8
    await training._save_workout(FakeMessage(), await session_state(data), 1)
    await assert_one_completion(data)


@pytest.mark.asyncio
async def test_cancel_cleanup_cannot_delete_an_already_committed_workout(test_db, monkeypatch):
    data = await prepare_session(test_db)
    data["orig_set_record"] = 0
    await test_db.execute("UPDATE users SET set_record=10 WHERE tg_id=1")
    await test_db.commit()
    state = await session_state(data)
    monkeypatch.setattr(state, "clear", AsyncMock(side_effect=RuntimeError("FSM unavailable")))
    with pytest.raises(RuntimeError, match="FSM unavailable"):
        await training._save_workout(FakeMessage(), state, 1)
    await training._cleanup_cancelled_workout(1, data)
    await assert_one_completion(data)
    assert (await db.get_user(1))["set_record"] == 10


@pytest.mark.asyncio
async def test_back_recovers_saved_session_and_new_sets_get_a_new_id(test_db, monkeypatch):
    data = await prepare_session(test_db)
    state = await session_state(data)
    real_clear = state.clear
    monkeypatch.setattr(state, "clear", AsyncMock(side_effect=RuntimeError("FSM unavailable")))
    with pytest.raises(RuntimeError, match="FSM unavailable"):
        await training._save_workout(FakeMessage(), state, 1)
    monkeypatch.setattr(state, "clear", real_clear)
    message = FakeMessage()
    await training.rpe_back(message, state)
    assert await state.get_state() is None
    assert "already saved" in message.answers[-1]
    await assert_one_completion(data)

    user = await db.get_user(1)
    await training._begin_training(message, state, user, "en", data["date"], "pullups", "Средний")
    new_data = await state.get_data()
    assert new_data["session_id"] != data["session_id"]
    await state.update_data(sets=[5], rpe=6)
    await state.set_state(Training.rpe)
    await training._save_workout(message, state, 1)
    user = await db.get_user(1)
    row = await db.get_workout(user["id"], data["date"], "pullups")
    assert (user["xp"], row["completed"]) == (15, 15)
    assert json.loads(row["sets_json"]) == [10, 5]


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [training.cancel_confirm, training.cancel_training_btn,
                                     training.undo_set, training.custom_set_input,
                                     training.finish_training_btn, training.cancel_back_msg])
async def test_stale_completed_fsm_cannot_cancel_or_edit_sets(test_db, handler):
    data = await prepare_session(test_db)
    await training._save_workout(FakeMessage(), await session_state(data), 1)
    stale_state = await session_state(data)
    await stale_state.set_state(Training.active)
    message = FakeMessage()
    await handler(message, stale_state)
    assert await stale_state.get_state() is None
    assert "already saved" in message.answers[-1]
    await assert_one_completion(data)


@pytest.mark.asyncio
async def test_internal_failure_rolls_back_all_awards_and_can_be_retried(test_db, monkeypatch):
    data = await prepare_session(test_db)
    state = await session_state(data)
    adjustment = training._apply_rpe_adjustment
    monkeypatch.setattr(training, "_apply_rpe_adjustment",
                        AsyncMock(side_effect=RuntimeError("adjustment failed")))
    with pytest.raises(RuntimeError, match="adjustment failed"):
        await training._save_workout(FakeMessage(), state, 1)
    user = await db.get_user(1)
    row = await db.get_workout(user["id"], data["date"], "pullups")
    assert (user["xp"], user["streak"], user["program_day"], user["freeze_tokens"]) == (0, 0, 0, 3)
    assert row["completed"] == 0
    assert json.loads(row["sets_json"]) == []
    async with test_db.execute("SELECT COUNT(*) FROM workout_completions") as cursor:
        assert (await cursor.fetchone())[0] == 0

    monkeypatch.setattr(training, "_apply_rpe_adjustment", adjustment)
    await training._save_workout(FakeMessage(), state, 1)
    await assert_one_completion(data)


@pytest_asyncio.fixture
async def file_db(tmp_path, monkeypatch):
    """An isolated temporary DB exercises separate SQLite connections."""
    previous = db._conn
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "workout-test.sqlite"))
    db._conn = None
    try:
        await db.init_db()
        yield await db.get_db()
    finally:
        await db.close_db()
        db._conn = previous


@pytest.mark.asyncio
async def test_receipt_survives_closing_and_reopening_the_database(file_db, monkeypatch):
    data = await prepare_session(file_db)
    state = await session_state(data)
    monkeypatch.setattr(state, "clear", AsyncMock(side_effect=RuntimeError("process stopped")))
    with pytest.raises(RuntimeError, match="process stopped"):
        await training._save_workout(FakeMessage(), state, 1)
    await db.close_db()
    await training._save_workout(FakeMessage(), await session_state(data), 1)
    await assert_one_completion(data)


@pytest.mark.asyncio
async def test_concurrent_duplicate_sessions_award_once(file_db):
    data = await prepare_session(file_db)
    states = [await session_state(data) for _ in range(2)]
    await asyncio.gather(*(training._save_workout(FakeMessage(), state, 1) for state in states))
    await assert_one_completion(data)
    training._notify_friends.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_distinct_sessions_append_instead_of_overwriting(file_db):
    first = await prepare_session(file_db)
    second = dict(first, session_id="session-2", sets=[20])
    states = [await session_state(data) for data in (first, second)]
    await asyncio.gather(*(training._save_workout(FakeMessage(), state, 1) for state in states))
    user = await db.get_user(1)
    row = await db.get_workout(user["id"], first["date"], "pullups")
    assert (user["xp"], user["streak"], user["program_day"]) == (30, 1, 1)
    assert row["completed"] == 30
    assert sorted(json.loads(row["sets_json"])) == [10, 20]


@pytest.mark.asyncio
async def test_other_task_commit_cannot_commit_half_a_workout(file_db, monkeypatch):
    data = await prepare_session(file_db)
    adjustment_started = asyncio.Event()
    finish_adjustment = asyncio.Event()

    async def fail_after_other_commit(*args):
        adjustment_started.set()
        await finish_adjustment.wait()
        raise RuntimeError("late failure")

    monkeypatch.setattr(training, "_apply_rpe_adjustment", fail_after_other_commit)
    task = asyncio.create_task(training._save_workout(FakeMessage(), await session_state(data), 1))
    try:
        await asyncio.wait_for(adjustment_started.wait(), timeout=5)
        # This is a different task and must see the shared connection, not the
        # completion's private transaction or its uncommitted XP.
        assert await db.get_db() is file_db
        assert (await db.get_user(1))["xp"] == 0
        await file_db.commit()
    finally:
        finish_adjustment.set()
    with pytest.raises(RuntimeError, match="late failure"):
        await task
    assert (await db.get_user(1))["xp"] == 0


@pytest.mark.asyncio
async def test_reopen_and_cancel_keeps_the_saved_weight(test_db):
    await insert_test_user(test_db, tg_id=1, base_pullups_weighted=30,
                           weight_pullups_weighted=30)
    user = await db.get_user(1)
    d = today().isoformat()
    await db.upsert_workout(user["id"], d, "pullups_weighted", planned=30,
                            completed=10, sets_json="[10]", weight_kg=10, rpe=6)
    state = await session_state({"date": d, "pick_day_type": "Средний"})
    message = FakeMessage()
    await training._ask_session_weight(message, state, user, "en", "pullups_weighted")
    assert await state.get_state() == Training.active.state
    data = await state.get_data()
    assert data["weight"] == 10
    assert "same weight" in message.answers[0]
    await training._cleanup_cancelled_workout(1, data)
    row = await db.get_workout(user["id"], d, "pullups_weighted")
    assert (row["completed"], row["weight_kg"]) == (10, 10)
    assert json.loads(row["sets_json"]) == [10]


@pytest.mark.asyncio
async def test_stale_weight_selection_cannot_reprice_completed_sets(test_db):
    await insert_test_user(test_db, tg_id=1, base_pullups_weighted=30,
                           weight_pullups_weighted=30, xp=13)
    user = await db.get_user(1)
    d = today().isoformat()
    await db.upsert_workout(user["id"], d, "pullups_weighted", planned=30,
                            completed=10, sets_json="[10]", weight_kg=10, rpe=6)
    data = {"date": d, "exercise": "pullups_weighted", "planned": 30,
            "sets": [10], "done_before": 10, "weight": 30, "rpe": 6, "lang": "en"}
    await training._save_workout(FakeMessage(), await session_state(data), 1)
    user = await db.get_user(1)
    row = await db.get_workout(user["id"], d, "pullups_weighted")
    assert (row["completed"], row["weight_kg"]) == (20, 10)
    assert user["xp"] == 26


@pytest.mark.asyncio
async def test_finishing_a_previous_day_preserves_newer_activity(test_db):
    d = today().isoformat()
    old_day = (today() - timedelta(days=1)).isoformat()
    await insert_test_user(test_db, tg_id=1, last_workout=d, program_day=4,
                           streak=4, xp=100, personal_record=100)
    user = await db.get_user(1)
    await db.upsert_workout(user["id"], old_day, "pullups", planned=100)
    data = {"session_id": "old-session", "date": old_day, "exercise": "pullups",
            "sets": [10], "done_before": 0, "planned": 100, "rpe": 6, "lang": "en"}
    await training._save_workout(FakeMessage(), await session_state(data), 1)
    user = await db.get_user(1)
    assert (user["last_workout"], user["program_day"], user["streak"]) == (d, 4, 4)
    assert user["xp"] == 110
    assert (await db.get_workout(user["id"], old_day, "pullups"))["completed"] == 10
