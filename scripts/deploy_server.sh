#!/usr/bin/env bash
# Run via deploy.ps1, or: bash scripts/deploy_server.sh BRANCH EXPECTED_SHA
set -euo pipefail

branch=${1:?Specify a feature/fix branch}
expected=${2:?Specify the exact commit SHA to deploy}
if [[ ! "$branch" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ || "$branch" == main || "$branch" == master ]]; then
    echo "Refusing to deploy an invalid branch or main/master." >&2
    exit 2
fi
if [[ ! "$expected" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Expected a full commit SHA." >&2
    exit 2
fi

repo="$HOME/repo"
service=pullup-bot.service
current="$HOME/pullup-current"
override_dir="$HOME/.config/systemd/user/$service.d"
override="$override_dir/50-release.conf"
exec 9>"$HOME/.pullup-deploy.lock"
flock -n 9 || { echo "Another deployment is in progress." >&2; exit 1; }
git -C "$repo" check-ref-format --branch "$branch" >/dev/null
if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=no)" ]]; then
    echo "Server repository has tracked changes; refusing to overwrite them." >&2
    exit 1
fi
if [[ -e "$current" && ! -L "$current" ]]; then
    echo "$current must be absent or a release symlink." >&2
    exit 1
fi
git -C "$repo" fetch origin "$branch"
actual=$(git -C "$repo" rev-parse FETCH_HEAD)
[[ "$actual" == "$expected" ]] || { echo "Remote branch moved; deployment stopped." >&2; exit 1; }

mkdir -p "$HOME/pullup-releases"
release=$(mktemp -d "$HOME/pullup-releases/$expected.XXXXXX")
git -C "$repo" archive "$expected" | tar -x -C "$release"
# A separate environment keeps failed installations away from the running bot.
"$HOME/.venv-pullup/bin/python" -m venv "$release/.venv"
python="$release/.venv/bin/python"
"$python" -m pip install --disable-pip-version-check -r "$release/requirements-dev.lock"
"$python" -m pip check
(
    cd "$release"
    PULLUP_TESTING=1 "$python" -m pytest pullup_bot/tests -q
    env -u PULLUP_TESTING "$python" -c 'from pullup_bot.config import validate_webhook_config; validate_webhook_config()'
)

mkdir -p "$override_dir" "$release/backups"
had_override=0
if [[ -f "$override" ]]; then
    cp -p "$override" "$release/backups/50-release.conf"
    had_override=1
fi
old_target=$(readlink "$current" || true)
# Refuse to snapshot different databases if systemd overrides their paths.
service_pid=$(systemctl --user show "$service" -p MainPID --value)
if [[ "$service_pid" =~ ^[1-9][0-9]*$ ]]; then
    (
        cd "$release"
        "$python" - "$service_pid" <<'PY'
import os
import sys
from pathlib import Path
from pullup_bot.config import DB_PATH, FSM_DB_PATH
entries = Path(f"/proc/{sys.argv[1]}/environ").read_bytes().split(b"\0")
environment = dict(entry.split(b"=", 1) for entry in entries if b"=" in entry)
for name, configured in (("PULLUP_DB", DB_PATH), ("PULLUP_FSM_DB", FSM_DB_PATH)):
    override = environment.get(name.encode())
    if override and Path(os.fsdecode(override)).expanduser().resolve() != Path(configured).expanduser().resolve():
        raise RuntimeError(f"{name} differs between systemd and deployment; align the configuration first")
PY
    )
fi
stopped=0
rollback() {
    rc=$?
    trap - EXIT
    if [[ "$rc" -ne 0 && "$stopped" == 1 ]]; then
        echo "Deployment failed; restoring the previous service configuration." >&2
        systemctl --user stop "$service" || true
        if [[ "$had_override" == 1 ]]; then
            cp -p "$release/backups/50-release.conf" "$override"
        else
            rm -f "$override"
        fi
        if [[ -n "$old_target" ]]; then
            ln -sfn "$old_target" "$current.rollback"
            mv -Tf "$current.rollback" "$current"
        else
            rm -f "$current"
        fi
        systemctl --user daemon-reload
        systemctl --user start "$service" || true
        echo "SQLite snapshots retained at $release/backups (no automatic data rewind)." >&2
    fi
    exit "$rc"
}
trap rollback EXIT
systemctl --user stop "$service"
stopped=1
# Snapshot SQLite through its backup API, including any committed WAL content.
(
    cd "$release"
    "$python" - "$release/backups" <<'PY'
import sqlite3
import sys
from pathlib import Path
from pullup_bot.config import DB_PATH, FSM_DB_PATH
for label, source in (("workouts", DB_PATH), ("fsm", FSM_DB_PATH)):
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(f"Configured {label} database is missing; refusing an unbacked deployment")
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as src:
        with sqlite3.connect(Path(sys.argv[1]) / f"{label}.db") as dst:
            src.backup(dst)
print("SQLite snapshots completed.")
PY
)
ln -sfn "$release" "$current.next"
mv -Tf "$current.next" "$current"
cat >"$override" <<EOF
[Service]
WorkingDirectory=$current
ExecStart=
ExecStart=$current/.venv/bin/python -m pullup_bot
EOF
systemctl --user daemon-reload
systemctl --user reset-failed "$service"
systemctl --user start "$service"
ready=0
for attempt in {1..10}; do
    sleep 3
    systemctl --user is-active --quiet "$service"
    restarts=$(systemctl --user show "$service" -p NRestarts --value)
    [[ "$restarts" == 0 ]] || { echo "New bot restarted during startup." >&2; exit 1; }
    invocation=$(systemctl --user show "$service" -p InvocationID --value)
    if journalctl --user "_SYSTEMD_INVOCATION_ID=$invocation" --no-pager -o cat | grep -Eq 'Run polling for bot|Webhook mode on'; then
        ready=1
        break
    fi
done
[[ "$ready" == 1 ]] || { echo "No successful Telegram startup within 30 seconds." >&2; exit 1; }
# Keep the repository checkout on the deployed branch, without pulling main into it.
git -C "$repo" checkout -B "$branch" "$expected"
printf '#!/usr/bin/env bash\nset -euo pipefail\nexec bash "$HOME/repo/scripts/deploy_server.sh" "$@"\n' >"$HOME/deploy.sh"
chmod 700 "$HOME/deploy.sh"
stopped=0
echo "Deployed $expected from $branch. Service is active. Backups: $release/backups"
