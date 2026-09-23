"""Mini App authentication and real shared-DB operations, without Telegram calls."""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import urlencode
from uuid import uuid4

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation

import pullup_bot.miniapp as miniapp
import pullup_bot.db as db_mod
from pullup_bot import globals as g
from pullup_bot.db import ban_user, get_user, get_workout, upsert_workout
from pullup_bot.states import Reg, Training
from pullup_bot.timeutils import today
from .conftest import insert_test_user

TOKEN = "123456:miniapp-test-token"
UID = 12345


def init_data(uid=UID, *, age=0, token=TOKEN, user=None, extras=None):
    values = {"auth_date": str(int(time.time()) - age), "query_id": "AA-test-query",
              "user": json.dumps(user if user is not None else {
                  "id": uid, "first_name": "Тест + Test", "username": "tester", "language_code": "ru"},
                  ensure_ascii=False, separators=(",", ":"))}
    values.update(extras or {})
    secret = hmac.digest(b"WebAppData", token.encode(), "sha256")
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def auth(uid=UID, **kwargs):
    return {"Authorization": "tma " + init_data(uid, **kwargs)}


def workout_payload(**kwargs):
    result = {"session_id": str(uuid4()), "exercise": "pullups", "date": today().isoformat(),
              "sets": [10, 8, 7], "rpe": 6, "weight_kg": 0}
    result.update(kwargs)
    return result


@pytest_asyncio.fixture
async def api(test_db):
    storage = MemoryStorage()
    isolation = SimpleEventIsolation()
    app = web.Application()
    miniapp.setup_miniapp(app, storage=storage, events_isolation=isolation,
                         bot_id=123456, bot_token=TOKEN)
    async def health(request):
        return web.json_response({"ok": True})
    app.router.add_get("/healthz", health)
    client = TestClient(TestServer(app))
    await client.start_server()
    yield SimpleNamespace(client=client, storage=storage, isolation=isolation,
                          runtime=app[miniapp.RUNTIME], db=test_db)
    await client.close()
    await storage.close()
    await isolation.close()


def test_init_data_preserves_unicode_plus_and_checks_signature_field():
    raw = init_data(extras={"signature": "signed-by-Telegram-too"})
    user = miniapp.validate_init_data(raw, TOKEN)
    assert user["id"] == UID
    assert user["first_name"] == "Тест + Test"
    with pytest.raises(miniapp.ApiError, match="Telegram"):
        miniapp.validate_init_data(raw.replace("signed-by-Telegram-too", "tampered"), TOKEN)


@pytest.mark.parametrize("raw", ["", "user=nope", "bad%QQ", "x=" + "a" * 17000])
def test_malformed_init_data_is_rejected(raw):
    with pytest.raises(miniapp.ApiError) as error:
        miniapp.validate_init_data(raw, TOKEN)
    assert error.value.status == 401


@pytest.mark.parametrize("kind", ["tampered", "wrong_token", "duplicate", "expired", "future", "bool_id", "missing_user"])
def test_invalid_signed_sessions_are_rejected(kind):
    raw = init_data()
    if kind == "tampered":
        raw = raw.replace("12345", "54321")
    elif kind == "wrong_token":
        raw = init_data(token="another-bot-token")
    elif kind == "duplicate":
        raw += "&auth_date=1"
    elif kind == "expired":
        raw = init_data(age=86401)
    elif kind == "future":
        raw = init_data(age=-120)
    elif kind == "bool_id":
        raw = init_data(user={"id": True, "first_name": "Test"})
    else:
        raw = init_data(extras={"user": "null"})
    with pytest.raises(miniapp.ApiError) as error:
        miniapp.validate_init_data(raw, TOKEN)
    assert error.value.status == 401


@pytest.mark.asyncio
async def test_api_requires_header_auth_but_does_not_intercept_other_routes(api):
    response = await api.client.get("/api/miniapp/state", params={"initData": init_data()})
    assert response.status == 401
    assert (await response.json())["error"]["code"] == "invalid_auth"
    assert response.headers["Cache-Control"] == "no-store"
    assert "Access-Control-Allow-Origin" not in response.headers
    assert (await api.client.get("/healthz")).status == 200


