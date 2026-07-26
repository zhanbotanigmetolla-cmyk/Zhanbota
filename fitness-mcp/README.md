# fitness-mcp

A personal, **read-only** MCP server over my own training data.

**Status: Phase 1 complete (local, stdio).** Not deployed, not reachable from
the network, no TLS, no auth. Target host is Cloudflare Workers + D1 on the
free plan — see [Not built yet](#not-built-yet).

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
| `recovery_metrics` | Resting HR and sleep, with a two-halves trend |

## Cross-source deduplication

A run recorded by both Strava and the Xiaomi export is one workout. Dedup
matches on start time within a tolerance plus comparable duration, and keeps
whichever row has more fields populated.

Two properties worth knowing:

* **Only rows with an exact start time take part.** The bot's `started_at` is a
  synthesized day marker (`time_precision = 'date_only'`), so including those
  would make every same-day session look like a duplicate of every other.
* **Nothing is deleted.** The losing row keeps its data and its `raw_json`, and
  is marked `superseded_by`. Queries return canonical rows only. Clearing that
  one column fully reverses a merge, so a bad match costs nothing.

Dedup does not run automatically — it is a separate step, because merging is
the one operation here that can lose information if the heuristics are wrong.

## Strava — API not built, bulk export is

Two different things:

* **Strava API — will not be built.** Since **2026-06-30**, Standard-tier API
  access requires an active paid Strava subscription. Self-hosting does not
  route around it: the gate is on the credentials, not on where the client
  runs. `ingest/strava.py` is a stub that documents the shape and refuses to
  run. It will fail at authorization, not at the code.
* **Strava bulk export — built.** *Settings → My Account → Download or Delete
  Your Account → request archive*. File-based: no API keys, no rate limits,
  nothing that can start charging.

```bash
./.venv/Scripts/python.exe -m fitness_mcp.ingest_cli \
    --source strava_export --archive path/to/export_<athlete>.zip
```

### What the real archive taught us

Building against the actual file rather than the documented format changed the
parser substantially. **The export is localized**: the account's Strava
language decides the column headers, so a parser hard-coded to `Activity ID`
imports zero rows from a Russian export *without erroring*. Columns are
resolved through an alias table, and a missing required column is a loud
failure — a silent empty import is the one outcome that must be impossible.

Other things only the real file revealed:

* Dates are localized too — `26 июл. 2026 г., 12:12:51`, with a narrow
  no-break space (U+202F) before `г.`.
* There are **two distance columns**: `Расстояние` is kilometres with a
  *comma* decimal separator, `Дистанция` is metres with a dot. Only the metres
  column is used.
* There are **two duration columns**, elapsed and moving. `duration_s` is
  elapsed; moving time survives in `raw_json`.
* Timestamps are **UTC** despite the localized formatting. Verified against the
  data rather than assumed: activities Strava auto-names *Ночной заезд* /
  *Дневной* / *Вечерний* land in clean, non-overlapping local-hour bands after
  UTC→Almaty conversion (morning 04–10, day 13–17, evening 18–20). Had the
  values already been local, "evening" rides would sit at 13:00.

The archive is read **straight out of the zip, never extracted**, and only
`activities.csv` is touched. A Strava GDPR export also contains `logins.csv`,
`contacts.csv` and `mobile_device_identifiers.csv`, none of which belong in
this database — there is a test asserting none of it leaks into `raw_json`.

## Not built yet

* **Xiaomi export importer** — requested, ~15 working days. Format unknown
  until it lands. It carries sleep, resting HR and stress, which is what
  `recovery_metrics` and `daily_metrics` exist for.
* **Phase 2 — Cloudflare Workers + D1**, MCP over Streamable HTTP at `/mcp`,
  auth via `workers-oauth-provider`. `server.py` selects transport by env var,
  so the transport switch is configuration rather than a rewrite.
* **Phase 3 — VM push script**: outbound HTTPS only, read-only on the bot DB,
  no inbound and no firewall changes.
* **Phase 4 — Mi Fitness cloud scraping**: only on explicit request.
* **Threat model**, **runbook**, and **Xiaomi format-change recovery** are
  written when there is something deployed to threaten. Right now this listens
  on nothing.

## Cost

Cloudflare Workers + D1 free tier covers this comfortably: 100k requests/day,
500 MB per D1 database, 5M row reads/day. A few hundred workouts is a rounding
error against that, and there is no egress charge.

One thing worth being accurate about: the GCP VM's external IPv4 costs
**~$3.65/month** (`$0.005/hr`, SKU `C054-7F72-A02E`) and has since Feb 2024.
That is a cost of running the Telegram bot, not of this project — the VM needs
an external IP for outbound access to Telegram regardless, and moving MCP
hosting to Cloudflare does not remove it. A reserved static IP attached to a
running instance bills at the same rate as an ephemeral one.
