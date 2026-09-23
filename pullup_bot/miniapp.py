"""Authenticated Telegram Mini App API backed by the bot's existing database.

Telegram authentication follows https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app.
No bot token, database row, or user identity supplied by the browser is trusted.
"""

import hashlib
import hmac
import json
import math
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import parse_qsl
from uuid import UUID

from aiohttp import web
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from . import globals as g
from .config import (BASE_COLS, BEST_WEIGHT_COLS, BOT_TIMEZONE, BOT_TOKEN,
                     EXERCISES, EXERCISE_EMOJI, LEVEL_THRESHOLDS, MAX_WEIGHT_KG,
                     PR_COLS, PROGRAMS, SET_RECORD_COLS, WEIGHT_COLS, XP_CASE_SQL,
                     is_admin_user, is_weighted, logger, xp_for)
from .db import (clear_rest_row, get_day_rows, get_db, get_user, get_workout,
                 is_muted, is_permanently_banned, mark_rest_day, upsert_workout,
                 workout_transaction)
from .handlers.training import (_coeff_for_day_type, _days_since_last,
                                _persist_workout, _run_cycle_progressions)
from .i18n import day_name, t
from .services.xp import day_type_for, display, level_info, user_base, user_weight
from .timeutils import today

MAX_AUTH_BYTES = 16_384
MAX_BODY_BYTES = 16_384
MAX_AUTH_AGE = 24 * 60 * 60
MAX_FUTURE_SKEW = 60
MAX_SETS = 50
MAX_REPS = 500
MAX_TOTAL_REPS = 10_000
READS_PER_MINUTE = 120
WRITES_PER_MINUTE = 30


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def _invalid(message):
    raise ApiError(400, "invalid_input", message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError("Non-finite JSON number")


def _json_loads(value):
    return json.loads(value, object_pairs_hook=_unique_object, parse_constant=_bad_constant)


def validate_init_data(raw: str, token: str, *, timestamp: float | None = None) -> dict:
    """Verify the bot-token HMAC before trusting Telegram's user JSON or date."""
    bad_auth = ApiError(401, "invalid_auth", "Open the app from Telegram to sign in.")
    try:
        if not isinstance(raw, str) or not raw or not token or len(raw.encode("utf-8")) > MAX_AUTH_BYTES:
            raise bad_auth
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True,
                          max_num_fields=32, encoding="utf-8", errors="strict")
        values = dict(pairs)
        if len(values) != len(pairs) or any(not re.fullmatch(r"[A-Za-z0-9_]+", k) for k in values):
            raise bad_auth
        received = values.pop("hash", "")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", received):
            raise bad_auth
        check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received.lower()):
            raise bad_auth
        auth_date = values.get("auth_date", "")
        if not re.fullmatch(r"\d{1,11}", auth_date):
            raise bad_auth
        current = time.time() if timestamp is None else timestamp
        age = current - int(auth_date)
        if age < -MAX_FUTURE_SKEW:
            raise bad_auth
        if age > MAX_AUTH_AGE:
            raise ApiError(401, "expired_auth", "Your Telegram session expired. Close and reopen the app.")
        user = _json_loads(values.get("user", "null"))
        if not isinstance(user, dict) or type(user.get("id")) is not int:
            raise bad_auth
        if not 0 < user["id"] < 2 ** 52 or user.get("is_bot"):
            raise bad_auth
        if not isinstance(user.get("first_name"), str):
            raise bad_auth
        # Expose only the signed identity fields the UI needs.
        return {"id": user["id"], "first_name": user["first_name"][:128],
                "username": user.get("username", "")[:64] if isinstance(user.get("username", ""), str) else "",
                "language_code": user.get("language_code", "ru")[:16]
                if isinstance(user.get("language_code", "ru"), str) else "ru"}
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise bad_auth from None


@dataclass
class MiniAppRuntime:
    storage: object
    events_isolation: object
    bot_id: int
    bot_token: str
    rate_windows: OrderedDict = field(default_factory=OrderedDict)

    def key(self, uid):
        return StorageKey(bot_id=self.bot_id, chat_id=uid, user_id=uid)

    def check_rate(self, uid, writing):
        now = time.monotonic()
        key = (uid, writing)
        started, count = self.rate_windows.get(key, (now, 0))
        if now - started >= 60:
            started, count = now, 0
        limit = WRITES_PER_MINUTE if writing else READS_PER_MINUTE
        if count >= limit:
            raise ApiError(429, "rate_limited", "Too many requests. Please wait a minute.")
        self.rate_windows[key] = (started, count + 1)
        self.rate_windows.move_to_end(key)
        while len(self.rate_windows) > 4096:
            self.rate_windows.popitem(last=False)


