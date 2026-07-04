from datetime import date, datetime, timedelta, timezone

from aiogram.exceptions import TelegramForbiddenError

from ..config import (ADMIN_TG_ID, EXERCISES, EXERCISE_EMOJI,
                      TZ_OFFSET_HOURS, XP_CASE_SQL, logger, xp_for)
from ..db import get_db, get_day_rows, mark_rest_day
from ..i18n import t, day_name
from ..services.xp import day_type_for, display, md_escape, user_base
from . import monitoring


async def _delete_user(conn, user_id: int):
    """Delete all data for a user by their DB id."""
    await conn.execute("DELETE FROM workouts WHERE user_id=?", (user_id,))
    await conn.execute("DELETE FROM friends WHERE user_id=? OR friend_id=?", (user_id, user_id))
    await conn.execute("DELETE FROM streak_recoveries WHERE user_id=?", (user_id,))
    await conn.execute("DELETE FROM bug_reports WHERE user_id=?", (user_id,))
    await conn.execute("DELETE FROM ai_usage_log WHERE user_id=?", (user_id,))
    await conn.execute("DELETE FROM pokes WHERE from_user_id=? OR to_user_id=?",
                       (user_id, user_id))
    await conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    await conn.commit()


async def daily_reminder(bot):
    """Send personalized morning reminders to all users whose notify_time matches the current minute."""
    tz = timezone(timedelta(hours=TZ_OFFSET_HOURS))
    now = datetime.now(tz).strftime("%H:%M")
    conn = await get_db()
    async with conn.execute(
        "SELECT * FROM users WHERE notify_time=? AND is_logged_out=0 AND is_banned=0", (now,)
    ) as cur:
        users = await cur.fetchall()
    for user in users:
        lang = user["lang"] or "ru"
        day_rows = await get_day_rows(user["id"])
        training_rows = [r for r in day_rows if r["exercise"] != "rest"]
        any_done = any((r["completed"] or 0) > 0 for r in training_rows)
        if any_done:
            continue  # the day is already saved — no nagging needed
        if training_rows:
            day_type = training_rows[0]["day_type"] or day_type_for(user)[0]
        elif day_rows:
            day_type = "Отдых"
        else:
            day_type = day_type_for(user)[0]
            # Same auto-advance as training handler: if the cycle says rest but
            # the user has already been off for 2+ days, today is actually a
            # training day — advance the cycle and recalculate.
            if day_type == "Отдых" and user["last_workout"]:
                try:
                    days_off = (date.today() - date.fromisoformat(user["last_workout"])).days
                except Exception:
                    days_off = 0
                if days_off >= 2:
                    new_pd = (user["program_day"] or 0) + 1
                    await conn.execute(
                        "UPDATE users SET program_day=? WHERE id=?", (new_pd, user["id"])
                    )
                    await conn.commit()
                    if new_pd % 7 == 0:
                        from ..handlers.training import _run_cycle_progressions
                        await _run_cycle_progressions(user["tg_id"], user["id"])
                    async with conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)) as cur:
                        user = await cur.fetchone()
                    day_type = day_type_for(user)[0]
        if day_type == "Отдых":
            msg = t("reminder_rest", lang)
        else:
            from ..handlers.training import _coeff_for_day_type, ex_label
            coeff = _coeff_for_day_type(user, day_type)
            plan_lines = [
                f"• {ex_label(ex, lang)}: {int(user_base(user, ex) * coeff)}"
                for ex in EXERCISES if user_base(user, ex) > 0
            ]
            msg = t("reminder_train", lang,
                    day_type=day_name(day_type, lang),
                    plans="\n".join(plan_lines),
                    status=t("reminder_not_started", lang))
        notify_time = user["notify_time"] or "09:00"
        silent = notify_time >= "22:00" or notify_time < "08:00"
        try:
            await bot.send_message(user["tg_id"], msg, disable_notification=silent)
        except TelegramForbiddenError:
            last = user["last_workout"]
            inactive = (not last or
                        (date.today() - date.fromisoformat(last)).days >= 7)
            if inactive:
                logger.info(f"[reminder] blocked+inactive 7d, removing user {user['tg_id']}")
                await _delete_user(conn, user["id"])
            else:
                logger.info(f"[reminder] user {user['tg_id']} blocked the bot but still active")
        except Exception as e:
            logger.warning(f"[reminder] {user['tg_id']}: {e}")


