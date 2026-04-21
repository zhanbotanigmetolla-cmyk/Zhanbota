# Changelog

All notable changes to Турникмен / Pullup Bot are documented here.

---

## [2026-04-21]

### Changed
- Removed all "beta testing" labels from welcome screen and About page — bot is now considered GA
- Added contact info (@zhanbota102) to the welcome screen for both RU and EN
- Added new funny waiting phrase about the uncertainty principle to Gemini loading messages
- Added account deletion note to About page 3 (Settings → Delete account), both RU and EN

### Fixed
- Leaderboard (rating tab) now filters out users inactive for 7+ days, matching the friends list behaviour. Users inactive for 30+ days are already deleted from the database by the auto-cleanup scheduler.

---

## [2026-04-19]

### Fixed
- Stale FSM state reset notification now includes the main menu keyboard so users can continue without needing to type /start (#64)
- Removed all references to a "secret code" from the guide, delete account warning, and delete account confirmation — no secret code is required to register anymore (#65)

## [2026-04-15]

### Fixed
- Training button numbers now start at a minimum of 4 (was 1) — users with smaller bases no longer see unrealistically low options like 1, 2, 3.

### Changed
- Training menu quick-rep buttons now show 10 numbers in 2 rows of 5: first row is 5 consecutive numbers anchored to last session's reps, second row continues with gradually increasing gaps (e.g. 5 6 7 8 9 | 10 11 14 17 20).

## [2026-04-14]

### Changed
- Renamed settings button "Уведомления о тренировках" → "Уведомления от друзей" (and EN: "Workout Notifications" → "Friend Notifications") for clarity.

### Fixed
- **Morning notification incorrectly saying "rest day" when it's actually a training day**: the scheduler now applies the same auto-advance logic as the training handler — if the cycle shows a rest day but the user hasn't trained for 2+ days already, it advances to the next training day before sending the notification.
- **Stats history wrongly showing consecutive unrecorded days as "Отдых"**: when two or more days in a row had no workout record, the wave-inference logic kept reusing the same cycle slot (the one immediately after the last recorded workout). Each missing day now gets its correct cycle slot by advancing the index by the number of days since the last recorded workout.

## [2026-04-13] (3)

### Fixed
- **Notifications firing at wrong time**: scheduler was comparing stored `notify_time` against server UTC clock, but users enter their local time (UTC+5 Kazakhstan). Notifications always arrived 5 hours late. Scheduler now uses UTC+5 (configurable via `TZ_OFFSET_HOURS` env var).

## [2026-04-13] (2)

### Changed
- **New user onboarding**: instead of asking for weight + daily base, now asks only "max pullups in one set". Base is derived automatically as `max × 3`. Existing users are unaffected.
- **Settings**: removed "Change Weight" button — weight is no longer collected or shown. Fixed broken `welcome_user` i18n test and stale `weight=` kwargs in settings display calls.

## [2026-04-13]

### Fixed
- **Forecast off-by-one**: "Next 7 days" schedule was showing one day ahead of the correct plan. After completing a workout `program_day` advances to the next slot, so the forecast now applies a `-1` offset when today's session is already recorded.
- **Double rest day bug**: if a user skipped a rest day without opening the bot, the next day still showed "Rest" because `program_day` never advanced. Now, if today is a scheduled rest day and the user hasn't trained since their last workout (days_off ≥ 2), the bot silently advances `program_day` to the next training day.

## [2026-04-11] (2)

### Fixed
- **Display name fallback**: users with a name shorter than 2 characters (e.g. ".") now show their username instead — fixes `\.` rendering in friends list

### Changed
- **Friends list header**: now explains that only users active in the last 7 days are shown

---

## [2026-04-11]

### Changed
- **Open registration**: removed secret code requirement — anyone can now register freely
- **Friends list filter**: only users who logged at least one workout in the last 7 days appear in the friends list; leaderboard still shows everyone

---

## [2026-04-10] (7)

### Fixed
- **Gemini 503 fallback**: when a model tier returns 503 UNAVAILABLE (overloaded), the bot now falls through to the next tier instead of immediately returning "AI unavailable"
- **AI unavailable message**: now tells users to retry — servers are often overloaded temporarily and it usually works on the next attempt

---

## [2026-04-10] (6)

### Added
- **Self-diagnosis watchdog**: runs every 5 min — checks DB connection liveness (auto-reconnect if dead), detects stale FSM states from previous days (auto-clears and notifies user), monitors error rate spikes (alerts admin immediately if 5+ errors/5min or >50% failure rate)

### Changed
- **AI waiting messages**: all phrases now end with "..." for consistency; fixed coffee message text

---

## [2026-04-10] (5)

### Changed
- **Workout notifications now opt-in**: friend workout finish notifications are OFF by default; users can toggle them in Settings. Stops spam as user count grows.
- **Friends list & leaderboard optimized**: replaced N+1 per-user DB queries with single batch queries (1 query instead of N)
- **User locks capped at 200**: prevents unbounded memory growth from per-user asyncio.Lock objects

### Fixed
- **Orphaned data on account delete**: self-delete (Settings) now also cleans `ai_usage_log` and `pokes` tables; scheduler auto-cleanup and admin delete also clean `pokes`

---

## [2026-04-10] (4)

### Fixed
- **Race condition in training**: concurrent rapid set inputs no longer corrupt the sets list — added per-user lock to `custom_set_input` handler
- **Atomic user deletion**: all related table deletes now wrapped in a single transaction; crash mid-delete no longer leaves orphaned data; also cleans `ai_usage_log`
- **Mute enforcement**: muted users are now actually blocked from sending messages/callbacks in middleware (previously only ban was enforced)
- **Deleted users re-registration**: permanently banned users can no longer re-register — `banned_ids` check added at secret code acceptance
- **N+1 weekly champion query**: replaced per-user loop with a single `GROUP BY` query
- **Weekly champion crown race**: atomic single-statement UPDATE instead of two sequential updates
- **40+ bare `except: pass`** replaced with specific exception types or logging (`logger.warning`/`logger.debug`) across db.py, main.py, admin.py, training.py, start.py, friends.py, ai.py, gemini.py

### Changed
- Added DB indexes on `ai_usage_log.date` and `bug_reports.status` for query performance (migration 17–18)
- Removed unused `GROQ_KEY` from config
- Moved `import re` from inline function to module-level in start.py

---

## [2026-04-10] (3)

### Changed
- AI waiting messages: two-phase system — Phase 1 shows original "Анализирую..." / "Thinking..." for 3 seconds; Phase 2 cycles 30 funny phrases (RU+EN) in smart-random order (full pool shown before reshuffle, no early repeats), switching every 6 seconds
- Auto-bug-fix cron: reduced from hourly to every 3 hours (8 checks/day vs 24) to save session token usage

## [2026-04-10] (2)

### Added
- Admin panel: "📝 Диалоги пользователей" page accessible from AI stats — shows full question and Gemini answer per user with pagination (5 per page)
- `ai_usage_log` now stores `question` and `answer` text for every AI exchange

## [2026-04-10]

### Added
- Triple-tier Gemini API key rotation: up to 4 keys × 3 models (gemini-3-flash-preview → gemini-2.5-flash → gemini-2.5-flash-lite) with automatic fallback on daily quota exhaustion
- AI usage tracking in DB (`ai_usage_log` table): per-user, per-model, per-day stats
- Admin panel: new "🤖 AI Использование" button shows today's request count, per-user and per-model breakdown, key exhaustion status
- AI limit pre-check: entering Turnikmen AI section immediately shows limit message if all quotas are exhausted, before trying to send a message
- Smart fallback: bot now responds to random free-form text via Gemini (1 call/60s per user) instead of staying silent — suggests bug report button if the message looks like a report
- Bug report approval workflow: non-admin bug reports arrive with Accept/Reject inline buttons; admin's own reports are auto-approved
- Silent notifications: reminders set at 22:00 or later are sent with `disable_notification=True`

### Changed
- History: each day now shown in monospace (`code`) style with blank line between days for better readability
- "About AI" section text updated: explains that AI analyses all workouts, sets, RPE, rest and missed days to give personalised advice
- Gemini key manager centralised in `services/gemini.py`; old single-client setup removed from `handlers/ai.py`

## [2026-04-09]

### Changed
- History: removed emojis and monospace backticks — now plain text rows.
- AI system prompt: workout dates now shown as DD.MM instead of MM-DD (was slicing YYYY-MM-DD incorrectly).
- Friends poke buttons: now show only the user's name (no username or #id). Target is resolved via a `poke_map` stored in FSM state when the page is rendered, so the lookup is always exact even if two users share a display name.
- Friends list now paginates at 8 users per page. "← Пред." / "След. →" buttons appear in the keyboard when there are more pages; the header shows "Стр. X / Y". Poke buttons only appear for users on the current page.
- Entrance screen: added "Бот полностью бесплатный, навсегда" after the motivation line (both welcome and welcome_intro variants).

### Fixed
- Admin panel "✖ Закрыть панель" inline button cleared FSM state but never sent `main_kb`, so the next ◀️ Назад press had state=None and triggered `entrance_handler`, showing the landing screen instead of main menu. Fix: after closing the panel, a new message with `main_kb` is sent.

### Fixed
- Turnikmen AI "Today" data was wrong after acknowledging a rest day: `program_day` is advanced at rest-day acknowledgement, so `planned_for_day` would read the next day (e.g. Medium) as "today". Fix: `_user_data_block` now checks the actual DB workout row for today first; only falls back to `planned_for_day` if no row exists yet.

### Changed
- Turnikmen AI rate limit handling: daily quota exhaustion (1 500 req/day) shows "бот использовал дневной лимит, попробуй завтра"; per-minute throttle (15 req/min) shows "подожди минуту и попробуй снова". Both messages are localised RU/EN.
- Welcome/landing screen now mentions Turnikmen AI for both new and returning users.
- Guide intro screen now mentions Turnikmen AI.
- Privacy policy updated: Section 4 replaced with a full Turnikmen AI / Google Gemini data disclosure (what is sent, why, link to Google Privacy Policy).
- README updated with a dedicated Turnikmen AI section covering model, free-tier limits, and system prompt design.

### Changed (prior)
- AI coach replaced: Groq/Llama dropped in favour of Google Gemini 3 Flash (free tier, `gemini-3-flash-preview`). SDK switched from deprecated `google-generativeai` to `google-genai`. Button renamed to "🤖 Турникмен AI" / "🤖 Turnikmen AI". Now a full multi-turn chat — user can ask anything across multiple messages; AI retains context for up to 10 exchanges. System prompt includes complete bot knowledge base + user's current rank, streak, base, last 14 workouts, and tomorrow's plan so answers are always personalised and accurate.

### Replaced the 10-level XP system (Новичок → God Mode) with 18 CS:GO-style ranks: Silver I through The Global Elite. XP cap raised from 25,000 to 70,000. Thresholds: Silver I (0) → Silver Elite Master (4,000) → Gold Nova Master (13,500) → DMG (36,000) → Global Elite (70,000). DB `level` field auto-corrects on next workout; one-time SQL migration applied for all existing users.
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