RUNTIME = web.AppKey("miniapp_runtime", MiniAppRuntime)
IDENTITY = "miniapp_verified_identity"


async def _check_access(identity):
    uid = identity["id"]
    if is_admin_user(uid):
        return
    if g.maintenance_mode:
        raise ApiError(403, "maintenance", "The bot is undergoing maintenance. Please try again later.")
    if await is_permanently_banned(uid):
        raise ApiError(403, "banned", "This account is blocked.")
    user = await get_user(uid)
    if user and user["is_banned"]:
        raise ApiError(403, "banned", "This account is blocked.")
    if user and await is_muted(uid):
        raise ApiError(403, "muted", "This account is temporarily muted.")


@web.middleware
async def miniapp_security(request, handler):
    if not request.path.startswith("/api/miniapp/"):
        return await handler(request)
    try:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("tma "):
            raise ApiError(401, "invalid_auth", "Open the app from Telegram to sign in.")
        runtime = request.app[RUNTIME]
        identity = validate_init_data(auth[4:], runtime.bot_token)
        request[IDENTITY] = identity
        runtime.check_rate(identity["id"], request.method != "GET")
        await _check_access(identity)
        response = await handler(request)
    except ApiError as exc:
        response = web.json_response({"ok": False, "error": {"code": exc.code, "message": exc.message}},
                                     status=exc.status)
        if exc.status == 429:
            response.headers["Retry-After"] = "60"
    except web.HTTPException as exc:
        response = web.json_response({"ok": False, "error": {"code": "http_error", "message": exc.reason}},
                                     status=exc.status)
    except Exception:
        logger.exception("Mini App API request failed (%s %s)", request.method, request.path)
        response = web.json_response({"ok": False, "error": {
            "code": "server_error", "message": "Unable to complete the request. Please try again."}}, status=500)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


async def _read_json(request, allowed):
    if request.content_type != "application/json":
        raise ApiError(415, "invalid_input", "Send an application/json request.")
    if request.content_length is not None and request.content_length > MAX_BODY_BYTES:
        raise ApiError(413, "invalid_input", "Request body is too large.")
    chunks = bytearray()
    async for chunk in request.content.iter_chunked(4096):
        chunks.extend(chunk)
        if len(chunks) > MAX_BODY_BYTES:
            raise ApiError(413, "invalid_input", "Request body is too large.")
    try:
        data = _json_loads(chunks.decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError):
        _invalid("Invalid JSON request.")
    if not isinstance(data, dict) or set(data) - allowed:
        _invalid("Unexpected request fields.")
    return data


def _integer(value, minimum, maximum, field_name):
    if type(value) is not int or not minimum <= value <= maximum:
        _invalid(f"{field_name} must be an integer from {minimum} to {maximum}.")
    return value


def _name(value):
    if not isinstance(value, str):
        _invalid("Name must contain 3–64 characters.")
    value = value.strip()
    if not 3 <= len(value) <= 64 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        _invalid("Name must contain 3–64 characters without control characters.")
    return value


def _language(value):
    if value not in ("ru", "en"):
        _invalid("Language must be ru or en.")
    return value


def _program(value):
    if not isinstance(value, str) or value not in PROGRAMS:
        _invalid("Unknown training program.")
    return value


def _weight(value):
    if type(value) not in (int, float) or not 0 <= value <= MAX_WEIGHT_KG or not math.isfinite(value):
        _invalid(f"Weight must be a number from 0 to {MAX_WEIGHT_KG:g} kg.")
    return float(value)


async def _assert_idle(runtime, uid, *, onboarding=False):
    state = await runtime.storage.get_state(runtime.key(uid))
    if state and not (onboarding and state.split(":", 1)[0] in ("Login", "Reg")):
        raise ApiError(409, "bot_session_active", "Finish the current conversation in the bot or send /cancel first.")
    return state


