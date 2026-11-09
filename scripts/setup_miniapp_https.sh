#!/usr/bin/env bash
# Configure the existing node Funnel only. This script never restarts the bot.
set -euo pipefail
umask 077

python="$HOME/pullup-current/.venv/bin/python"
if [[ ! -x "$python" ]]; then
    echo "The deployed bot virtualenv is required before configuring Mini App HTTPS." >&2
    exit 1
fi

exec "$python" - <<'PY'
import copy
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from dotenv.parser import parse_stream

HOST = "fitness-mcp.tail4ed987.ts.net"
HOST_PORT = HOST + ":443"
TARGET = "http://127.0.0.1:8080"
ROOT_HANDLER = {"Proxy": TARGET}
VALUES = {"MINI_APP_URL": "https://" + HOST + "/app",
          "WEB_BIND": "127.0.0.1", "WEB_PORT": "8080"}


class SetupError(Exception):
    pass


def command(args, log=None):
    # CLI output can contain an existing private route. Never echo it.
    result = subprocess.run(args, capture_output=True, check=False)
    if log is not None:
        log.write_bytes(result.stdout + result.stderr)
        log.chmod(0o600)
    if result.returncode:
        raise SetupError("Tailscale command failed; no command output was exposed.")
    return result.stdout


def configuration():
    return json.loads(command(["tailscale", "serve", "status", "--json"]))


def check_configuration(config):
    if config.get("Foreground"):
        raise SetupError("Stop: foreground Serve configuration needs a separate review.")
    if not config.get("TCP", {}).get("443", {}).get("HTTPS"):
        raise SetupError("The existing HTTPS listener on port 443 is required.")
    if config.get("AllowFunnel", {}).get(HOST_PORT) is not True:
        raise SetupError("The expected hostname must already have public Funnel enabled.")
    handlers = config.get("Web", {}).get(HOST_PORT, {}).get("Handlers", {})
    if not any(path != "/" and handler.get("Proxy") == "http://127.0.0.1:8787"
               for path, handler in handlers.items()):
        raise SetupError("The existing fitness MCP route was not found; refusing changes.")
    if "/" in handlers and handlers["/"] != ROOT_HANDLER:
        raise SetupError("The public root already serves a different target; refusing changes.")
    return "/" not in handlers


def prepare_environment(original):
    # The dotenv parser retains original strings, including unrelated multiline
    # secrets and comments. Replace only our three actual bindings, not text
    # inside another variable's quoted value. Do not source the file as shell.
    parts = []
    seen = set()
    for binding in parse_stream(io.StringIO(original.decode("utf-8"))):
        if binding.error:
            raise SetupError("The environment file contains an invalid dotenv binding.")
        if binding.key in VALUES:
            if binding.key not in seen:
                parts.append(binding.original.string[:len(binding.original.string)
                             - len(binding.original.string.lstrip("\r\n"))])
                parts.append(binding.key + "=" + VALUES[binding.key] + "\n")
                seen.add(binding.key)
        else:
            parts.append(binding.original.string)
    content = "".join(parts)
    for key, value in VALUES.items():
        if key not in seen:
            if content and not content.endswith(("\n", "\r")):
                content += "\n"
            content += key + "=" + value + "\n"
    return content.encode("utf-8")


