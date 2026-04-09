# Changelog

All notable changes to Турникмен / Pullup Bot are documented here.

---

## [2026-04-09]

### Changed
- "About bot" is now a 3-page flow with ← Back and Next → navigation, mirroring the Guide structure. Page 1: bot overview + wave cycle. Page 2: RPE, freeze tokens, AI coach, disclaimer. Page 3: full XP/level table with the "road to God Mode" estimate (~200+ days, ~14,500 pullups at 70/day with streak).
- Guide Step 1 registration text updated to remove the "program day" step (removed from registration in a prior release).

### Changed
- Stats screen redesigned for clarity: level now shows current→next with XP progress as `n/total XP`; streak/freezes/record merged into one line; dates shortened to dd.mm; "Total" now reads "За всё время: N подтягиваний"; chart removed (redundant with 7-day log); schedule dates shortened to dd.mm.
- Registration: removed example hints from weight and base pullups prompts — users now enter values without suggested numbers.
- Registration: removed the "program day" step entirely. New users always start at day 0. The question was confusing and irrelevant — load is driven by the user's own base pullup count, not by which day of the cycle they claim to be on.

---

## [2026-04-09]

### Fixed
- `start_training` now detects when `last_workout == today` but no workout row exists (row was deleted by a previous cancel). It restores the rest day row and shows the rest/train prompt instead of jumping straight to the next program day's training load.
- Canceling a rest-day override training now restores the rest day row (`planned=0 / Отдых`) instead of deleting it. Previously, canceling wiped the row, and the next training press used the already-advanced `program_day` to compute a training load — silently skipping the rest day prompt forever. Fix: `_begin_training` now accepts a `was_rest_override` flag stored in FSM state; `_cleanup_cancelled_workout` checks it and upserts the `Отдых` row back on cancel.

---

### Fixed
- Friends list: rest day now correctly shows `0/0` instead of tomorrow's training load. Root cause: when a rest day is acknowledged, `program_day` is incremented before the display; if no workout row exists, the fallback `planned_for_day` was reading the already-advanced day and showing the next day's plan. Fix: when no workout row exists but `last_workout == today`, show `0/0`.
- Streak race condition: if a training session was started on day N but saved after server midnight (day N+1), `update_streak` stamped `last_workout = N+1`, causing day N+1's real session to skip streak increment. Fixed by passing the session's own date to `update_streak` instead of using `date.today()`. Manually corrected streaks for all affected users: Zhanbota102 (→5), fabulousayan (→4), kamikadze24 (→0), Maffettone_Burger (→0), Bakhyt_Adilet (→0), Kris (→0).
- Progression check (+5% base) was skipped when the 7th program day fell on a rest day. The check now also runs in all three rest-day `program_day` advance paths (rest day acknowledgement, freeze token used, freeze token declined). Also manually applied the missed bump for Zhanbota102 (70 → 73).

---

## [2026-04-08]

### Added
- **Кочка недели** — weekly champion system. Every Monday at 08:00, the user with the most pullups in the past week is crowned "Кочка недели" (Beast of the Week). All active users receive an announcement with the winner's name and a top-3 leaderboard. The champion's stats screen shows a `👑 Кочка недели` badge, and the 🏆 Рейтинг leaderboard shows 👑 next to the current holder until the next Monday.
- "🏃+🏋️ Кардио+Зал" / "🏃+🏋️ Cardio+Gym" option in the extra-activity screen after training and in Edit Day. Selecting it stores `бег+зал` and applies a combined fatigue reduction (higher cap than either alone) to tomorrow's planned pullups.

### Fixed
- Edit Day: back button at every step now returns to the previous step instead of jumping to the main menu. `pick_date` → settings menu; `pick_done` → re-ask date; `pick_rpe` → re-ask pullup count; `confirm_extras` / `activity` / `act_mins` / `notes` → each returns to the step before it. Root cause: all EditDay states were in the generic catch-all back handler which fired before the specific per-step handlers.
- Edit Day: entering 0 to delete today's workout now also reverts `program_day` (decrements by 1) and restores `last_workout` to the most recent remaining workout. Previously, deleting today's record left `program_day` advanced, so pressing Train afterward showed the wrong day type (e.g. Плотность instead of the correct rest day).

---

## [2026-04-07]

### Added
- **Change name** button in user Settings — users can now update their display name at any time.
- **Admin: change user name** — new "✏️ Изменить имя" button in the admin user profile panel.
- **Back buttons throughout training flow** — user can now navigate back from: finish confirmation (RPE screen) → resume training; RPE → activity selection; activity selection → RPE; duration input → activity selection; notes → activity selection.
- **Edit Day: enter 0 to delete** — if a user enters 0 as completed reps in Edit Day, the workout record is deleted and XP is reversed (no RPE prompt shown).
- **Edit Day: activity & notes flow** — after entering RPE, user is asked whether to add extra activity and notes. If yes, the same gym/cardio → duration → notes flow as after training appears, with back navigation at every step.

