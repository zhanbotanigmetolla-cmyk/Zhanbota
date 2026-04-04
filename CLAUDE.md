# Claude Code Instructions

## Git & GitHub

After completing each new feature or fix, always:
1. Update `CHANGELOG.md` — add an entry under today's date (`## [YYYY-MM-DD]`) with a short human-readable note describing what was added, changed, or fixed and why. Use sections `### Added`, `### Changed`, `### Fixed` as needed.
2. Stage only the relevant changed files (never `git add -A` blindly)
3. Commit with a clear message describing *why* the change was made
4. Push to `origin main`
5. Restart the bot: `systemctl --user restart pullup-bot.service`

Remote: https://github.com/zhanbotanigmetolla-cmyk/Zhanbota.git
Credentials are stored in `~/.git-credentials` — no additional login needed.

## Project

This is the **Турникмен / Pullup Bot** Telegram bot project.
Main code lives in `pullup_bot/`. See `README.md` for full overview.
