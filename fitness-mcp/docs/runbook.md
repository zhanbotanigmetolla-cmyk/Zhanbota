# fitness-mcp runbook

Everything is a systemd **user** service on the GCP VM, so every `systemctl`
command needs `--user`. Without it you get a confusing "unit not found".

```bash
SSH="ssh -i ~/.ssh/id_ed25519_claude nigmetolla_zhanbota@35.226.20.162"
```

## Where things are

| | |
|---|---|
| Code | `~/fitness-mcp-src` (own clone — **not** `~/repo`, which the bot deploys from) |
| Virtualenv | `~/.venv-fitness-mcp` (own, nothing shared with the bot) |
| Database | `~/data/fitness-mcp/fitness.db` |
| Backups | `~/data/fitness-mcp/fitness.db.bak-YYYY-MM-DD`, last 7 |
| Secrets | `~/.env.fitness_mcp` (mode 600, never committed) |
| Units | `~/.config/systemd/user/fitness-mcp{,-sync,-backup}.{service,timer}` |

## Health check

```bash
$SSH "systemctl --user status fitness-mcp.service --no-pager | head -12
      systemctl --user list-timers 'fitness-mcp*' --no-pager
      systemctl --user list-units --failed --no-pager"
```

Then from anywhere:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
  "https://fitness-mcp.tail4ed987.ts.net/<SECRET>/mcp" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"c","version":"1"}}}'
# 200 = healthy
```

## Logs

```bash
$SSH "journalctl --user -u fitness-mcp.service -n 60 --no-pager"          # server
$SSH "journalctl --user -u fitness-mcp-sync.service -n 30 --no-pager"     # hourly import
$SSH "journalctl --user -u fitness-mcp.service --no-pager | grep -i ingest"  # phone pushes
$SSH "journalctl --user -u fitness-mcp.service --no-pager | grep 'rejected'" # bad tokens
```

## Restart / redeploy

```bash
$SSH "systemctl --user restart fitness-mcp.service"                       # restart only
$SSH "bash ~/fitness-mcp-src/fitness-mcp/deploy/deploy.sh main"           # pull + redeploy
```

The deploy script never touches `pullup-bot.service` and prints its status at
the end to prove it. **Never** use the bot's `~/deploy.sh` for this.

## Re-importing

| Source | Command | Notes |
|---|---|---|
| Bot | `$SSH "systemctl --user start fitness-mcp-sync.service"` | Also runs hourly on its own |
| Strava | `--source strava_export --archive <zip>` | Manual; request a fresh export first |
| Xiaomi | `--source xiaomi_export --export-dir <dir>` | Manual; ~15 working days to obtain |
| Apple Health | run the iOS Shortcut | Pushes a rolling 7-day window |

Manual imports run from wherever the archive is, usually the laptop:

```bash
cd fitness-mcp
./.venv/Scripts/python.exe -m fitness_mcp.ingest_cli \
    --source xiaomi_export --export-dir "path/to/..._MiFitness_..._data_copy"
```

**Every import is idempotent** — re-running only updates. After importing a new
archive that overlaps an existing one, run dedup explicitly:

```bash
./.venv/Scripts/python.exe -m fitness_mcp.ingest_cli --dedupe-only
```

Dedup is never automatic: it is the only operation that can lose information if
the matching heuristics are wrong.

## Undoing a bad merge

Superseded rows are kept, not deleted. To restore everything:

```bash
$SSH "~/.venv-fitness-mcp/bin/python -c \"
import sqlite3
c=sqlite3.connect('/home/nigmetolla_zhanbota/data/fitness-mcp/fitness.db')
with c: n=c.execute('update workouts set superseded_by=null').rowcount
print('restored', n)
\""
```

## Backup and restore

Backups run daily and keep 7. To take one now:

```bash
$SSH "systemctl --user start fitness-mcp-backup.service && ls -la ~/data/fitness-mcp/"
```

To restore, stop the writers first — copying over a live WAL database corrupts
it:

```bash
$SSH "systemctl --user stop fitness-mcp.service fitness-mcp-sync.timer
      cp ~/data/fitness-mcp/fitness.db.bak-YYYY-MM-DD ~/data/fitness-mcp/fitness.db
      systemctl --user start fitness-mcp.service fitness-mcp-sync.timer"
