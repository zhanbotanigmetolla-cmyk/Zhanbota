# fitness-mcp

A personal, **read-only** MCP server over my own training data.

**Status: Phase 1 complete (local, stdio).** Not deployed, not reachable from
the network, no TLS, no auth. Tasks 2–7 are not started — see
[Not built yet](#not-built-yet).

---

## Why it is shaped this way

The server owns **its own SQLite database**, which is the source of truth for
imported data. It is not a live view over the bot. That matters because the
upstreams have very different reliability: once a workout is imported, it stays
imported even if the source that produced it breaks, changes its API, or
disappears. `raw_json` keeps the original upstream payload on every row, so a
parsing bug can be fixed and re-run over stored data rather than costing
history.

Ingest adapters only *produce* normalized rows. They never write to the
database themselves — the runner owns the transaction. An adapter that raises
halfway through leaves the database exactly as it was, and the failure is
reported rather than propagated. One fragile source can never corrupt a healthy
one or take down the server.

```
fitness-mcp/
├── src/fitness_mcp/
│   ├── server.py       # FastMCP app + the six read-only tools
│   ├── db.py           # schema, migrations, queries
│   ├── ingest_cli.py   # `python -m fitness_mcp.ingest_cli`
│   ├── config.py       # env-var driven, no hardcoded secrets
│   └── ingest/
│       ├── base.py         # Adapter protocol + fail-soft runner
│       ├── pullup_bot.py   # Phase 1 — implemented
│       └── strava.py       # deliberately NOT implemented, see below
├── tests/
└── var/                # gitignored: local databases, never committed
```

## The pullup_bot constraint

The bot is production and used daily. This server:

* opens the bot database **read-only** (`file:...?mode=ro`) — enforced in code
  and asserted by a test that the connection rejects `CREATE TABLE`;
* never touches the bot's systemd unit, venv, or shared packages;
* filters to a single owner. The bot database holds 36 users' training logs.
  `FITNESS_MCP_OWNER_TG_ID` has **no default** and ingest refuses to run without
  it, so nobody else's data can be pulled in by accident.

## Data model

One `workouts` row per **training session** (a day), with a `sets` child table
carrying the exercise per set. The bot stores one row per
`(user_id, date, exercise)`, so a day with pull-ups *and* push-ups collapses
into one session with sets of both.

Times are stored UTC; `local_date` is computed in **Asia/Almaty** and is what
every query filters and groups on — the question is "which day did I train",
not where the UTC midnight boundary fell.

Idempotency comes from `UNIQUE(source, source_id)` plus
`INSERT ... ON CONFLICT DO UPDATE`. A workout's sets are fully replaced on
re-import, so editing a day upstream to have *fewer* sets cannot leave orphans.

### Decisions worth knowing before you trust a number

| Decision | Why |
|---|---|
| `started_at` is synthesized as local midnight → UTC | The bot records a date, no clock time. It marks the day; do not read precision into it. |
| `rpe = 0` becomes `NULL` | The bot writes 0 when RPE was never entered, and 0 is not a valid RPE. |
| Rest-day rows are dropped | `exercise='rest'` marks a rest day, not a session. |
| Planned-but-not-performed rows are dropped | No sets and `completed = 0` means it never happened. |
| Sets reconstructed from a session total are flagged `inferred` | They count toward volume but are excluded from single-set records, which would otherwise invent a PR. |
| `weight_kg` and `estimated_1rm` are `NULL` for bodyweight work | No external load was ever recorded. Null is the honest answer; a 1RM computed from bodyweight would be fiction. |
| `hr_distribution` is an approximation | The schema stores one avg/max HR per session, not a time series, so true time-in-zone is not derivable. Each session's duration is attributed to the single zone its average falls in, and the tool says so. |

Where the source disagrees with itself, ingest reports rather than silently
resolving. One real example in the current data:

```
2026-04-05 pullups: sets sum to 80 but completed=40; using the per-set breakdown
```

That row also has a UI button label (`◀️ Назад`) leaked into `notes`, so it
looks like a bot bug rather than a training log. **The per-set breakdown wins**
— it is the granular record — but the discrepancy is surfaced on every run.

## Running it

```bash
py -3 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

Ingest (never runs automatically; nothing a conversation does can trigger it):

```bash
FITNESS_MCP_OWNER_TG_ID=<your telegram id> \
  ./.venv/Scripts/python.exe -m fitness_mcp.ingest_cli --verbose
```

Tests:

```bash
./.venv/Scripts/python.exe -m pytest -q
```

The suite seeds fixtures with hand-computed totals and asserts the aggregations
against them — including that week buckets land on Mondays, that a week
straddling a month boundary is bucketed correctly, and that session duration is
not multiplied by set count when sets are joined.

### Configuration

| Variable | Default | Meaning |
|---|---|---|
| `FITNESS_MCP_DB` | `var/fitness.db` | This server's own database |
| `FITNESS_MCP_PULLUP_DB` | `var/pullup_bot_snapshot.db` | Bot database, opened read-only |
| `FITNESS_MCP_OWNER_TG_ID` | *(none — required)* | Whose data to import |
| `FITNESS_MCP_TZ` | `Asia/Almaty` | Zone for `local_date` |

## Tools

All read-only. No write tools. No tool returns credentials, tokens, filesystem
paths or environment values. Every tool opens its own short-lived connection in
SQLite read-only mode, so there is no code path from a tool call to a mutation
by construction rather than by discipline.

| Tool | Returns |
|---|---|
| `list_workouts` | Sessions in a date range, newest first |
| `get_workout` | One session in full, including every set |
| `training_summary` | Volume/duration/distance/session count per day, week or month |
| `exercise_history` | Every logged set of one movement, oldest first |
| `personal_records` | Best set by reps, by weight, estimated 1RM, best day |
| `hr_distribution` | Approximate session-level HR zone distribution |

## Strava — deliberately not built

As of **2026-06-30**, Standard-tier Strava API access requires an active paid
Strava subscription. Self-hosting does not route around it: the gate is on the
API credentials, not on where the client runs. `ingest/strava.py` is a stub that
documents the shape and refuses to run. Do not fill it in without a
subscription — it will fail at authorization, not at the code.

## Not built yet

Phase 2 (Xiaomi official export), Phase 3 (Mi Fitness cloud), and everything
network-facing:

* Streamable HTTP transport (Task 2) — `server.py` selects transport by env var
  so this is configuration, not a rewrite
* Domain + TLS (Task 3), GCP firewall (Task 4), auth (Task 5), deploy (Task 6)
* **Threat model** — belongs with Task 5 and is written when the server is
  actually exposed. Right now it listens on nothing.
* **Runbook** and **Xiaomi API-change recovery** — written when there is a
  deployed service and a Xiaomi adapter to recover.
