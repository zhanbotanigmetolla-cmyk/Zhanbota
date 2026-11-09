#!/bin/bash
# Deploy fitness-mcp on the VM.
#
# Deliberately SEPARATE from ~/deploy.sh, which restarts pullup-bot.service.
# This script must never touch the bot: not its unit, not its venv, not its
# database in write mode. Extending the bot's deploy script would couple an
# MCP release to a bot restart, which is exactly what we do not want.
#
# Usage:  ./deploy.sh [branch]     (default: main)

set -euo pipefail

# Its own checkout, deliberately NOT ~/repo. The bot's ~/deploy.sh runs
# `git pull origin main` in ~/repo, so leaving that clone parked on a feature
# branch would turn the next bot deploy into a surprise merge.
REPO_URL="https://github.com/zhanbotanigmetolla-cmyk/Zhanbota.git"
REPO="$HOME/fitness-mcp-src"
VENV="$HOME/.venv-fitness-mcp"
BRANCH="${1:-main}"
DATA_DIR="$HOME/data/fitness-mcp"

# This script lives in the repo it updates, which is a trap in two stages.
#
# Bash reads a script incrementally as it runs, so `git reset --hard` rewriting
# this file mid-execution makes bash resume at a byte offset into the new
# content and silently skip whatever moved. Re-running from a *copy* avoids the
# corruption but still executes the pre-pull text, so a change to this file only
# took effect on the deploy *after* the one that pulled it — which is how the
# backup timer came to be missing even though the pull had succeeded.
#
# So: do the git sync first, then hand off to the freshly-pulled file with exec.
# The new text is fully written before bash ever opens it.
if [ -z "${FITNESS_MCP_DEPLOY_SYNCED:-}" ]; then
    if [ ! -d "$REPO/.git" ]; then
        echo "==> cloning into $REPO"
        git clone "$REPO_URL" "$REPO"
    fi

    echo "==> syncing $REPO to $BRANCH"
    cd "$REPO"
    git fetch origin
    git checkout "$BRANCH"
    git reset --hard "origin/$BRANCH"

    export FITNESS_MCP_DEPLOY_SYNCED=1
    exec bash "$REPO/fitness-mcp/deploy/deploy.sh" "$@"
fi

cd "$REPO"
echo "==> deploying $(git rev-parse --short HEAD) on $BRANCH"

echo "==> ensuring own venv (never shared with the bot)"
if [ ! -d "$VENV" ]; then
    # 3.12 is present system-wide; the bot's venv is untouched either way.
    python3.12 -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -e "$REPO/fitness-mcp"

echo "==> data directory"
mkdir -p "$DATA_DIR"

echo "==> installing systemd user units"
mkdir -p "$HOME/.config/systemd/user"
cp "$REPO/fitness-mcp/deploy/fitness-mcp.service" "$HOME/.config/systemd/user/"
cp "$REPO/fitness-mcp/deploy/fitness-mcp-sync.service" "$HOME/.config/systemd/user/"
cp "$REPO/fitness-mcp/deploy/fitness-mcp-sync.timer" "$HOME/.config/systemd/user/"
cp "$REPO/fitness-mcp/deploy/fitness-mcp-backup.service" "$HOME/.config/systemd/user/"
cp "$REPO/fitness-mcp/deploy/fitness-mcp-backup.timer" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable fitness-mcp.service
systemctl --user restart fitness-mcp.service

echo "==> enabling hourly sync from the bot database"
systemctl --user enable --now fitness-mcp-sync.timer

echo "==> enabling daily database backup"
systemctl --user enable --now fitness-mcp-backup.timer

echo "==> linger (service must survive logout)"
if ! loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=yes"; then
    echo "    WARNING: linger is not enabled. Run: loginctl enable-linger $USER"
else
    echo "    ok"
fi

sleep 2
echo "==> status"
systemctl --user --no-pager status fitness-mcp.service | head -12

echo
echo "==> confirming the bot was not disturbed"
systemctl --user is-active pullup-bot.service