async def _registered_user(uid):
    user = await get_user(uid)
    if not user:
        raise ApiError(403, "registration_required", "Complete your profile first.")
    if user["is_logged_out"]:
        raise ApiError(403, "account_paused", "Resume your account before training.")
    return user


def _today_context(user, rows):
    """Preview the same saved-day and long-break rules as the bot, without writes."""
    training = [r for r in rows if r["exercise"] != "rest"]
    if training:
        day_type = training[0]["day_type"] or day_type_for(user)[0]
    elif rows or user["last_workout"] == today().isoformat():
        day_type = "Отдых"
    else:
        day_type = day_type_for(user)[0]
    skip_rest = day_type == "Отдых" and not training and _days_since_last(user) >= 2
    pd = (user["program_day"] or 0) + int(skip_rest)
    if skip_rest:
        wave = PROGRAMS.get(user["program_type"], PROGRAMS["standard"])
        day_type = wave[pd % 7][0]
    return day_type, pd, skip_rest


def _target(user, exercise, day_type, existing=None):
    if existing and existing["planned"]:
        return existing["planned"]
    planned = int(user_base(user, exercise) * _coeff_for_day_type(user, day_type))
    days_off = _days_since_last(user)
    if 3 <= days_off < 999:
        planned = int(planned * (0.6 if days_off >= 7 else 0.75))
    return planned


def _sets_from_row(row):
    try:
        sets = json.loads(row["sets_json"] or "[]")
        return sets if isinstance(sets, list) and all(type(x) is int and x >= 0 for x in sets) else []
    except (ValueError, TypeError):
        return []