async def _announce_weekly_champ(bot, conn, users):
    """Crown the user with the most pullups last week and broadcast the result."""
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Single query instead of N+1 per-user loop — weekly XP across all exercises
    async with conn.execute(
        f"SELECT user_id, COALESCE(SUM({XP_CASE_SQL}),0) as total FROM workouts "
        "WHERE date>=? AND date<=? GROUP BY user_id",
        (week_ago, yesterday)
    ) as cur:
        totals_rows = await cur.fetchall()
    totals_map = {r["user_id"]: int(round(r["total"])) for r in totals_rows}

    entries = [(user, totals_map.get(user["id"], 0)) for user in users]
    entries.sort(key=lambda x: x[1], reverse=True)
    if not entries or entries[0][1] == 0:
        return  # nobody trained — skip the ceremony

    champ, champ_total = entries[0]

    # Crown the new champion atomically
    await conn.execute(
        "UPDATE users SET is_weekly_champ = CASE WHEN id=? THEN 1 ELSE 0 END",
        (champ["id"],)
    )
    await conn.commit()

    medals = ["🥇", "🥈", "🥉"]
    top3_text = "\n".join(
        f"{medals[i]} *{md_escape(display(u))}* — {total}"
        for i, (u, total) in enumerate(entries[:3])
        if total > 0
    )
    champ_name = md_escape(display(champ))

    for user in users:
        lang = user["lang"] or "ru"
        is_winner = user["id"] == champ["id"]
        if lang == "ru":
            suffix = "🎉 *Поздравляем — корона твоя!*" if is_winner else "💪 На следующей неделе корона может быть твоей!"
            msg = (
                f"👑 *Кочка недели*\n\n"
                f"Неделя позади — подводим итоги!\n\n"
                f"🏆 Лучший атлет: *{champ_name}*\n"
                f"⭐ XP за неделю: *{champ_total}*\n\n"
                f"Топ недели:\n{top3_text}\n\n"
                f"{suffix}"
            )
        else:
            suffix = "🎉 *Congrats — the crown is yours!*" if is_winner else "💪 Next week the crown could be yours!"
            msg = (
                f"👑 *Beast of the Week*\n\n"
                f"The week is over — here are the results!\n\n"
                f"🏆 Top athlete: *{champ_name}*\n"
                f"⭐ Weekly XP: *{champ_total}*\n\n"
                f"Top of the week:\n{top3_text}\n\n"
                f"{suffix}"
            )
        try:
            await bot.send_message(user["tg_id"], msg, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"[weekly_champ] {user['tg_id']}: {e}")


