# Changelog

All notable changes to Турникмен / Pullup Bot are documented here.

---

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
