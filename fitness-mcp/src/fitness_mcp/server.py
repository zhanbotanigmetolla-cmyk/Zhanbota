"""FastMCP app and tool definitions — all tools are read-only.

Every tool opens its own short-lived SQLite connection in read-only mode. That
sidesteps cross-thread connection sharing, and it means the storage layer
itself refuses writes: there is no code path from an MCP tool call to a
mutation, by construction rather than by discipline.

No tool returns credentials, tokens, filesystem paths or environment values.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import sqlite3
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import config, db
from .ingest.apple_health import ApplePayload

log = logging.getLogger("fitness_mcp.server")

MAX_LIMIT = 500

_HOST = os.environ.get("FITNESS_MCP_HOST", "127.0.0.1")
_PORT = int(os.environ.get("FITNESS_MCP_PORT", "8787"))

# Public hostname(s) this is reachable under, comma separated. Requests arrive
# through a reverse proxy (a Tailscale Funnel) carrying the public Host header,
# not the loopback address the socket is bound to.
_PUBLIC_HOSTS = [h.strip() for h in os.environ.get("FITNESS_MCP_PUBLIC_HOST", "").split(",") if h.strip()]

# DNS rebinding protection stays ON. FastMCP's loopback default only trusts
# localhost Host headers, which a proxied public request never has, so the
# public name is added explicitly rather than by disabling the check.
_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", *_PUBLIC_HOSTS,
                   *[f"{h}:*" for h in _PUBLIC_HOSTS]],
    allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*",
                     *[f"https://{h}" for h in _PUBLIC_HOSTS]],
)

# stateless_http keeps every request self-contained: no server-side session to
# resume, so a restart can never leave a client wedged. Streamable HTTP mounts
# at /mcp. SSE is deprecated and deliberately unused.
mcp = FastMCP(
    "fitness-mcp",
    stateless_http=True,
    host=_HOST,
    port=_PORT,
    transport_security=_transport_security,
)


def _conn() -> sqlite3.Connection:
    return db.connect(config.DB_PATH, read_only=True)


def _ensure_db() -> None:
    """Create the schema if this is a first run, so read-only opens succeed."""
    with db.connect(config.DB_PATH) as conn:
        db.migrate(conn)


# ── tools ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_workouts(
    start_date: str,
    end_date: str,
    sport_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List training sessions in a date range, newest first.

    Dates are local calendar dates in Asia/Almaty, format YYYY-MM-DD, and both
    ends are INCLUSIVE. A session is one day's training; strength work done on
    the same day is one session even when it covers several exercises.

    Returns one entry per session with its id, date, sport type, the distinct
    exercises trained, the number of sets, and total reps. Use get_workout for
    the individual sets of a session.

    Fields that the underlying source never recorded come back as null — a null
    duration means "not tracked", not "zero". Days with no training simply do
    not appear; absence is not a zero row.

    Args:
        start_date: First day to include, YYYY-MM-DD.
        end_date: Last day to include, YYYY-MM-DD, inclusive.
        sport_type: Optional filter, e.g. "strength". Omit for all types.
        limit: Maximum sessions to return (default 100, capped at 500).
    """
    limit = max(1, min(int(limit), MAX_LIMIT))
    with _conn() as conn:
        return db.list_workouts(conn, start_date, end_date, sport_type, limit)


@mcp.tool()
def get_workout(workout_id: int) -> dict[str, Any] | None:
    """Get one training session in full, including every individual set.

    Takes the numeric id from list_workouts. Returns the session fields plus a
    "sets" list, each set carrying its exercise, position within the session
    (set_index, 0-based), reps, weight_kg, and RPE.

    Set flags worth reading: `inferred` is 1 when the source recorded only a
    session total and the breakdown was reconstructed — such a set counts
    toward volume but is not a real single-set record. `rpe` is null when it
    was never entered.

    Returns null if no session has that id.

    Args:
        workout_id: Numeric session id from list_workouts.
    """
    with _conn() as conn:
        return db.get_workout(conn, int(workout_id))