def atomic_environment_write(path, content):
    fd, temporary = tempfile.mkstemp(prefix=".env.pullup_bot.miniapp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    home = Path.home()
    env_path = home / ".env.pullup_bot"
    if os.geteuid() == 0:
        raise SetupError("Run as the bot's regular user, not root or sudo.")
    if not env_path.is_file() or env_path.is_symlink() or env_path.stat().st_uid != os.getuid():
        raise SetupError("A regular, user-owned ~/.env.pullup_bot is required.")

    # Match the already provisioned domain; never create DNS, enable a new
    # Funnel hostname, or rename the node as part of this setup.
    node = json.loads(command(["tailscale", "status", "--json"]))
    if (node.get("Self", {}).get("DNSName", "").rstrip(".") != HOST
            or node.get("BackendState") != "Running"):
        raise SetupError("The active Tailscale hostname differs from the reviewed host.")

    state_dir = home / ".local" / "state" / "pullup-miniapp"
    if state_dir.is_symlink():
        raise SetupError("The private backup directory must not be a symlink.")
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    state_dir.chmod(0o700)
    lock_fd = os.open(state_dir / "setup.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SetupError("Another Mini App HTTPS setup is already running.") from None

        before = configuration()
        add_root = check_configuration(before)
        original_env = env_path.read_bytes()
        prepared_env = prepare_environment(original_env)
        backup = Path(tempfile.mkdtemp(prefix="https-", dir=state_dir))
        backup.chmod(0o700)
        (backup / "funnel.before.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
        (backup / "env.before").write_bytes(original_env)
        (backup / "env.prepared").write_bytes(prepared_env)
        (backup / "manifest.json").write_text(json.dumps({
            "hostname": HOST, "target": TARGET, "root_added": add_root,
            "env_before_sha256": hashlib.sha256(original_env).hexdigest(),
        }, indent=2) + "\n", encoding="utf-8")
        for path in backup.iterdir():
            path.chmod(0o600)

        # Verify both the backup and the source before any routing/env mutation.
        if (backup / "env.before").read_bytes() != original_env:
            raise SetupError("Environment backup validation failed.")
        if json.loads((backup / "funnel.before.json").read_text()) != before:
            raise SetupError("Funnel backup validation failed.")
        if env_path.read_bytes() != original_env or configuration() != before:
            raise SetupError("Configuration changed during preparation; rerun after review.")

        attempted_root = False
        changed_env = False
        try:
            if add_root:
                attempted_root = True
                command(["tailscale", "funnel", "--bg", "--https=443", "--set-path=/",
                         "--yes", TARGET], backup / "funnel.apply.log")
            expected = copy.deepcopy(before)
            expected["Web"][HOST_PORT]["Handlers"]["/"] = ROOT_HANDLER
            after = configuration()
            (backup / "funnel.after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
            (backup / "funnel.after.json").chmod(0o600)
            if after != expected:
                raise SetupError("Funnel changed beyond the public root; refusing to update the bot environment.")
            if env_path.read_bytes() != original_env:
                raise SetupError("The bot environment changed concurrently; refusing to overwrite it.")
            if prepared_env != original_env:
                atomic_environment_write(env_path, prepared_env)
                changed_env = True
            else:
                env_path.chmod(0o600)
        except Exception:
            if changed_env and env_path.read_bytes() == prepared_env:
                atomic_environment_write(env_path, original_env)
            if attempted_root:
                try:
                    current = configuration()
                    current_root = current.get("Web", {}).get(HOST_PORT, {}).get("Handlers", {}).get("/")
                    if current_root == ROOT_HANDLER:
                        command(["tailscale", "funnel", "--https=443", "--set-path=/", "off"],
                                backup / "funnel.rollback.log")
                    elif current_root is not None:
                        raise SetupError("The root route changed concurrently.")
                    if configuration() != before:
                        raise SetupError("Other routes changed; review the private snapshot.")
                except Exception:
                    print("Root-route recovery needs review; other routes were not overwritten.", file=sys.stderr)
            print("Private backups: " + str(backup), file=sys.stderr)
            raise
        print("Mini App HTTPS configured: " + VALUES["MINI_APP_URL"])
        print("Existing routes preserved. Private backups: " + str(backup))
        print("Deploy/restart the bot separately to apply the environment settings.")


try:
    main()
except SetupError as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(1)
except Exception:
    print("Mini App HTTPS setup failed; sensitive configuration details were suppressed.", file=sys.stderr)
    sys.exit(1)
PY
