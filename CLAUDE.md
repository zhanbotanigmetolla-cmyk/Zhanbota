# Claude Code Instructions

## Git & GitHub

After completing each new feature or fix, always:
1. Update `CHANGELOG.md` — add an entry under today's date (`## [YYYY-MM-DD]`) with a short human-readable note describing what was added, changed, or fixed and why. Use sections `### Added`, `### Changed`, `### Fixed` as needed.
2. Stage only the relevant changed files (never `git add -A` blindly)
3. Commit with a clear message describing *why* the change was made
4. Push to a **feature branch** and open a PR — never push directly to `main`
5. Deploy the bot **from the branch** (not main) so changes are live while CodeRabbit reviews
6. After the user approves, merge the PR to `main`

### Branch & PR workflow

```bash
# 1. Create and switch to a new branch
git checkout -b codex/fix-short-description

# 2. Commit changes as usual, then push the branch
git push -u origin codex/fix-short-description

# 3. Open a PR (gh CLI)
gh pr create --title "..." --body "..." 

# 4. Deploy from the branch
./deploy.bat

# 5. After approval, merge on GitHub (user clicks Merge) or:
gh pr merge --squash --delete-branch
git checkout main && git pull
```

**Branch naming:** use `codex/` for new agent branches, with a short feature/fix description.
**gh CLI path (Windows Git Bash):** `/c/Program Files/GitHub CLI/gh.exe`

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
| External IP | 35.226.20.162 (verified 2026-09-23) |
| User | nigmetolla_zhanbota |
| SSH | `ssh nigmetolla_zhanbota@35.226.20.162` (key-based, no password) |

⚠️ **The external IP is ephemeral** — it changes when the VM stops/restarts (34.123.71.99 → 35.226.20.162 on 2026-07-07). If SSH *times out*, don't assume the bot is down: the VM likely got a new IP. Check GCP Console → Compute Engine → VM instances (`instance-20260406-162354`, us-central1-f) and update the IP here.

### Bot locations on server

- **Active source after release deployment:** `/home/nigmetolla_zhanbota/pullup-current/pullup_bot/`
- **Release directories:** `/home/nigmetolla_zhanbota/pullup-releases/` (each contains its own `.venv` and SQLite backups)
- **GitHub repo mirror:** `/home/nigmetolla_zhanbota/repo/`
- **Active virtual env:** `/home/nigmetolla_zhanbota/pullup-current/.venv/` (Python 3.12); the original `.venv-pullup/` remains available to create new release environments
- **Live databases:** `/home/nigmetolla_zhanbota/data/pullup-bot/pullups.db` and `pullups_fsm.db`
- **Secrets:** `/home/nigmetolla_zhanbota/.env.pullup_bot`
- **Systemd service:** `~/.config/systemd/user/pullup-bot.service`

### Claude Code SSH access

Claude Code connects to the server using a dedicated passphrase-free key:
- **Private key:** `~/.ssh/id_ed25519_claude`
- **Always use:** `ssh -i ~/.ssh/id_ed25519_claude nigmetolla_zhanbota@35.226.20.162`

The user's own key (`~/.ssh/id_ed25519`) has a passphrase and cannot be used non-interactively.

### Bot management commands

```bash
# Check status
ssh -i ~/.ssh/id_ed25519_claude nigmetolla_zhanbota@35.226.20.162 "systemctl --user status pullup-bot.service"

# Restart
ssh -i ~/.ssh/id_ed25519_claude nigmetolla_zhanbota@35.226.20.162 "systemctl --user restart pullup-bot.service"

# View logs
ssh -i ~/.ssh/id_ed25519_claude nigmetolla_zhanbota@35.226.20.162 "journalctl --user -u pullup-bot.service -n 50"
```

## Deploy Workflow

1. Edit code, add the changelog entry, and run `python -m pytest pullup_bot/tests -q` in the locked environment.
2. Commit relevant files to a feature branch, push it, and open a PR against the appropriate base (the current feature branch for a stacked PR).
3. Run `deploy.bat` (or `deploy.ps1` with explicit `-Server`/`-SshKey`). It refuses main/master and uncommitted tracked changes, pushes the branch, and deploys its exact commit.
4. `scripts/deploy_server.sh` builds a release and venv, runs tests, validates configuration, backs up both SQLite databases with the bot stopped, switches the systemd release, and checks Telegram startup. On failure it restores the previous service configuration and retains database snapshots for manual recovery.
5. The server's `~/deploy.sh` is a wrapper requiring two arguments: branch and full commit SHA. It never pulls main into another branch. Merge only after user approval.