@mcp.tool()
def training_summary(
    start_date: str,
    end_date: str,
    group_by: str = "week",
) -> list[dict[str, Any]]:
    """Aggregate training volume per day, week or month.

    Dates are local calendar dates in Asia/Almaty (YYYY-MM-DD), both ends
    INCLUSIVE. Use this for trends and totals rather than pulling every session
    and adding them up.

    group_by must be one of:
      "day"   — bucket is the date itself, YYYY-MM-DD
      "week"  — bucket is that week's MONDAY, as YYYY-MM-DD
      "month" — bucket is YYYY-MM

    Each bucket reports:
      sessions      — number of recorded activities
      training_days — number of distinct days trained
      total_reps    — volume measure for strength work
      duration_s, distance_m — 0 when the source tracked neither, which is the
                    case for all bot-sourced strength work

    sessions and training_days differ, and the distinction matters: several
    activities can fall on one day (six cycling commutes is six sessions but
    one training day). Use training_days for "how often did I train" and
    sessions for "how many activities are recorded".

    Buckets with no training are omitted entirely rather than returned as
    zeros, so a gap in the output means no training happened.

    Args:
        start_date: First day to include, YYYY-MM-DD.
        end_date: Last day to include, YYYY-MM-DD, inclusive.
        group_by: One of "day", "week", "month". Defaults to "week".
    """
    with _conn() as conn:
        return db.training_summary(conn, start_date, end_date, group_by)


