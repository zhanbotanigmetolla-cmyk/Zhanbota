# Changelog

All notable changes to Турникмен / Pullup Bot are documented here.

---

## [2026-04-06]

### Changed
- Workout completion notification format: now shows `🎯 Цель: X | Выполнено: Y | Подходов: Z` instead of the old `emoji done/planned за sets подходов`

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