async def _state(identity, runtime):
    uid = identity["id"]
    user = await get_user(uid)
    lang = (user["lang"] or "ru") if user else ("ru" if identity["language_code"].startswith("ru") else "en")
    d = today()
    ds = d.isoformat()
    bot_state = await runtime.storage.get_state(runtime.key(uid))
    state = {
        "registered": user is not None, "date": ds, "timezone": str(BOT_TIMEZONE),
        "language": lang, "telegram_user": {k: identity[k] for k in ("id", "first_name", "username")},
        "user": None, "today": {"day_type": "Средний", "label": day_name("Средний", lang),
                                  "is_rest": False, "completed": 0, "planned": 0, "xp": 0},
        "exercises": [], "week_plan": [], "history": [], "leaderboard": [], "friends": [],
        "stats": {"total_workouts": 0, "total_reps": 0, "week_workouts": 0,
                  "week_reps": 0, "week_xp": 0, "totals": {}},
        "settings": {"language": lang, "notify_time": "09:00", "notify_workouts": False,
                     "program_type": "standard", "name": identity["first_name"]},
        "bot_session": {"active": bool(bot_state), "state": bot_state},
        "limits": {"max_sets": MAX_SETS, "max_reps": MAX_REPS,
                   "max_total_reps": MAX_TOTAL_REPS, "max_weight_kg": MAX_WEIGHT_KG},
    }
    rows = await get_day_rows(user["id"], ds) if user else []
    rows_by_ex = {r["exercise"]: r for r in rows}
    dtype, pd, _ = _today_context(user, rows) if user else ("Средний", 0, False)
    for ex in EXERCISES:
        row = rows_by_ex.get(ex)
        base = user_base(user, ex) if user else 0
        state["exercises"].append({
            "id": ex, "label": t("ex_" + ex, lang), "emoji": EXERCISE_EMOJI[ex],
            "weighted": is_weighted(ex), "configured": base > 0, "base": base,
            "weight_kg": user_weight(user, ex) if user else 0,
            "best_weight_kg": (user[BEST_WEIGHT_COLS[ex]] or 0) if user and is_weighted(ex) else 0,
            "personal_record": (user[PR_COLS[ex]] or 0) if user else 0,
            "set_record": (user[SET_RECORD_COLS[ex]] or 0) if user else 0,
            "today_planned": _target(user, ex, dtype, row) if user else 0,
            "today_completed": (row["completed"] or 0) if row else 0,
            "today_sets": _sets_from_row(row) if row else [],
            "today_weight_kg": (row["weight_kg"] or 0) if row else (user_weight(user, ex) if user else 0),
            "weight_locked": bool(is_weighted(ex) and row and row["completed"] > 0),
        })
    if not user:
        return state

    level, name, to_next, progress = level_info(user["xp"] or 0)
    state["user"] = {
        "id": user["id"], "name": display(user), "username": user["username"] or "",
        "xp": user["xp"] or 0, "level": level, "level_name": name,
        "next_level_xp": LEVEL_THRESHOLDS[level + 1], "xp_to_next": max(0, to_next),
        "level_progress": min(100, max(0, progress)), "streak": user["streak"] or 0,
        "max_streak": user["max_streak"] or 0, "freeze_tokens": user["freeze_tokens"] or 0,
        "joined": user["joined"], "program_day": user["program_day"] or 0,
        "is_logged_out": bool(user["is_logged_out"]), "is_weekly_champ": bool(user["is_weekly_champ"]),
    }
    state["settings"] = {"name": display(user), "language": lang,
                         "notify_time": user["notify_time"], "notify_workouts": bool(user["notify_workouts"]),
                         "program_type": user["program_type"] or "standard"}
    state["today"] = {"day_type": dtype, "label": day_name(dtype, lang), "is_rest": dtype == "Отдых",
                      "completed": sum(ex["today_completed"] for ex in state["exercises"]),
                      "planned": sum(ex["today_planned"] for ex in state["exercises"]),
                      "xp": sum(xp_for(r["exercise"], r["completed"] or 0, r["weight_kg"] or 0) for r in rows)}
    wave = PROGRAMS.get(user["program_type"], PROGRAMS["standard"])
    for offset in range(7):
        future_type, coeff = (dtype, _coeff_for_day_type(user, dtype)) if offset == 0 else wave[
            (pd + offset - int(user["last_workout"] == ds)) % 7]
        state["week_plan"].append({"date": (d + timedelta(days=offset)).isoformat(),
                                  "day_type": future_type, "label": day_name(future_type, lang),
                                  "is_rest": future_type == "Отдых",
                                  "targets": {ex: (rows_by_ex[ex]["planned"] if offset == 0 and ex in rows_by_ex
                                                       else _target(user, ex, dtype) if offset == 0
                                                       else int(user_base(user, ex) * coeff)) for ex in EXERCISES}})
    conn = await get_db()
    monday = (d - timedelta(days=d.weekday())).isoformat()
    async with conn.execute(
        "SELECT * FROM workouts WHERE user_id=? AND date>=? AND date<=? ORDER BY date DESC, id DESC LIMIT 700",
        (user["id"], (d - timedelta(days=89)).isoformat(), ds),
    ) as cur:
        history = await cur.fetchall()
    state["history"] = [{"date": r["date"], "exercise": r["exercise"],
                         "label": day_name("Отдых", lang) if r["exercise"] == "rest" else t("ex_" + r["exercise"], lang),
                         "planned": r["planned"] or 0, "completed": r["completed"] or 0,
                         "sets": _sets_from_row(r), "rpe": r["rpe"] or 0, "weight_kg": r["weight_kg"] or 0,
                         "day_type": r["day_type"], "xp": xp_for(r["exercise"], r["completed"] or 0, r["weight_kg"] or 0)}
                        for r in history]
    async with conn.execute(
        "SELECT exercise, SUM(completed) AS reps FROM workouts WHERE user_id=? AND completed>0 GROUP BY exercise",
        (user["id"],),
    ) as cur:
        totals = {row["exercise"]: row["reps"] for row in await cur.fetchall()}
    async with conn.execute(
        "SELECT COUNT(DISTINCT date) FROM workouts WHERE user_id=? AND completed>0", (user["id"],),
    ) as cur:
        total_days = (await cur.fetchone())[0]
    week = [r for r in history if r["date"] >= monday and r["completed"] > 0]
    state["stats"] = {"total_workouts": total_days, "total_reps": sum(totals.values()), "totals": totals,
                      "week_workouts": len({r["date"] for r in week}), "week_reps": sum(r["completed"] for r in week),
                      "week_xp": sum(xp_for(r["exercise"], r["completed"], r["weight_kg"]) for r in week)}
    # Participants already appear in the bot. Expose only display names and
    # public training totals, never other users' Telegram IDs or account settings.
    async with conn.execute(
        f"SELECT u.id, u.first_name, u.username, u.streak, u.is_weekly_champ, COALESCE(SUM({XP_CASE_SQL}),0) AS weekly_xp "
        "FROM users u LEFT JOIN workouts w ON w.user_id=u.id AND w.date>=? AND w.date<=? "
        "WHERE u.is_banned=0 AND u.is_logged_out=0 AND u.tg_id NOT IN (SELECT tg_id FROM banned_ids) "
        "GROUP BY u.id HAVING weekly_xp>0 ORDER BY weekly_xp DESC, u.id ASC LIMIT 50",
        (monday, ds),
    ) as cur:
        leaders = await cur.fetchall()
    state["leaderboard"] = [{"rank": rank, "name": display(row), "xp": round(row["weekly_xp"], 2),
                             "streak": row["streak"] or 0, "is_me": row["id"] == user["id"],
                             "is_weekly_champ": bool(row["is_weekly_champ"])} for rank, row in enumerate(leaders, 1)]
    async with conn.execute(
        "SELECT u.id,u.first_name,u.username,u.xp,u.streak,u.is_weekly_champ, "
        "COALESCE(SUM(CASE WHEN w.date=? THEN w.completed ELSE 0 END),0) AS today_completed "
        "FROM users u LEFT JOIN workouts w ON w.user_id=u.id AND w.date>=? AND w.date<=? "
        "WHERE u.is_banned=0 AND u.is_logged_out=0 AND u.tg_id NOT IN (SELECT tg_id FROM banned_ids) "
        "GROUP BY u.id HAVING SUM(w.completed)>0 OR u.id=? ORDER BY u.id LIMIT 50",
        (ds, (d - timedelta(days=6)).isoformat(), ds, user["id"]),
    ) as cur:
        friends = await cur.fetchall()
    state["friends"] = [{"name": display(row), "streak": row["streak"] or 0,
                         "level_name": level_info(row["xp"] or 0)[1], "is_me": row["id"] == user["id"],
                         "is_weekly_champ": bool(row["is_weekly_champ"]), "today_completed": row["today_completed"]}
                        for row in friends]
    return state