@pytest.mark.asyncio
async def test_guest_state_is_empty_and_has_six_exercises(api):
    response = await api.client.get("/api/miniapp/state", headers=auth())
    assert response.status == 200
    state = (await response.json())["state"]
    assert not state["registered"]
    assert state["user"] is None
    assert state["history"] == state["leaderboard"] == state["friends"] == []
    assert len(state["exercises"]) == 6
    assert all(not ex["configured"] for ex in state["exercises"])
    assert await get_user(UID) is None


@pytest.mark.asyncio
async def test_onboarding_reuses_bot_registration_and_completes_registration_fsm(api):
    await api.storage.set_state(api.runtime.key(UID), Reg.max_pullups)
    body = {"name": "Атлет", "max_pullups": 10, "language": "en", "program_type": "beginner"}
    response = await api.client.post("/api/miniapp/onboarding", headers=auth(), json=body)
    assert response.status == 200
    state = (await response.json())["state"]
    user = await get_user(UID)
    assert user["base_pullups"] == 30
    assert (user["start_day"], user["program_day"], user["xp"]) == (0, 0, 0)
    assert user["joined"] == today().isoformat()
    assert user["first_name"] == "Атлет"
    assert state["language"] == "en"
    assert await api.storage.get_state(api.runtime.key(UID)) is None
    # Repeating onboarding must never reset the established profile or progress.
    await api.db.execute("UPDATE users SET xp=123,streak=3 WHERE tg_id=?", (UID,))
    await api.db.commit()
    assert (await api.client.post("/api/miniapp/onboarding", headers=auth(), json=body)).status == 200
    assert (await get_user(UID))["xp"] == 123


@pytest.mark.asyncio
async def test_client_cannot_choose_user_identity_or_xp(api):
    response = await api.client.post("/api/miniapp/onboarding", headers=auth(), json={
        "name": "Test", "max_pullups": 10, "tg_id": 999, "xp": 50000})
    assert response.status == 400
    assert await get_user(UID) is None
    assert await get_user(999) is None


@pytest.mark.asyncio
async def test_resuming_a_paused_account_preserves_streak_and_prevents_cleanup(api):
    from pullup_bot.services.scheduler import auto_cleanup_inactive

    class FakeBot:
        async def send_message(self, *args, **kwargs):
            pass

    await insert_test_user(api.db, joined=(today() - timedelta(days=100)).isoformat(),
                           last_workout=(today() - timedelta(days=40)).isoformat(),
                           streak=10, xp=100, is_logged_out=1)
    response = await api.client.post("/api/miniapp/onboarding", headers=auth(), json={})
    assert response.status == 200
    user = await get_user(UID)
    assert user["last_workout"] == (today() - timedelta(days=1)).isoformat()
    assert user["streak"] == 10
    await auto_cleanup_inactive(FakeBot())
    assert await get_user(UID) is not None
    assert (await api.client.post("/api/miniapp/workout", headers=auth(), json=workout_payload())).status == 200
    user = await get_user(UID)
    assert (user["streak"], user["xp"]) == (11, 175)


@pytest.mark.asyncio
@pytest.mark.parametrize("restriction", ["ban", "deleted_ban", "mute", "maintenance"])
async def test_account_restrictions_apply_to_reads_and_writes(api, monkeypatch, restriction):
    await insert_test_user(api.db)
    if restriction == "ban":
        await ban_user(UID)
    elif restriction == "deleted_ban":
        await api.db.execute("INSERT INTO banned_ids (tg_id) VALUES (?)", (UID,))
        await api.db.commit()
    elif restriction == "mute":
        await api.db.execute("UPDATE users SET muted_until=? WHERE tg_id=?",
                             ((datetime.now() + timedelta(hours=1)).isoformat(), UID))
        await api.db.commit()
    else:
        monkeypatch.setattr(g, "maintenance_mode", True)
    for method, path, kwargs in [("get", "state", {}), ("post", "workout", {"json": workout_payload()})]:
        response = await getattr(api.client, method)(f"/api/miniapp/{path}", headers=auth(), **kwargs)
        assert response.status == 403
    assert (await get_user(UID))["xp"] == 0