async def weekly_summary(bot):
    """Send weekly summary to every user every Monday at 08:00."""
    conn = await get_db()
    async with conn.execute("SELECT * FROM users WHERE is_logged_out=0 AND is_banned=0") as cur:
        users = await cur.fetchall()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    for user in users:
        lang = user["lang"] or "ru"
        async with conn.execute(
            "SELECT * FROM workouts WHERE user_id=? AND date>=? AND date<=? "
            "AND exercise != 'rest' ORDER BY date ASC",
            (user["id"], week_ago, yesterday)
        ) as cur:
            rows = await cur.fetchall()
        if not rows or not any((r["completed"] or 0) > 0 for r in rows):
            try:
                await bot.send_message(user["tg_id"], t("weekly_summary_no_workouts", lang))
            except Exception as e:
                logger.warning(f"[weekly_summary] send failed for {user['tg_id']}: {e}")
            continue
        totals: dict = {}
        for r in rows:
            done_p, planned_p = totals.get(r["exercise"], (0, 0))
            totals[r["exercise"]] = (done_p + (r["completed"] or 0),
                                     planned_p + (r["planned"] or 0))
        volume_lines = []
        for ex in EXERCISES:
            if ex not in totals:
                continue
            done_e, planned_e = totals[ex]
            pct_e = int(done_e / planned_e * 100) if planned_e else 0
            volume_lines.append(
                f"  {EXERCISE_EMOJI[ex]} {t('ex_' + ex, lang)}: {done_e}/{planned_e} ({pct_e}%)")
        week_xp = sum(xp_for(r["exercise"], r["completed"] or 0) for r in rows)
        rpe_rows = [r["rpe"] for r in rows if r["rpe"] and r["rpe"] > 0]
        avg_rpe = f"{sum(rpe_rows)/len(rpe_rows):.1f}" if rpe_rows else "—"
        msg = (
            t("weekly_summary_title", lang) + "\n"
            f"👤 *{md_escape(display(user))}*\n\n" +
            t("weekly_summary_body", lang,
              volume="\n".join(volume_lines), week_xp=week_xp,
              avg_rpe=avg_rpe, streak=user["streak"],
              freeze=user["freeze_tokens"])
        )
        try:
            await bot.send_message(user["tg_id"], msg, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"[weekly_summary] {user['tg_id']}: {e}")

    # After personal summaries, crown the week's champion
    await _announce_weekly_champ(bot, conn, users)


async def daily_health_summary(bot):
    """Send daily health summary to admin at 08:00."""
    snap = monitoring.reset()
    conn = await get_db()
    async with conn.execute("SELECT COUNT(*) FROM users") as cur:
        row = await cur.fetchone()
        total_users = row[0] if row else 0
    today = date.today().isoformat()
    async with conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM workouts WHERE date=? AND completed > 0",
        (today,)
    ) as cur:
        row = await cur.fetchone()
        workouts_today = row[0] if row else 0
    errors = snap.get("errors", 0)
    unhandled = snap.get("unhandled", 0)
    actions = snap.get("actions", 0)
    msg = (
        f"📊 Ежедневный отчёт бота\n"
        f"👤 Пользователей: {total_users}\n"
        f"🏋️ Тренировок сегодня: {workouts_today}\n"
        f"⚡ Действий за сутки: {actions}\n"
        f"❌ Ошибок: {errors}\n"
        f"❓ Необработанных сообщений: {unhandled}"
    )
    try:
        await bot.send_message(ADMIN_TG_ID, msg)
    except Exception as e:
        logger.warning(f"[health_summary] {e}")


async def db_integrity_check(bot):
    """Periodic DB integrity check at 03:00."""
    issues = []
    conn = await get_db()
    try:
        async with conn.execute("PRAGMA integrity_check") as cur:
            row = await cur.fetchone()
            if row and row[0] != "ok":
                issues.append(f"integrity_check: {row[0]}")
    except Exception as e:
        issues.append(f"integrity_check error: {e}")

    try:
        async with conn.execute(
            "SELECT COUNT(*) FROM users WHERE base_pullups <= 0"
        ) as cur:
            row = await cur.fetchone()
            bad = row[0] if row else 0
            if bad:
                issues.append(f"{bad} users with base_pullups <= 0")
    except Exception as e:
        issues.append(f"anomaly check error: {e}")

    if issues:
        msg = "⚠️ DB integrity issues:\n" + "\n".join(f"• {i}" for i in issues)
        logger.error(f"[db_integrity] {msg}")
        try:
            await bot.send_message(ADMIN_TG_ID, msg)
        except Exception as e:
            logger.warning(f"[db_integrity] alert failed: {e}")
    else:
        logger.info("[db_integrity] OK")