### Fixed
- Rest days now appear in the Stats history. The display infers scheduled rest days from surrounding workout records using the WAVE cycle, so days with no DB record but a rest-day wave position show as 😴 Отдых. Additionally, pressing "Train" on a rest day now immediately creates the DB record so it always appears in history going forward.
- Admin panel user list now shows the user's display name (first_name) instead of their Telegram username (@handle).
- Training button no longer shows "do N pullups" after overriding a rest day — `_begin_training` no longer restores `day_type` or zero `planned` from the DB record, so a rest-day override keeps the correct values without permanently changing the stored day type.
- `program_day` was stuck on Heavy (index 2) after migration to GCP — the DB was copied while a workout was still in progress on the old server, so the post-workout increment never landed on the new server. Fixed with a one-time SQL update on the server (`program_day + 1`). No code change needed; the logic is correct.

### Changed
- Updated `CLAUDE.md` with full GCP server details (e2-micro, us-central1-f, IP, paths, SSH commands, deploy workflow). Old Ubuntu Desktop VPS reference removed.

---

## [2026-04-06]

### Added
- "⏳ Сохраняю..." indicator before workout save — auto-deleted once save completes, preventing users from tapping again while waiting

### Fixed
- Race condition in RPE handler: when two messages arrived in rapid succession (e.g. "🥵 7" then "7"), both were dispatched while state was still `Training.rpe`, causing the "extra activity?" prompt to appear twice. Fixed with a per-user asyncio lock that drops duplicate concurrent messages.

### Changed
- Workout completion notification format: now shows `🎯 Цель: X | Выполнено: Y | Подходов: Z` instead of the old `emoji done/planned за sets подходов`
- Simplified post-training extra activity options from 4 choices to 3: Running/Cardio, Gym, Skip
- "Как начать" guide is now a step-by-step flow (Intro → Шаг 1–4 → Дополнительно) instead of one long message

---

## [2026-04-04]

### Fixed
- Bot was crashing with TelegramConflictError because CLAUDE.md instructed restarting via `nohup` while a systemd service was already managing the bot — fixed CLAUDE.md to use `systemctl --user restart` instead
- Added a startup guard in `__main__.py` that blocks direct `python -m pullup_bot` launches outside of systemd, printing a clear error — prevents accidental double-instance conflicts in the future

---

## [2026-04-03]

### Added
- Freeze token earning system: users now earn +1 token automatically for every 7-day streak milestone, on each level-up, and when breaking a personal record (capped at 5 tokens max). Earn notification shown inline in the workout summary.
- Updated О боте and Как начать / About and Getting Started texts to explain all three ways to earn tokens


### Changed
- Welcome screen and bug report prompt now invite users to share ideas for improvement, not just report bugs — "Сообщить о баге" button now clearly covers both bugs and feature suggestions

### Added
- Admin panel accessible from Settings (🛡 Панель администратора, visible only to admin): user management (ban/unban, mute, reset streak/XP, give freeze tokens, delete accounts), bot controls (restart, maintenance mode toggle, broadcast to all users), bug report management, live stats (uptime, active users, total workouts), and security event log for suspicious activity

### Fixed
- Weight input now accepts formats like "75 kg", "75kg", "75 кг", "75кг" — the "kg"/"кг" suffix is stripped before parsing, so users no longer get an error for natural input

## [2026-04-02]

### Added
- New "📖 Как начать" / "📖 Getting Started" button on the landing screen with a step-by-step beginner guide covering registration, daily plan, training flow, RPE, streak, stats, and AI coach (Russian + English)
- "О боте" now includes a friendly reminder that the bot works best alongside good sleep, nutrition, and recovery — not as a substitute for them
- `CLAUDE.md` with project instructions for Claude Code (auto-push and changelog rules)

### Changed
- Restored original "О боте" / "About" description (feature overview) — beginner guide moved to dedicated "Как начать" button

---

## [2026-03-29]

### Added
- Initial project snapshot — full bot codebase with training, stats, history, friends, AI coach, leaderboard, settings, admin, and scheduler
- Project `README.md` with feature overview, tech stack, and deploy instructions
- `.gitattributes` for consistent LF line endings
- `.gitignore` entries for `.env` files and runtime SQLite database files

### Fixed
- Daily plan stability — same-day plan no longer shifts when the bot is restarted mid-day