@pytest.mark.asyncio
async def test_settings_update_existing_account_and_preserve_program_position(api):
    await insert_test_user(api.db, program_day=4)
    response = await api.client.post("/api/miniapp/settings", headers=auth(), json={
        "name": "New name", "language": "en", "notify_time": "08:00", "notify_workouts": True,
        "program_type": "beginner", "exercises": {"pushups": {"max_reps": 20},
                                                   "pullups_weighted": {"max_reps": 10, "weight_kg": 12.5}}})
    assert response.status == 200
    user = await get_user(UID)
    assert (user["base_pushups"], user["base_pullups_weighted"], user["weight_pullups_weighted"]) == (60, 30, 12.5)
    assert (user["lang"], user["notify_time"], user["notify_workouts"], user["program_day"]) == ("en", "08:00", 1, 4)
    assert user["best_weight_pullups_weighted"] == 0  # choosing a load is not a completed record


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,body", [("settings", {"name": "New name"}), ("workout", None),
                                           ("onboarding", {})])
async def test_active_bot_workflow_prevents_conflicting_writes(api, endpoint, body):
    await insert_test_user(api.db)
    await api.storage.set_state(api.runtime.key(UID), Training.active)
    response = await api.client.post(f"/api/miniapp/{endpoint}", headers=auth(),
                                     json=workout_payload() if body is None else body)
    assert response.status == 409
    assert (await response.json())["error"]["code"] == "bot_session_active"
    assert await api.storage.get_state(api.runtime.key(UID)) == Training.active.state
    assert (await get_user(UID))["xp"] == 0


@pytest.mark.asyncio
async def test_shared_bot_lock_is_held_before_rechecking_fsm(api):
    await insert_test_user(api.db)
    key = api.runtime.key(UID)
    async with api.isolation.lock(key):
        pending = asyncio.create_task(api.client.post("/api/miniapp/workout", headers=auth(), json=workout_payload()))
        await asyncio.sleep(0.02)
        assert not pending.done()
        await api.storage.set_state(key, Training.active)
    response = await pending
    assert response.status == 409
    assert (await get_user(UID))["xp"] == 0


@pytest.mark.asyncio
async def test_workout_uses_bot_xp_records_and_durable_idempotency(api):
    await insert_test_user(api.db)
    body = workout_payload()
    first = await api.client.post("/api/miniapp/workout", headers=auth(), json=body)
    assert first.status == 200
    result = await first.json()
    assert result["receipt"]["xp_gained"] == 25
    assert result["receipt"]["duplicate"] is False
    user = await get_user(UID)
    row = await get_workout(user["id"], today().isoformat(), "pullups")
    assert (user["xp"], user["streak"], user["program_day"], user["set_record"], user["personal_record"]) == (25, 1, 1, 10, 25)
    assert json.loads(row["sets_json"]) == [10, 8, 7]
    second = await api.client.post("/api/miniapp/workout", headers=auth(), json=body)
    assert second.status == 200
    assert (await second.json())["receipt"]["duplicate"] is True
    assert (await get_user(UID))["xp"] == 25

    changed = await api.client.post("/api/miniapp/workout", headers=auth(), json=dict(body, sets=[50]))
    assert changed.status == 409
    assert (await changed.json())["error"]["code"] == "idempotency_conflict"
    assert (await get_user(UID))["xp"] == 25