async def get_state(request):
    return web.json_response({"ok": True, "state": await _state(request[IDENTITY], request.app[RUNTIME])})


async def onboarding(request):
    data = await _read_json(request, {"name", "language", "max_pullups", "program_type"})
    identity, runtime = request[IDENTITY], request.app[RUNTIME]
    uid = identity["id"]
    async with runtime.events_isolation.lock(runtime.key(uid)):
        await _assert_idle(runtime, uid, onboarding=True)
        async with workout_transaction() as conn:
            await _check_access(identity)
            user = await get_user(uid)
            if user:
                if user["is_logged_out"]:
                    # A deliberate pause preserves the streak and grants a fresh
                    # inactivity window, as logging back in through the bot does.
                    # Keep a newer activity date when resuming on the same day.
                    yesterday = (today() - timedelta(days=1)).isoformat()
                    last = max(user["last_workout"] or yesterday, yesterday)
                    await conn.execute("UPDATE users SET is_logged_out=0,last_workout=? WHERE tg_id=?", (last, uid))
            else:
                name = _name(data.get("name"))
                lang = _language(data.get("language", "ru" if identity["language_code"].startswith("ru") else "en"))
                maximum = _integer(data.get("max_pullups"), 1, 200, "max_pullups")
                program = _program(data.get("program_type", "standard"))
                await conn.execute(
                    "INSERT INTO users (tg_id,username,first_name,base_pullups,start_day,lang,program_day,joined,program_type) "
                    "VALUES (?,?,?,?,0,?,0,?,?)",
                    (uid, identity["username"] or name, name, max(5, maximum * 3), lang, today().isoformat(), program))
        # Registration through the app completes the corresponding bot dialog.
        await FSMContext(runtime.storage, runtime.key(uid)).clear()
        state = await _state(identity, runtime)
    return web.json_response({"ok": True, "state": state})