@mcp.tool()
def exercise_history(
    exercise: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Every logged set of a single movement, oldest first, for tracking progression.

    Returns one entry per set: the local date, the session id, set_index within
    that session, reps, weight_kg, RPE, and the `inferred` flag described in
    get_workout.

    Exercise names are lowercase identifiers as stored, e.g. "pullups",
    "pushups", "dips", "squats". The match is exact, so call personal_records
    with no argument first if you need to discover which names exist.

    Omit the dates for the full history.

    Args:
        exercise: Exact exercise name, e.g. "pullups".
        start_date: Optional first day, YYYY-MM-DD.
        end_date: Optional last day, YYYY-MM-DD, inclusive.
    """
    with _conn() as conn:
        return db.exercise_history(conn, exercise, start_date, end_date)


@mcp.tool()
def personal_records(exercise: str | None = None) -> list[dict[str, Any]]:
    """Best recorded efforts per exercise. Omit the argument for all exercises.

    For each exercise returns:
      best_set_by_reps        — the highest-rep single set
      best_set_by_weight      — the heaviest single set
      estimated_1rm           — one-rep max estimate, Epley formula
      best_session_total_reps — the highest single-day total for that exercise

    IMPORTANT for interpreting the result: best_set_by_weight and
    estimated_1rm are null for unweighted bodyweight training, because no
    external load was ever recorded. That is a genuine absence of data, not a
    zero and not an error — do not describe a null 1RM as a weakness or a
    missing PR, and do not try to compute one from bodyweight. For bodyweight
    work, best_set_by_reps and best_session_total_reps are the meaningful
    records.

    Sets reconstructed from a session total are excluded from single-set
    records, so these numbers reflect genuinely logged sets.

    Args:
        exercise: Optional exact exercise name to restrict to.
    """
    with _conn() as conn:
        return db.personal_records(conn, exercise)


@mcp.tool()
def hr_distribution(start_date: str, end_date: str) -> dict[str, Any]:
    """Approximate heart-rate zone distribution across a date range.

    READ THIS BEFORE QUOTING THE NUMBERS. The stored data has one average and
    one maximum heart rate per session, not a heart-rate time series, so real
    time-in-zone cannot be computed. This attributes each session's entire
    duration to the single zone its average HR falls into. It is a rough
    session-level picture and should be described that way, not as measured
    time in zone.

    Zones are fractions of the highest max HR observed in the stored data,
    which is a stand-in for true max HR: Z1 <60%, Z2 60-70%, Z3 70-80%,
    Z4 80-90%, Z5 >=90%.

    Sessions without heart-rate data are counted in sessions_without_hr rather
    than dropped. Strength work from the pullup bot carries no HR at all, so
    on bot-only data every session lands there and the zones are empty — that
    means "no heart-rate source connected", not "no cardio done".

    Args:
        start_date: First day to include, YYYY-MM-DD.
        end_date: Last day to include, YYYY-MM-DD, inclusive.
    """
    with _conn() as conn:
        return db.hr_distribution(conn, start_date, end_date)


@mcp.tool()
def recovery_metrics(start_date: str, end_date: str) -> dict[str, Any]:
    """Resting heart rate and sleep over a date range, with a simple trend.

    Dates are local calendar dates in Asia/Almaty (YYYY-MM-DD), both ends
    INCLUSIVE.

    Returns a per-day series (resting HR, sleep minutes, steps, stress),
    summary statistics for each, and a trend that compares the first half of
    the range against the second half. The trend is a plain two-halves
    comparison, not a regression — do not present it as a statistical result.
    A FALLING resting heart rate generally indicates improving recovery, which
    is why a negative change is reported as "improving".

    These metrics come from the Xiaomi export only. The pullup bot records
    none of them, so until that export is imported this returns an empty
    "days" list and an explanatory "note". An empty result means NO DATA
    SOURCE IS CONNECTED — it does not mean recovery was poor, and it must not
    be reported as bad sleep or an elevated resting heart rate.

    Args:
        start_date: First day to include, YYYY-MM-DD.
        end_date: Last day to include, YYYY-MM-DD, inclusive.
    """
    with _conn() as conn:
        return db.recovery_metrics(conn, start_date, end_date)


# ── push ingest (NOT an MCP tool) ───────────────────────────────────────────
#
# The MCP surface above stays strictly read-only. This is a plain HTTP route
# that the phone POSTs to; no MCP tool can reach it and Claude cannot invoke it.
# It exists because HealthKit will not release data while the device is locked,
# so the phone has to push when it happens to be unlocked rather than being
# polled on a schedule.

MAX_BODY_BYTES = 8 * 1024 * 1024


@mcp.custom_route("/ingest/health", methods=["POST"])
async def ingest_health(request: Request) -> JSONResponse:
    expected = config.ingest_token()
    if not expected:
        # Refusing beats defaulting open: this endpoint writes, and it is
        # reachable from the public internet through the funnel.
        return JSONResponse({"error": "ingest is not configured"}, status_code=503)

    presented = request.headers.get("x-ingest-token", "")
    if not hmac.compare_digest(presented, expected):
        log.warning("rejected /ingest/health: bad or missing token")
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        return JSONResponse({"error": "payload too large"}, status_code=413)

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return JSONResponse({"error": f"invalid JSON: {exc}"}, status_code=400)

    # Count what arrived *before* parsing. Without this, "0 workouts" is
    # ambiguous between "the phone sent nothing" and "the phone sent things
    # that all failed to parse", and those need completely different fixes.
    received = {
        key: len(payload[key]) if isinstance(payload.get(key), list) else "not-a-list"
        for key in ("workouts", "sleep_samples", "resting_hr", "steps")
        if key in payload
    }

    try:
        parsed = ApplePayload(payload)
        workouts = list(parsed.workouts())
        metrics = list(parsed.daily_metrics())
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    created = updated = 0
    conn = db.connect(config.DB_PATH)
    try:
        db.migrate(conn)
        # One transaction: a partial delivery is never half-applied.
        with conn:
            for row in workouts:
                _, was_created = db.upsert_workout(conn, row)
                created += was_created
                updated += not was_created
            for metric in metrics:
                db.upsert_daily_metric(conn, metric)
    except Exception as exc:  # noqa: BLE001 - never leak a stack trace outward
        log.exception("ingest failed")
        return JSONResponse({"error": f"{type(exc).__name__}"}, status_code=500)
    finally:
        conn.close()

    log.info(
        "ingest: received=%s -> %d workouts (%d new), %d daily metrics, %d warnings",
        received or "{}", len(workouts), created, len(metrics), len(parsed.warnings),
    )
    # Counts come back so a single run can be verified from the phone itself.
    # `received` echoes the raw item counts per key, and `hint` says plainly
    # what to fix when nothing arrived — debugging a Shortcut from a phone is
    # painful enough without having to guess.
    body: dict[str, Any] = {
        "ok": True,
        "received": received,
        "workouts_received": len(workouts),
        "workouts_created": created,
        "workouts_updated": updated,
        "daily_metrics": len(metrics),
        "warnings": parsed.warnings[:20],
    }
    if not received:
        body["hint"] = ("Body contained no workouts/sleep_samples/resting_hr/steps keys. "
                        "In Get Contents of URL set Request Body to JSON and add an Array "
                        "field per key; a leftover Text action with {} sends this.")
    elif not workouts and not metrics:
        body["hint"] = ("Keys arrived but every entry was unusable. Check that the "
                        "date fields are set to ISO 8601 format.")
    return JSONResponse(body)


# ── entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    _ensure_db()
    # Task 1 runs over stdio. Task 2 flips this to streamable-http; keeping it
    # env-selectable means that switch is configuration, not a code change.
    transport = os.environ.get("FITNESS_MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "streamable-http":
        # Bound to loopback by default. Whatever exposes this — a Tailscale
        # Funnel or a reverse proxy — is the only thing that should reach it,
        # so the port itself is never open to the network.
        log.info("serving streamable-http on %s:%s/mcp", mcp.settings.host, mcp.settings.port)
        mcp.run(transport="streamable-http")
    else:
        raise SystemExit(
            f"Unsupported transport {transport!r}: use 'stdio' or 'streamable-http'."
        )


if __name__ == "__main__":
    main()