@pytest.mark.asyncio
async def test_concurrent_retries_and_shared_uuid_between_users_are_safe(api):
    await insert_test_user(api.db)
    await insert_test_user(api.db, tg_id=54321)
    body = workout_payload()
    responses = await asyncio.gather(*(
        api.client.post("/api/miniapp/workout", headers=auth(), json=body) for _ in range(3)))
    results = [await response.json() for response in responses]
    assert all(response.status == 200 for response in responses)
    assert sum(not result["receipt"]["duplicate"] for result in results) == 1
    other = await api.client.post("/api/miniapp/workout", headers=auth(54321), json=body)
    assert other.status == 200
    assert not (await other.json())["receipt"]["duplicate"]
    assert (await get_user(UID))["xp"] == (await get_user(54321))["xp"] == 25


@pytest.mark.asyncio
async def test_file_database_receipt_survives_concurrent_requests_and_runtime_restart(tmp_path, monkeypatch):
    """Exercise real HTTP handlers and independent SQLite transaction connections."""
    database_path = tmp_path / "miniapp-restart.sqlite"
    monkeypatch.setattr(db_mod, "DB_PATH", str(database_path))
    monkeypatch.setattr(db_mod, "_conn", None)
    body = workout_payload()
    original_receipt = None
    try:
        for restarted in (False, True):
            # Recreate the DB connection, app, FSM storage, isolation locks and
            # runtime cache. Only the temporary SQLite file survives restart.
            await db_mod.init_db()
            connection = await db_mod.get_db()
            if not restarted:
                await insert_test_user(connection)
            storage = MemoryStorage()
            isolation = SimpleEventIsolation()
            app = web.Application()
            miniapp.setup_miniapp(app, storage=storage, events_isolation=isolation,
                                 bot_id=123456, bot_token=TOKEN)
            try:
                async with TestClient(TestServer(app)) as client:
                    responses = await asyncio.gather(*(
                        client.post("/api/miniapp/workout", headers=auth(), json=body)
                        for _ in range(1 if restarted else 3)))
                    results = [await response.json() for response in responses]
                    assert all(response.status == 200 for response in responses)
                    if not restarted:
                        first = [result["receipt"] for result in results if not result["receipt"]["duplicate"]]
                        assert len(first) == 1
                        original_receipt = first[0]
                    else:
                        assert results[0]["receipt"] == dict(original_receipt, duplicate=True)

                    user = await get_user(UID)
                    row = await get_workout(user["id"], body["date"], "pullups")
                    assert (user["xp"], user["streak"], user["program_day"], user["freeze_tokens"]) == (25, 1, 1, 4)
                    assert row["completed"] == 25
                    assert json.loads(row["sets_json"]) == [10, 8, 7]
                    async with connection.execute(
                        "SELECT session_id FROM workout_completions WHERE user_id=?", (user["id"],),
                    ) as cursor:
                        receipts = await cursor.fetchall()
                    assert [r["session_id"] for r in receipts] == [f"miniapp:{UID}:{body['session_id']}"]
            finally:
                await storage.close()
                await isolation.close()
            await db_mod.close_db()
            assert database_path.is_file()
    finally:
        await db_mod.close_db()


@pytest.mark.asyncio
async def test_successful_retry_after_midnight_returns_original_receipt(api, monkeypatch):
    await insert_test_user(api.db)
    body = workout_payload()
    assert (await api.client.post("/api/miniapp/workout", headers=auth(), json=body)).status == 200
    tomorrow = today() + timedelta(days=1)
    monkeypatch.setattr(miniapp, "today", lambda: tomorrow)
    response = await api.client.post("/api/miniapp/workout", headers=auth(), json=body)
    assert response.status == 200
    assert (await response.json())["receipt"]["duplicate"]
    fresh = dict(body, session_id=str(uuid4()))
    response = await api.client.post("/api/miniapp/workout", headers=auth(), json=fresh)
    assert response.status == 409
    assert (await response.json())["error"]["code"] == "date_changed"
    assert (await get_user(UID))["xp"] == 25