def _settings_values(data):
    values = {}
    if "name" in data:
        values["first_name"] = _name(data["name"])
    if "language" in data:
        values["lang"] = _language(data["language"])
    if "program_type" in data:
        values["program_type"] = _program(data["program_type"])
    if "notify_time" in data:
        value = data["notify_time"]
        if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            _invalid("Reminder time must be HH:MM, from 00:00 to 23:59.")
        values["notify_time"] = value
    if "notify_workouts" in data:
        if type(data["notify_workouts"]) is not bool:
            _invalid("notify_workouts must be true or false.")
        values["notify_workouts"] = int(data["notify_workouts"])
    if "exercises" in data:
        exercises = data["exercises"]
        if not isinstance(exercises, dict) or set(exercises) - set(EXERCISES):
            _invalid("Unknown exercise settings.")
        for exercise, options in exercises.items():
            if not isinstance(options, dict) or not options or set(options) - {"max_reps", "weight_kg"}:
                _invalid("Exercise settings accept max_reps and weight_kg.")
            if "max_reps" in options:
                values[BASE_COLS[exercise]] = max(5, _integer(options["max_reps"], 1, 200, "max_reps") * 3)
            if "weight_kg" in options:
                if not is_weighted(exercise):
                    _invalid("Only weighted exercises accept weight_kg.")
                values[WEIGHT_COLS[exercise]] = _weight(options["weight_kg"])
    if not values:
        _invalid("No settings were provided.")
    return values


async def settings(request):
    data = await _read_json(request, {"name", "language", "notify_time", "notify_workouts", "program_type", "exercises"})
    values = _settings_values(data)
    identity, runtime = request[IDENTITY], request.app[RUNTIME]
    uid = identity["id"]
    async with runtime.events_isolation.lock(runtime.key(uid)):
        await _assert_idle(runtime, uid)
        async with workout_transaction() as conn:
            await _check_access(identity)
            await _registered_user(uid)
            await conn.execute("UPDATE users SET " + ",".join(f"{col}=?" for col in values) + " WHERE tg_id=?",
                               (*values.values(), uid))
        state = await _state(identity, runtime)
    return web.json_response({"ok": True, "state": state})


def _workout_values(data):
    try:
        session_id = str(UUID(data.get("session_id", "")))
    except (ValueError, TypeError, AttributeError):
        _invalid("session_id must be a UUID.")
    if UUID(session_id).int == 0:
        _invalid("session_id must be a non-zero UUID.")
    exercise = data.get("exercise")
    if exercise not in [*EXERCISES, "rest"]:
        _invalid("Unknown exercise.")
    d = data.get("date")
    try:
        if not isinstance(d, str) or date.fromisoformat(d).isoformat() != d:
            raise ValueError
    except ValueError:
        _invalid("date must use YYYY-MM-DD.")
    sets = data.get("sets")
    if not isinstance(sets, list) or len(sets) > MAX_SETS:
        _invalid(f"sets must be a list of at most {MAX_SETS} rep counts.")
    for reps in sets:
        _integer(reps, 1, MAX_REPS, "reps")
    if sum(sets) > MAX_TOTAL_REPS:
        _invalid(f"A session may contain at most {MAX_TOTAL_REPS} repetitions.")
    if exercise == "rest":
        if sets or _integer(data.get("rpe", 0), 0, 0, "rpe") != 0 or _weight(data.get("weight_kg", 0)) != 0:
            _invalid("Rest has no sets, RPE or added weight.")
        rpe, weight = 0, 0.0
    else:
        if not sets:
            _invalid("Record at least one set before finishing.")
        rpe = _integer(data.get("rpe"), 1, 10, "rpe")
        weight = _weight(data.get("weight_kg", 0))
        if not is_weighted(exercise) and weight != 0:
            _invalid("Bodyweight exercises cannot have added weight.")
    return {"session_id": session_id, "exercise": exercise, "date": d, "sets": sets, "rpe": rpe, "weight_kg": weight}


