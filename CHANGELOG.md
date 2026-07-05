# Changelog

All notable changes to Турникмен / Pullup Bot are documented here.

---

## [2026-07-05]

### Fixed
- **Set record no longer sticks after undo/cancel.** Logging a set that beat your per-set record used to keep the record even if you undid the set or cancelled the whole workout. Now the record rolls back to its correct value in both cases.
- **Freeze tokens are no longer charged for backfilled days.** Streak gap-bridging counted a day as "missed" even when a workout was later added for it via «Редактировать день»; days with logged reps now bridge for free, like rest days.
- **Deleted accounts clean up greeting links.** All deletion paths (self-delete, admin delete, inactivity cleanup) now also remove `welcome_greetings` rows, so a re-registered user can be greeted again.
- **Admin error alerts respect Telegram's 4096-char limit** — long user messages inside the alert used to make the alert itself fail to send.
- **Bug-report approve/reject buttons work on reports containing `<`** — the status edit was silently failing on unescaped HTML.

### Added
- **Squats** 🦵 as the fourth exercise — same treatment as the others: own норма (set up on first pick, max × 3), own RPE adjustments and weekly progression, own records. XP weight: 0.25 per squat (ladder: pull-up 1 · dip 0.75 · push-up 0.5 · squat 0.25). Guide, About, AI knowledge base and README updated.

## [2026-07-04]

### Added
- **Three exercises: pull-ups, push-ups, dips.** The Training button now opens a picker («Что тренируем сегодня?») with per-exercise targets shown right on the buttons. One shared 7-day calendar: the day type (Средний/Лёгкий/Тяжёлый/Отдых/Плотность) applies to whichever exercise you pick; training at least one exercise per day keeps the streak and advances the cycle once.
- Each exercise has its own daily норма, its own RPE-based adjustments, weekly +5% progression, and its own records (best day / best set). Push-ups and dips are set up lazily — the bot asks for your one-set max the first time you pick them (base = max × 3).
- XP weights per rep: pull-up 1 · dip 0.75 · push-up 0.5 (+50/streak day unchanged). Existing XP untouched.
- Weekly leaderboard and 👑 Кочка недели now rank by **weekly XP across all exercises** instead of pull-up count.
- Stats, History, Analytics, weekly summaries, morning reminders, friends list, AI coach context, and CSV export all show per-exercise data.

### Changed
- Database: `workouts` table rebuilt with an `exercise` column (`UNIQUE(user_id, date, exercise)`); legacy rows migrated as pull-ups, rest days as day-level rest markers. New per-exercise base/record columns on `users`.
- Guide («Как начать») and «О боте» rewritten to match actual behavior: correct wave percentages (Лёгкий ~50–60%, Тяжёлый 115%), freeze tokens described as automatic, three programs mentioned, new XP rules documented.

### Removed
- Extra-activity feature (бег/зал plan reduction) and the notes-adding step in «Редактировать день» — removed entirely per owner decision; old saved notes still display in history. Break reduction after 3+/7+ days off stays.
- A dozen dead i18n strings and orphaned flows (interactive freeze prompt, old registration questions, unused chart helper).

## [2026-07-03]

### Fixed
- Second audit pass — remaining issues fixed:
  - Editing a stored rest day to add reps kept the row as `planned=0 / Отдых`, so history showed "😴 50/0" and the session never counted toward progression (same class of bug as the rest-day-override fix) — now converted to a training day.
  - Finishing a training session overwrote `extra_activity` / `extra_minutes` / `notes` with empty values (the flow no longer collects them), erasing data added via "Edit Day". Those columns are no longer touched by the training save.
  - Admin exemption unified: ban/mute and maintenance middlewares checked only the admin Telegram ID while the admin panel also accepted the admin username — both now use one shared `is_admin_user()` check.
  - Maintenance mode now also blocks inline-button (callback) presses, not just messages.
  - Morning reminders moved from a 1-minute interval to a cron tick with a 30s grace period — a slow tick can no longer silently skip a minute (and its reminders).
  - Per-user duplicate-message locks no longer evict a lock that is currently held.

## [2026-07-02]