@pytest.mark.asyncio
async def test_weight_is_locked_after_first_completed_set(api):
    await insert_test_user(api.db, base_pullups_weighted=30, weight_pullups_weighted=10)
    body = workout_payload(exercise="pullups_weighted", sets=[10], weight_kg=10)
    first = await api.client.post("/api/miniapp/workout", headers=auth(), json=body)
    assert first.status == 200
    assert (await first.json())["receipt"]["xp_gained"] == 13
    changed = dict(body, session_id=str(uuid4()), weight_kg=30)
    response = await api.client.post("/api/miniapp/workout", headers=auth(), json=changed)
    assert response.status == 409
    assert (await response.json())["error"]["code"] == "weight_locked"
    user = await get_user(UID)
    row = await get_workout(user["id"], body["date"], body["exercise"])
    assert (row["completed"], row["weight_kg"], user["xp"]) == (10, 10, 13)


@pytest.mark.asyncio
async def test_unfinished_server_operation_rolls_back_and_retry_succeeds(api, monkeypatch):
    await insert_test_user(api.db)
    real_persist = miniapp._persist_workout

    async def fail_after_updates(*args):
        await real_persist(*args)
        raise RuntimeError("simulated failure after XP award")

    monkeypatch.setattr(miniapp, "_persist_workout", fail_after_updates)
    body = workout_payload()
    response = await api.client.post("/api/miniapp/workout", headers=auth(), json=body)
    assert response.status == 500
    user = await get_user(UID)
    assert (user["xp"], user["program_day"], user["set_record"]) == (0, 0, 0)
    assert await get_workout(user["id"], body["date"], body["exercise"]) is None
    monkeypatch.setattr(miniapp, "_persist_workout", real_persist)
    assert (await api.client.post("/api/miniapp/workout", headers=auth(), json=body)).status == 200
    assert (await get_user(UID))["xp"] == 25


@pytest.mark.asyncio
async def test_rest_acknowledgement_is_idempotent_and_training_can_override_rest(api):
    yesterday = (today() - timedelta(days=1)).isoformat()
    await insert_test_user(api.db, program_day=3, last_workout=yesterday, streak=3)
    body = workout_payload(exercise="rest", sets=[], rpe=0)
    response = await api.client.post("/api/miniapp/workout", headers=auth(), json=body)
    assert response.status == 200
    assert (await response.json())["receipt"]["xp_gained"] == 0
    assert (await get_user(UID))["program_day"] == 4
    assert (await api.client.post("/api/miniapp/workout", headers=auth(), json=body)).status == 200
    assert (await get_user(UID))["program_day"] == 4
    response = await api.client.post("/api/miniapp/workout", headers=auth(), json=workout_payload())
    assert response.status == 200
    user = await get_user(UID)
    assert (user["program_day"], user["xp"]) == (4, 25)
    assert await get_workout(user["id"], body["date"], "rest") is None


@pytest.mark.asyncio
async def test_planned_reps_are_derived_on_server_and_include_break_reduction(api):
    await insert_test_user(api.db, base=100, last_workout=(today() - timedelta(days=8)).isoformat())
    response = await api.client.post("/api/miniapp/workout", headers=auth(), json=workout_payload())
    assert response.status == 200
    user = await get_user(UID)
    row = await get_workout(user["id"], today().isoformat(), "pullups")
    assert row["planned"] == 60


@pytest.mark.asyncio
async def test_state_preview_does_not_advance_cycle_but_workout_applies_rest_skip(api):
    await insert_test_user(api.db, base=100, program_day=3,
                           last_workout=(today() - timedelta(days=3)).isoformat())
    response = await api.client.get("/api/miniapp/state", headers=auth())
    assert response.status == 200
    state = (await response.json())["state"]
    assert state["today"]["day_type"] == "Плотность"
    assert (await get_user(UID))["program_day"] == 3
    assert state["exercises"][0]["today_planned"] == 75
    response = await api.client.post("/api/miniapp/workout", headers=auth(), json=workout_payload())
    assert response.status == 200
    user = await get_user(UID)
    row = await get_workout(user["id"], today().isoformat(), "pullups")
    assert (user["program_day"], row["day_type"], row["planned"]) == (5, "Плотность", 75)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [{"notify_time": "8:00"}, {"notify_workouts": 1},
                                 {"language": "xx"}, {"program_type": "arbitrary"},
                                 {"exercises": {"pushups": {"max_reps": True}}},
                                 {"exercises": {"squats": {"weight_kg": 20}}},
                                 {"exercises": {"dips_weighted": {"weight_kg": -1}}},
                                 {"name": "Test\nName"}])