async def _save_api_workout(uid, payload):
    """Use the same XP/progression service and durable receipts as bot sessions."""
    key = f"miniapp:{uid}:{payload['session_id']}"
    async with workout_transaction() as conn:
        await _check_access({"id": uid})
        user = await _registered_user(uid)
        async with conn.execute("SELECT result_json FROM workout_completions WHERE session_id=? AND user_id=?",
                                (key, user["id"])) as cursor:
            existing_receipt = await cursor.fetchone()
        if existing_receipt:
            saved = json.loads(existing_receipt["result_json"])
            if saved["request"] != payload:
                raise ApiError(409, "idempotency_conflict", "This session ID was already used for different workout data.")
            return dict(saved["receipt"], duplicate=True)
        d = payload["date"]
        if d != today().isoformat():
            raise ApiError(409, "date_changed", "The training date changed. Refresh the app before saving.")
        exercise = payload["exercise"]
        rows = await get_day_rows(user["id"], d)
        dtype, effective_pd, skip_rest = _today_context(user, rows)
        if skip_rest:
            await conn.execute("UPDATE users SET program_day=? WHERE id=?", (effective_pd, user["id"]))
            await clear_rest_row(user["id"], d)
            if effective_pd % 7 == 0:
                await _run_cycle_progressions(uid, user["id"])
            user = await get_user(uid)
        lang = user["lang"] or "ru"
        xp_before = user["xp"] or 0
        if exercise == "rest":
            if dtype != "Отдых" or any((r["completed"] or 0) > 0 for r in rows):
                raise ApiError(409, "rest_not_available", "Today already has a workout or is a training day.")
            await mark_rest_day(user["id"], d)
            if user["last_workout"] != d:
                pd = (user["program_day"] or 0) + 1
                await conn.execute("UPDATE users SET program_day=?,last_workout=? WHERE id=?", (pd, d, user["id"]))
                if pd % 7 == 0:
                    await _run_cycle_progressions(uid, user["id"])
            result = {"done": 0, "summary": "День отдыха сохранён." if lang == "ru" else "Rest day saved."}
        else:
            if user_base(user, exercise) <= 0:
                raise ApiError(400, "exercise_not_configured", "Set your maximum reps for this exercise first.")
            existing = await get_workout(user["id"], d, exercise)
            weight = payload["weight_kg"]
            if existing and existing["completed"] > 0 and is_weighted(exercise) and weight != float(existing["weight_kg"] or 0):
                raise ApiError(409, "weight_locked", "Additional sets today must use the weight already saved for this exercise.")
            dtype = "Средний" if dtype == "Отдых" else dtype
            planned = _target(user, exercise, dtype, existing)
            await clear_rest_row(user["id"], d)
            if is_weighted(exercise):
                await conn.execute(f"UPDATE users SET {WEIGHT_COLS[exercise]}=? WHERE id=?", (weight, user["id"]))
            if not existing:
                await upsert_workout(user["id"], d, exercise, planned=planned, day_type=dtype, weight_kg=weight)
            old_record = user[SET_RECORD_COLS[exercise]] or 0
            top_set = max(payload["sets"])
            if top_set > old_record:
                await conn.execute(f"UPDATE users SET {SET_RECORD_COLS[exercise]}=? WHERE id=?", (top_set, user["id"]))
            result = await _persist_workout({"date": d, "exercise": exercise, "sets": payload["sets"],
                                             "planned": planned, "rpe": payload["rpe"], "weight": weight,
                                             "lang": lang, "pick_day_type": dtype,
                                             "session_set_pr": top_set if top_set > old_record else None}, uid)
        updated = await get_user(uid)
        receipt = {"session_id": payload["session_id"], "duplicate": False, "exercise": exercise,
                   "date": d, "completed": result["done"], "xp_gained": (updated["xp"] or 0) - xp_before,
                   "xp_total": updated["xp"] or 0, "summary": result["summary"]}
        await conn.execute("INSERT INTO workout_completions (session_id,user_id,result_json) VALUES (?,?,?)",
                           (key, user["id"], json.dumps({"request": payload, "receipt": receipt})))
        return receipt


async def workout(request):
    data = await _read_json(request, {"session_id", "exercise", "date", "sets", "rpe", "weight_kg"})
    payload = _workout_values(data)
    identity, runtime = request[IDENTITY], request.app[RUNTIME]
    uid = identity["id"]
    async with runtime.events_isolation.lock(runtime.key(uid)):
        await _assert_idle(runtime, uid)
        await _check_access(identity)
        receipt = await _save_api_workout(uid, payload)
        state = await _state(identity, runtime)
    return web.json_response({"ok": True, "receipt": receipt, "state": state})


def setup_miniapp(app: web.Application, *, storage, events_isolation, bot_id: int, bot_token: str | None = None):
    """Register only API routes; share the bot's private-chat FSM lock and storage."""
    app[RUNTIME] = MiniAppRuntime(storage, events_isolation, bot_id, BOT_TOKEN if bot_token is None else bot_token)
    app.middlewares.append(miniapp_security)
    app.router.add_get("/api/miniapp/state", get_state)
    app.router.add_post("/api/miniapp/onboarding", onboarding)
    app.router.add_post("/api/miniapp/workout", workout)
    app.router.add_post("/api/miniapp/settings", settings)
