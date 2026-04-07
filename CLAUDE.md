# Claude Code Instructions

## Git & GitHub

After completing each new feature or fix, always:
1. Update `CHANGELOG.md` — add an entry under today's date (`## [YYYY-MM-DD]`) with a short human-readable note describing what was added, changed, or fixed and why. Use sections `### Added`, `### Changed`, `### Fixed` as needed.
2. Stage only the relevant changed files (never `git add -A` blindly)
3. Commit with a clear message describing *why* the change was made
4. Push to `origin main`
5. Restart the bot (see Bot Management below)

Remote: https://github.com/zhanbotanigmetolla-cmyk/Zhanbota.git (branch: main)
Credentials are stored in `~/.git-credentials` — no additional login needed.

## Project

This is the **Турникмен / Pullup Bot** Telegram bot project.
Main code lives in `pullup_bot/`. See `README.md` for full overview.

## Local Environment

- **Project folder:** `C:\Users\janbo\OneDrive\Рабочий стол\TelegramBot\`
- **Main bot code:** `pullup_bot/`
- **Deploy script:** `deploy.bat`

## Server (Google Cloud Platform)

The bot runs on GCP — the old VPS in Germany is no longer used.

| Field | Value |
|---|---|
| Provider | Google Cloud Platform (Always Free tier) |
| Machine | e2-micro, 1 vCPU, 1 GB RAM, 30 GB standard disk |
| Region | us-central1-f (Iowa) |
| OS | Ubuntu 22.04 LTS |
| External IP | 34.123.71.99 |
| User | nigmetolla_zhanbota |
| SSH | `ssh nigmetolla_zhanbota@34.123.71.99` (key-based, no password) |

### Bot locations on server

- **Source code:** `/home/nigmetolla_zhanbota/pullup_bot/`
- **GitHub repo mirror:** `/home/nigmetolla_zhanbota/repo/`
- **Virtual env:** `/home/nigmetolla_zhanbota/.venv-pullup/` (Python 3.12)
- **Live databases:** `/home/nigmetolla_zhanbota/data/pullup-bot/pullups.db` and `pullups_fsm.db`
- **Secrets:** `/home/nigmetolla_zhanbota/.env.pullup_bot`
- **Systemd service:** `~/.config/systemd/user/pullup-bot.service`

### Claude Code SSH access

Claude Code connects to the server using a dedicated passphrase-free key:
- **Private key:** `~/.ssh/id_ed25519_claude`
- **Always use:** `ssh -i ~/.ssh/id_ed25519_claude nigmetolla_zhanbota@34.123.71.99`

The user's own key (`~/.ssh/id_ed25519`) has a passphrase and cannot be used non-interactively.

### Bot management commands

```bash
# Check status
ssh -i ~/.ssh/id_ed25519_claude nigmetolla_zhanbota@34.123.71.99 "systemctl --user status pullup-bot.service"

# Restart
ssh -i ~/.ssh/id_ed25519_claude nigmetolla_zhanbota@34.123.71.99 "systemctl --user restart pullup-bot.service"

# View logs
ssh -i ~/.ssh/id_ed25519_claude nigmetolla_zhanbota@34.123.71.99 "journalctl --user -u pullup-bot.service -n 50"
```

## Deploy Workflow

1. Edit code locally
2. Run `deploy.bat`, which:
   - Runs `git push origin main`
   - SSHes into the server and runs `~/deploy.sh`
3. `deploy.sh` on the server does: `git pull` → `cp -r pullup_bot ~/` → `systemctl --user restart`