async def test_invalid_settings_never_partially_update_the_user(api, bad):
    await insert_test_user(api.db)
    response = await api.client.post("/api/miniapp/settings", headers=auth(), json={"name": "Changed", **bad})
    assert response.status == 400
    user = await get_user(UID)
    assert user["first_name"] == "Test"
    assert user["notify_time"] == "09:00"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [{"sets": []}, {"sets": [True]}, {"sets": [501]}, {"sets": [0]},
                                 {"sets": [1] * 51}, {"rpe": True}, {"rpe": 11}, {"weight_kg": float("nan")},
                                 {"weight_kg": 10 ** 300}, {"exercise": "sql injection"}, {"session_id": "nope"},
                                 {"planned": 1}, {"date": "20260923"}])
async def test_bad_workout_data_is_rejected_without_writes(api, bad):
    await insert_test_user(api.db)
    response = await api.client.post("/api/miniapp/workout", headers=auth(), json=workout_payload(**bad))
    assert response.status == 400
    assert (await get_user(UID))["xp"] == 0


@pytest.mark.asyncio
async def test_json_duplicate_keys_and_oversized_chunked_body_are_rejected(api):
    headers = dict(auth(), **{"Content-Type": "application/json"})
    response = await api.client.post("/api/miniapp/onboarding", headers=headers,
                                     data='{"name":"Alice","name":"Bob","max_pullups":10}')
    assert response.status == 400

    async def chunks():
        yield b'{"name":"'
        yield b'x' * (miniapp.MAX_BODY_BYTES + 1)
        yield b'","max_pullups":10}'

    response = await api.client.post("/api/miniapp/onboarding", headers=headers, data=chunks())
    assert response.status == 413
    assert await get_user(UID) is None


@pytest.mark.asyncio
async def test_rate_limit_is_per_user_and_bounded(api, monkeypatch):
    monkeypatch.setattr(miniapp, "READS_PER_MINUTE", 2)
    assert (await api.client.get("/api/miniapp/state", headers=auth())).status == 200
    assert (await api.client.get("/api/miniapp/state", headers=auth())).status == 200
    response = await api.client.get("/api/miniapp/state", headers=auth())
    assert response.status == 429
    assert response.headers["Retry-After"] == "60"
    assert (await api.client.get("/api/miniapp/state", headers=auth(54321))).status == 200


@pytest.mark.asyncio
async def test_state_uses_real_history_and_limits_other_participants_data(api):
    await insert_test_user(api.db, first_name="Me", last_workout=today().isoformat(), program_day=1)
    await insert_test_user(api.db, tg_id=54321, first_name="Friend", xp=500, streak=3)
    user = await get_user(UID)
    friend = await get_user(54321)
    await upsert_workout(user["id"], today().isoformat(), "pullups", planned=100, completed=25, sets_json="[25]", day_type="Средний")
    await upsert_workout(friend["id"], today().isoformat(), "pushups", planned=100, completed=80, sets_json="[80]", day_type="Средний")
    response = await api.client.get("/api/miniapp/state", headers=auth())
    assert response.status == 200
    state = (await response.json())["state"]
    assert state["stats"]["total_reps"] == 25
    assert state["history"][0]["sets"] == [25]
    assert state["today"]["day_type"] == "Средний"
    assert state["week_plan"][1]["day_type"] == "Лёгкий"
    assert state["leaderboard"][0]["name"] == "Friend"
    assert state["leaderboard"][0]["xp"] == 40
    public = json.dumps([state["leaderboard"], state["friends"]])
    assert "54321" not in public
    assert "tg_id" not in public and "username" not in public and "notify_time" not in public