```

## Rotating the ingest token

```bash
$SSH "TOKEN=\$(head -c 48 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 40)
      sed -i \"s|^FITNESS_MCP_INGEST_TOKEN=.*|FITNESS_MCP_INGEST_TOKEN=\$TOKEN|\" ~/.env.fitness_mcp
      systemctl --user restart fitness-mcp.service
      grep -oP '(?<=FITNESS_MCP_INGEST_TOKEN=).*' ~/.env.fitness_mcp"
```

Then update the `X-Ingest-Token` header in the iOS Shortcut. The old token
stops working the moment the service restarts.

## Rotating the secret path

Do this if the URL is ever pasted somewhere public. It breaks the Claude
connector and the Shortcut until both are updated.

```bash
$SSH "OLD=\$(grep -oP '(?<=FITNESS_MCP_SECRET_PATH=).*' ~/.env.fitness_mcp)
      NEW=\$(head -c 48 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32)
      tailscale funnel --https=443 off
      tailscale funnel --bg --set-path=/\$NEW 8787
      sed -i \"s|^FITNESS_MCP_SECRET_PATH=.*|FITNESS_MCP_SECRET_PATH=\$NEW|\" ~/.env.fitness_mcp
      echo \"new URL: https://fitness-mcp.tail4ed987.ts.net/\$NEW/mcp\""
```

Then re-add the connector in Claude with the new URL and update the Shortcut.

## Capacity

Nothing here is near a limit, and none of it costs money.

```bash
$SSH "df -h / | tail -1; free -m | head -2; du -sh ~/data/fitness-mcp"
```

Current: **0.8 MB** database, 448 workouts, 390 daily metrics. Disk 33% used
with 20 GB free; ~600 MB RAM available; the server itself holds ~40 MB against
a 200 MB cap. At the present growth rate the database gains roughly 1 MB a year.

The only recurring charge on this VM is its external IPv4, about **$3.65/month**
— a cost of running the Telegram bot, not of this project, and unaffected by
anything here.

## If the VM's IP changes

**Nothing breaks.** Tailscale Funnel is an outbound connection, so the public
hostname does not depend on the VM's address. This is the main reason it was
chosen over opening a port.

Only your own SSH access breaks. Get the new address from the GCP console, or
reach the VM over Tailscale instead:

```bash
ssh nigmetolla_zhanbota@100.109.78.35     # stable tailnet IP
```

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `421 Invalid Host header` | Public hostname missing from the allowlist | Check `FITNESS_MCP_PUBLIC_HOST` in the unit |
| `503 ingest is not configured` | Token missing from the env file | Re-add `FITNESS_MCP_INGEST_TOKEN`, restart |
| `401` on ingest | Wrong or stale token in the Shortcut | Rotate, update the Shortcut |
| Connector fails to add | URL truncated or case-mangled on paste | The secret path is case-sensitive and must end `/mcp` |
| `NXDOMAIN` right after setup | Funnel DNS not propagated yet | Wait up to 10 minutes |
| Data looks stale in Claude | Sync failed silently | `journalctl --user -u fitness-mcp-sync.service` |
| `database is locked` | Two writers collided | Should not happen — WAL plus a 10s busy timeout. Report it. |

## The gap worth knowing about

**A failed sync tells nobody.** It logs, systemd marks the unit failed, and
that is all — you would notice by seeing stale numbers in Claude. Closing it
means either a Telegram alert on failure (the bot already has a token and your
chat id) or exposing a `last_sync` timestamp so Claude can say the data is
stale. Neither is built.
