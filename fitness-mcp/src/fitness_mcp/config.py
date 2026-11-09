"""Configuration, entirely env-var driven.

Nothing here is a secret in Phase 1 — the pullup_bot adapter reads a local
SQLite file and the server exposes read-only tools. Secrets only appear from
Phase 3 (Mi Fitness cloud credentials), and they live in an env file with 600
perms that is never committed.
"""

from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

# Repo root: .../fitness-mcp
_PKG_ROOT = Path(__file__).resolve().parents[2]


def _path_env(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


# ── Timezone ────────────────────────────────────────────────────────────────
# Everything is stored in UTC. `local_date` is computed in this zone, because
# the question that matters is "which day did I train", not where the UTC
# midnight boundary happened to fall.
LOCAL_TZ_NAME = os.environ.get("FITNESS_MCP_TZ", "Asia/Almaty")
LOCAL_TZ = ZoneInfo(LOCAL_TZ_NAME)

# ── Databases ───────────────────────────────────────────────────────────────
# fitness-mcp's own database. This is the source of truth for imported data:
# if an upstream breaks or disappears, history already imported stays here.
DB_PATH = _path_env("FITNESS_MCP_DB", _PKG_ROOT / "var" / "fitness.db")

# The pullup_bot database. Opened READ-ONLY, always. The bot is production and
# this server must never write to it.
PULLUP_BOT_DB = _path_env("FITNESS_MCP_PULLUP_DB", _PKG_ROOT / "var" / "pullup_bot_snapshot.db")

# Strava bulk-export archive (the GDPR zip, not the API). Read straight out of
# the zip and never extracted — it also contains logins, contacts and device
# identifiers that have no business in this database.
STRAVA_ARCHIVE = _path_env("FITNESS_MCP_STRAVA_ARCHIVE", _PKG_ROOT / "var" / "strava_export.zip")

# Mi Fitness export directory (the official archive, not the cloud API).
XIAOMI_EXPORT_DIR = _path_env("FITNESS_MCP_XIAOMI_DIR", _PKG_ROOT / "var" / "xiaomi_export")


def ingest_token() -> str | None:
    """Shared secret the phone must present to POST /ingest/health.

    Returns None when unset, and the endpoint then refuses every request. An
    unauthenticated write endpoint reachable from the public internet must never
    be the default, so absence disables it rather than opening it.
    """
    return os.environ.get("FITNESS_MCP_INGEST_TOKEN", "").strip() or None


def owner_tg_id() -> int:
    """Telegram user id whose training data belongs to the server operator.

    Deliberately has no default. The bot database holds many users' training
    logs; ingesting without an explicit owner would pull in other people's
    data and expose it through the connector. Fail loudly instead.
    """
    raw = os.environ.get("FITNESS_MCP_OWNER_TG_ID", "").strip()
    if not raw:
        raise RuntimeError(
            "FITNESS_MCP_OWNER_TG_ID is not set. The pullup_bot database contains "
            "multiple users; refusing to ingest without an explicit owner id."
        )
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"FITNESS_MCP_OWNER_TG_ID must be an integer, got {raw!r}") from exc