async def daily_xp_decay(bot):
    """
    Decay XP daily for users inactive 7+ days.
    Grace period: 7 days — no decay before that.
    Notifies the user only on the first decay day and whenever they lose a rank.
    """
    from ..db import apply_xp_decay
    from ..config import LEVEL_NAMES
    today = date.today()
    conn = await get_db()
    async with conn.execute(
        "SELECT * FROM users WHERE last_workout IS NOT NULL AND is_logged_out=0 AND is_banned=0"
    ) as cur:
        users = await cur.fetchall()

    decayed = 0
    for user in users:
        try:
            days_inactive = (today - date.fromisoformat(user["last_workout"])).days
        except Exception:
            continue
        if days_inactive < 7:
            continue
        result = await apply_xp_decay(user["tg_id"], days_inactive)
        if result is None:
            continue
        old_xp, new_xp, old_level, new_level = result
        decayed += 1
        lang = user["lang"] or "ru"
        rank_lost = new_level < old_level
        first_decay = days_inactive == 7
        # Notify only on first decay day or rank loss — avoid daily spam
        if not first_decay and not rank_lost:
            continue
        if rank_lost:
            msg = (
                f"📉 Ты не тренировался {days_inactive} дней — ранг упал!\n"
                f"*{LEVEL_NAMES[old_level]}* → *{LEVEL_NAMES[new_level]}*\n"
                f"XP: {old_xp} → {new_xp}\n\n"
                f"Вернись и тренируйся, чтобы восстановить ранг 💪"
                if lang == "ru" else
                f"📉 You haven't trained for {days_inactive} days — rank dropped!\n"
                f"*{LEVEL_NAMES[old_level]}* → *{LEVEL_NAMES[new_level]}*\n"
                f"XP: {old_xp} → {new_xp}\n\n"
                f"Come back and train to recover your rank 💪"
            )
        else:
            msg = (
                f"⏳ Ты не тренировался {days_inactive} дней — XP начал убывать.\n"
                f"XP: {old_xp} → {new_xp}\n\n"
                f"Тренируйся, чтобы остановить потерю 💪"
                if lang == "ru" else
                f"⏳ You haven't trained for {days_inactive} days — XP is decaying.\n"
                f"XP: {old_xp} → {new_xp}\n\n"
                f"Train to stop the loss 💪"
            )
        try:
            await bot.send_message(user["tg_id"], msg, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"[xp_decay] {user['tg_id']}: {e}")

    logger.info(f"[xp_decay] applied decay to {decayed} user(s)")


async def auto_cleanup_inactive(bot):
    """Warn at 27 days of inactivity, delete at 30 days."""
    today = date.today()
    cutoff_delete = (today - timedelta(days=30)).isoformat()
    cutoff_warn = (today - timedelta(days=27)).isoformat()
    conn = await get_db()

    # Step 1: delete accounts inactive 30+ days (skip logged-out users — they're paused)
    async with conn.execute(
        "SELECT * FROM users WHERE last_workout IS NOT NULL AND last_workout < ? AND is_logged_out=0 AND is_banned=0",
        (cutoff_delete,)
    ) as cur:
        stale = await cur.fetchall()
    deleted = 0
    for user in stale:
        logger.info(f"[cleanup] deleting inactive 30d user {user['tg_id']}")
        await _delete_user(conn, user["id"])
        deleted += 1

    # Step 2: warn accounts inactive 27–29 days (warning not yet sent, skip logged-out)
    async with conn.execute(
        "SELECT * FROM users WHERE last_workout IS NOT NULL AND last_workout < ? "
        "AND last_workout >= ? AND inactivity_warned IS NULL AND is_logged_out=0 AND is_banned=0",
        (cutoff_warn, cutoff_delete)
    ) as cur:
        to_warn = await cur.fetchall()
    warned = 0
    for user in to_warn:
        lang = user["lang"] or "ru"
        days_inactive = (today - date.fromisoformat(user["last_workout"])).days
        days_left = 30 - days_inactive
        msg = (
            f"⚠️ Ты не тренировался {days_inactive} дней.\n\n"
            f"Через {days_left} дн. аккаунт будет удалён автоматически.\n"
            f"Зайди и сделай хоть одну тренировку, чтобы сохранить данные 💪"
            if lang == "ru" else
            f"⚠️ You haven't trained for {days_inactive} days.\n\n"
            f"Your account will be deleted in {days_left} day(s) if you stay inactive.\n"
            f"Log a workout to keep your data 💪"
        )
        try:
            await bot.send_message(user["tg_id"], msg)
            await conn.execute(
                "UPDATE users SET inactivity_warned=? WHERE id=?",
                (today.isoformat(), user["id"])
            )
            await conn.commit()
            warned += 1
        except Exception as e:
            logger.warning(f"[cleanup] warning failed for {user['tg_id']}: {e}")

    if deleted or warned:
        try:
            await bot.send_message(
                ADMIN_TG_ID,
                f"🧹 Авто-очистка:\n"
                f"🗑 Удалено: {deleted} (30+ дней неактивны)\n"
                f"⚠️ Предупреждено: {warned} (27+ дней неактивны)"
            )
        except Exception as e:
            logger.warning(f"[cleanup] admin notify failed: {e}")


