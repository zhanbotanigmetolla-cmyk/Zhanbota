# Mini App HTTPS on the existing GCP server

The server already has Tailscale Funnel and a valid HTTPS hostname:
`fitness-mcp.tail4ed987.ts.net`. The Mini App uses
`https://fitness-mcp.tail4ed987.ts.net/app`, with aiohttp listening only on
`127.0.0.1:8080`. No new domain, certificate service, VM or public firewall rule
is needed. The existing fitness MCP route remains on the same hostname.

After reviewing and testing the release, run as `nigmetolla_zhanbota` on the server:

```bash
bash /path/to/reviewed/release/scripts/setup_miniapp_https.sh
```

The script requires the existing running Tailscale hostname, public HTTPS on port
443, and the existing MCP proxy. It refuses an occupied root route unless it
already points exactly to `http://127.0.0.1:8080`. It adds only the root proxy and
verifies that every other configuration value is unchanged. More specific MCP
paths keep their existing handler; `/app` and API paths reach aiohttp unchanged.
Tailscale documents these [path-matching and proxy rules](https://tailscale.com/docs/reference/tailscale-cli/serve)
and [persistent Funnel configuration](https://tailscale.com/docs/reference/tailscale-cli/funnel).

Before changing anything, the script validates private backups under
`~/.local/state/pullup-miniapp/https-*/` (directory mode `700`, files mode `600`).
Only `MINI_APP_URL`, `WEB_BIND` and `WEB_PORT` are updated in `~/.env.pullup_bot`;
unrelated secrets and multiline values are preserved. The environment replacement
is atomic and mode `600`. Re-running the script is safe. It does **not** restart
the bot: deploy the reviewed release separately, then check `/app`, static assets,
the unauthenticated API rejection and Telegram launch authentication.

If setup fails after adding the root route, it attempts to remove only that root
route. Existing routes are never reset or overwritten from an old snapshot.
If manual recovery is needed, first inspect `manifest.json` in the printed backup
directory. Remove the root only when `root_added` is true and the current root
still points to `http://127.0.0.1:8080`:

```bash
# Keep CLI output private: it can contain the existing MCP access path.
umask 077
tailscale funnel --https=443 --set-path=/ off > ~/miniapp-root-recovery.log 2>&1
```

This leaves the more specific MCP route in place. Restore `env.before` to
`~/.env.pullup_bot` with mode `600` only after checking that no other environment
settings changed since that backup, then restart the previous bot release. Never
run `tailscale funnel reset` or `tailscale serve reset` for Mini App recovery.
The available `serve get-config/set-config` commands manage **Tailscale Services**;
they are not the restoration format for this node's `serve status --json` snapshot.