### Fixed
- Full project audit. Bugs found and fixed:
  - Deleting today's workout via "Edit Day" corrupted the program cycle position: `program_day` was wrapped with `% 7` even though it's a monotonic counter (e.g. day 22 → 0 instead of 21), silently shifting the whole future schedule.
  - "Next 7 days" schedule in Stats (and the AI's view of tomorrow) was off by one whenever a workout row existed but the day wasn't finished yet — the offset now keys off `last_workout == today` (the moment `program_day` actually advances) instead of the row's existence.
  - Training on a rest day ("Train anyway") saved the workout against a `planned=0 / Отдых` row, so history showed things like "😴 50/0" and the session never counted toward RPE/weekly progression. The override is now persisted as a real training day (cancelling still restores the rest row).
  - The 23:55 auto-rest job could overwrite today's workout row for a user mid rest-day-override session; it now skips users who already have real activity recorded today.
  - Base-change validation message claimed "1 to 2000" while the code accepts 1–500.
  - Guide and AI system prompt described outdated RPE progression rules (≤6.5 for +3%, no −2% zone) — aligned with the actual code (≤5.5 / 5.5–7.0 / 7.0–8.5 −2% / ≥8.5 −5%).
  - Admin panel: user names and search queries are now HTML-escaped — a user named e.g. `<b>` made the profile view silently fail to render.
  - Gemini fallback per-user cooldown dict grew without bound — expired entries are now pruned.
  - `.gitignore` contained corrupted UTF-16 garbage lines, so `bot.log` and DB backups weren't actually ignored — rewritten clean.
  - Test suite repaired: 8 tests were stale (old rank names, old XP thresholds, missing `program_type` field) — updated to match current config; added coverage for beginner/unknown program types. 80/80 passing.

## [2026-07-01]

### Fixed
- Skip reason (overtraining/illness/etc.) now writes a rest-day row to the workouts table, so stats shows 😴 instead of ❌ and the training screen no longer says "didn't complete plan" after a skip.

## [2026-06-25]

### Changed
- Post-training flow simplified: removed the extra-activity (cardio/gym) question and notes step. Only RPE rating remains — tap a number and you're done.
- Streaks are now protected silently: if you miss a training day, a freeze token is auto-spent without any prompt. No more streak resets that happen without the user knowing.
- Rest days on the "Keep resting" screen no longer ask about freeze tokens — the system handles it automatically on the next training day.

### Fixed
- Streak bug: if a training day was skipped and the next day was a scheduled rest day, the streak would silently reset the day after. Now `update_streak` checks rest-day records in the workout history and only spends tokens for genuinely missed training days.
- Restored streaks for 3 users whose streaks were incorrectly reset by the rest-day bug.

### Added
- Stats screen now shows longest streak ever: "🔥 Streak: X days (best: Y)" alongside current streak.

## [2026-05-08]

### Changed
- Training session rep buttons now show 10 consecutive numbers (e.g. 8–17) instead of spaced-out values. Range is still anchored to the user's per-set target so relevant counts are always visible.

## [2026-05-07]

### Added
- XP decay system: after 7 days of inactivity, XP decreases daily (0.5%→1%→1.5% per day as absence grows). Floor: can lose at most one rank per absence. Notifies user on first decay day and on rank loss.

### Changed
- Slowed down base progression: weekly +5% bump now blocked if avg RPE of last 5 workouts is ≥ 7.0 (high effort = no auto-advance)
- Lowered RPE threshold for base growth from ≤ 6.5 to ≤ 5.5 — base now only grows via RPE path when training feels easy
- Filled the RPE dead zone: added −2% base zone for avg RPE 7.0–8.4 (previously no change at all in that wide range)

## [2026-05-04]

### Fixed
- Fixed `IntegrityError: UNIQUE constraint failed: workouts.user_id, workouts.date` crash when tapping Training — replaced the SELECT-then-INSERT pattern with an atomic `INSERT … ON CONFLICT DO UPDATE` to eliminate the race condition.
- Removed dead `weight_kg` field: it was never collected during registration, always defaulted to 80, and was only feeding a wrong value into the AI context. Cleaned up the DB schema, states, i18n strings, AI prompt, scheduler, and tests. Added DB migration (index 24) to drop the column from existing databases.
- Removed stale body-weight instruction from `ai_system_prompt` in both locales — the prompt no longer supplies weight data, so telling the model to "consider body weight" was misleading.

## [2026-05-02]

### Added
- **Extended History (monthly view):** History screen now has a "📅 By Month" toggle button. Tapping it switches from the weekly drill-down view to a 12-month summary showing total reps, completion %, and training days per month. A "By Week" button switches back.
- **Custom Training Program:** Users can now choose between three preset programs from Settings → 🔧 Program: Standard (5x/week, the original wave), Beginner (3x/week with more rest), and Advanced (6x/week with an extra training day). The choice is persisted and affects both the daily training target and the 7-day forward schedule in Stats.
- **Data Export (CSV):** Settings → 📤 Export sends a CSV file of all workout history (date, day type, planned, completed, sets, RPE, extra activity, notes, completion %). UTF-8 BOM encoding for Excel compatibility.
- **Advanced Analytics:** Stats screen now shows a "📈 Подробно / Analytics" inline button. Tapping it reveals: monthly volume bar chart (last 6 months), completion % by day type, personal records (best day, best set, max streak ever), and most trained day of the week.
- `max_streak` column added to users table — tracks the all-time highest streak ever reached. Updated automatically after each workout.
- Per-set personal record (PR) tracking. A new `set_record` column stores the user's all-time best single-set rep count. When a user enters a set that beats their record, they immediately receive a "New personal record! Congrats! 🎉" message mid-session. If a session PR was set, the workout completion notification sent to other users also includes a trophy line showing the record count.

---

## [2026-04-27]

### Fixed
- Rest days no longer break the streak when the user doesn't open the bot. A nightly job (`auto_acknowledge_rest_days`, runs at 23:55) now automatically advances `program_day` and sets `last_workout` for any user whose scheduled rest day passed while they were offline — mirroring the "Keep resting" button press.
- Manually restored Zhanbota102's streak to 25 (consecutive active days since Apr 2, counting skipped rest days).
- AI system prompt (`_SYSTEM_TEMPLATE`) had stale thresholds — ≥90% completion and RPE ≤4.5. Updated to match live code: ≥80% completion and RPE ≤6.5 for the +3% RPE-easy bump.
- Admin restart no longer runs `pgrep -f "python.*pullup_bot"` which could kill unrelated Python processes; `os.execv` replaces the current process in-place, so the sibling-kill block was unnecessary.
- `scheduler.py` auto-advance path now calls `_check_weekly_progression` when `new_pd % 7 == 0`, matching the `training.py` logic. Previously a cycle boundary crossed via morning-reminder auto-advance would silently skip the +5% base bump.
- Removed duplicate migrations 15 & 16 (redundant `ALTER TABLE ai_usage_log ADD COLUMN` that migration 14 already covers); replaced with no-ops to preserve migration version numbering.
- Fixed `train_day` i18n keys — they contained a raw Python ternary that `str.format()` would never evaluate; changed to `{icon}` placeholder so future callers can pass the icon explicitly.

### Changed
- Morning reminders sent before 08:00 are now also silent (disable_notification=True), matching the existing 22:00+ quiet-hours rule.
- README: replaced obsolete Groq/Llama stack reference with Google Gemini API.
- Removed unused `GEMINI_MODEL` constant from `config.py`.
- Added docstrings to all functions across the codebase (handlers, services, core modules) to bring docstring coverage from ~50% to >80% and satisfy the CodeRabbit pre-merge quality check.

## [2026-04-25]

### Added
- Added "🔑 Key Principle" tip to the guide's "More →" page (both RU and EN): even logging 10 pullups on a busy day matters — consistency over perfection, long-term results over short-term completion.
- Morning reminder now includes a "📈 Your base increased to X" line if the base was auto-raised since the last reminder. The flag is cleared after the notification is sent so it only appears once.

### Changed
- Weekly cycle progression threshold lowered from ≥90% to ≥80% average completion across last 5 sessions — more achievable for real-world training.
- RPE increase threshold raised from ≤4.5 to ≤6.5 (with 100% completion required) — aligned with sports science: progressive overload is appropriate at moderate effort, not just when workouts feel trivial.

### Fixed
- Weekly progression was silently skipped when the "auto-advance" path triggered (rest day with days_off ≥ 2). The auto-advance increments `program_day` but had no `new_pd % 7 == 0` check, so any 7-day cycle that ended on an unacknowledged rest day never bumped the base. Added the missing progression check there. Applied retroactive progression corrections for impacted accounts.

## [2026-04-23]

### Added
- Guide "More →" step now explains the full training logic in plain language: how the base increases/decreases, what the 7-day cycle means, whether you need 7 consecutive days, how extra activity reduces tomorrow's plan, and how RPE affects the base over time.

### Fixed
- Leaderboard and Friends list no longer show users who only acknowledged rest days — only users with at least 1 actual pullup in the last 7 days are included.

## [2026-04-22]

### Fixed
- Turnikmen AI now correctly reports tomorrow's day type.
- Turnikmen AI now receives today's calendar date in its context, so it can detect gaps between the last logged workout and today and adjust its response accordingly. Previously, after today's workout was logged (advancing `program_day`), the AI computed "tomorrow" as one step too far in the wave cycle — showing the day after tomorrow instead. The fix mirrors the `pd_offset` logic already used by the Stats button.

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