async def auto_acknowledge_rest_days(bot):
    """Silently acknowledge rest days for users who trained yesterday but didn't open the bot today."""
    tz = timezone(timedelta(hours=TZ_OFFSET_HOURS))
    today_str = datetime.now(tz).date().isoformat()
    yesterday_str = (datetime.now(tz).date() - timedelta(days=1)).isoformat()

    conn = await get_db()
    async with conn.execute(
        "SELECT * FROM users WHERE last_workout=? AND is_logged_out=0 AND is_banned=0",
        (yesterday_str,)
    ) as cur:
        users = await cur.fetchall()

    acknowledged = 0
    for user in users:
        name, _ = day_type_for(user)
        if name != "Отдых":
            continue
        # Don't clobber a day the user actually interacted with (e.g. an
        # in-progress rest-day-override training session)
        day_rows = await get_day_rows(user["id"], today_str)
        if any((r["planned"] or 0) > 0 or (r["completed"] or 0) > 0 for r in day_rows):
            continue
        program_day = user["program_day"] or 0
        # Advance program_day and mark last_workout=today so the streak stays intact
        new_pd = program_day + 1
        await conn.execute(
            "UPDATE users SET program_day=?, last_workout=? WHERE id=?",
            (new_pd, today_str, user["id"])
        )
        await mark_rest_day(user["id"], today_str)
        if new_pd % 7 == 0:
            from ..handlers.training import _run_cycle_progressions
            await _run_cycle_progressions(user["tg_id"], user["id"])
        acknowledged += 1

    if acknowledged:
        await conn.commit()
    logger.info(f"[auto_rest] auto-acknowledged {acknowledged} rest day(s)")


# ── Self-diagnosis watchdog ─────────────────────────────────────────────────

# Track consecutive error-only intervals to detect silent failures
_watchdog_prev_errors = 0
_watchdog_prev_actions = 0
_watchdog_error_streak = 0


async def watchdog_health_check(bot):
    """
    Runs every 5 minutes. Detects:
    1. DB connection dead → reconnect
    2. Stale FSM states (user stuck 2+ hours) → auto-clear and notify user
    3. Error rate spikes → alert admin immediately
    """
    global _watchdog_prev_errors, _watchdog_prev_actions, _watchdog_error_streak
    issues = []

    # ── 1. DB liveness check ────────────────────────────────────────────────
    try:
        conn = await get_db()
        async with conn.execute("SELECT 1") as cur:
            await cur.fetchone()
    except Exception as e:
        issues.append(f"DB connection dead: {e}")
        logger.error(f"[watchdog] DB connection failed: {e}")
        # Force reconnect
        from ..db import close_db
        try:
            await close_db()
        except Exception:
            pass

    # ── 2. Stale FSM state detection ────────────────────────────────────────
    try:
        from ..storage import SqliteStorage
        from ..config import FSM_DB_PATH
        import aiosqlite
        async with aiosqlite.connect(FSM_DB_PATH) as fsm_conn:
            fsm_conn.row_factory = aiosqlite.Row
            async with fsm_conn.execute(
                "SELECT chat_id, user_id, state, data FROM fsm_states WHERE state IS NOT NULL"
            ) as cur:
                stuck_rows = await cur.fetchall()
        import json
        cleared = 0
        for row in stuck_rows:
            try:
                data = json.loads(row["data"]) if row["data"] else {}
            except (json.JSONDecodeError, TypeError):
                data = {}
            # Check if state has a timestamp we can use — otherwise use a heuristic
            # States with active training data older than 2 hours are likely stale
            state_name = row["state"] or ""
            # Training and AI states are the ones most likely to get stuck
            if not any(s in state_name for s in ["Training", "AIChat", "EditDay",
                                                   "SetNotify", "SetBase",
                                                   "SetName", "SkipReason"]):
                continue
            # For training states: check if the stored date is today
            stored_date = data.get("date")
            if stored_date and stored_date != date.today().isoformat():
                # Stale — from a previous day
                async with aiosqlite.connect(FSM_DB_PATH) as fsm_w:
                    await fsm_w.execute(
                        "UPDATE fsm_states SET state=NULL, data='{}' WHERE chat_id=? AND user_id=?",
                        (row["chat_id"], row["user_id"])
                    )
                    await fsm_w.commit()
                cleared += 1
                user_tg_id = row["user_id"]
                try:
                    from ..db import get_lang, get_user
                    from ..keyboards import main_kb
                    lang = await get_lang(user_tg_id)
                    user = await get_user(user_tg_id)
                    if lang == "ru":
                        msg = "🔄 Бот перезапустил твою сессию — предыдущее действие было прервано."
                    else:
                        msg = "🔄 Bot reset your session — the previous action was interrupted."
                    kb = main_kb(lang) if user else None
                    await bot.send_message(user_tg_id, msg, reply_markup=kb)
                except Exception as e:
                    logger.debug(f"[watchdog] notify stale user {user_tg_id}: {e}")
        if cleared:
            issues.append(f"Cleared {cleared} stale FSM state(s)")
            logger.info(f"[watchdog] cleared {cleared} stale FSM states")
    except Exception as e:
        logger.warning(f"[watchdog] FSM check failed: {e}")

    # ── 3. Error rate spike detection ───────────────────────────────────────
    current_errors = monitoring.get("errors")
    current_actions = monitoring.get("actions")
    new_errors = current_errors - _watchdog_prev_errors
    new_actions = current_actions - _watchdog_prev_actions
    _watchdog_prev_errors = current_errors
    _watchdog_prev_actions = current_actions

    if new_errors >= 5:
        _watchdog_error_streak += 1
        issues.append(f"Error spike: {new_errors} errors in last 5 min (streak: {_watchdog_error_streak})")
    elif new_errors > 0 and new_actions > 0 and new_errors / new_actions > 0.5:
        _watchdog_error_streak += 1
        issues.append(f"High error rate: {new_errors}/{new_actions} actions failed (streak: {_watchdog_error_streak})")
    else:
        _watchdog_error_streak = 0

    # ── Alert admin if issues found ─────────────────────────────────────────
    if issues:
        msg = "🩺 *Watchdog alert*\n\n" + "\n".join(f"• {i}" for i in issues)
        try:
            await bot.send_message(ADMIN_TG_ID, msg, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"[watchdog] alert failed: {e}")

    logger.debug(f"[watchdog] ok — errors={new_errors} actions={new_actions}")
