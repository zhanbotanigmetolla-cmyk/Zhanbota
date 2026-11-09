# iOS Shortcut → fitness-mcp

Build this in three stages and run it after each. A 40-step Shortcut built
blind is very hard to debug; a 12-step one that already works is easy to extend.

The last step of every stage is **Show Result**, so the server's reply appears
on screen the moment you run it. That reply is your debugger.

## What the server expects

```
URL     https://fitness-mcp.tail4ed987.ts.net/<SECRET-PATH>/ingest/health
Method  POST
Headers X-Ingest-Token: <YOUR-TOKEN>
        Content-Type: application/json
Body    JSON
```

Every top-level key is optional. Send only what a stage builds:

```json
{
  "workouts":      [ {"type": "...", "start": "...", "end": "..."} ],
  "sleep_samples": [ {"start": "...", "end": "...", "value": "..."} ],
  "resting_hr":    [ {"date": "...", "bpm": 48} ],
  "steps":         [ {"date": "...", "steps": 9431} ]
}
```

**Do not send `duration_s`.** The server computes it from `start` and `end`.
That is one less field to get wrong, and Shortcuts reports workout duration
inconsistently across iOS versions.

Dates: set the variable's format to **ISO 8601**. Shortcuts has that built in —
tap the inserted date variable, and under *Date Format* choose `ISO 8601`. Epoch
seconds and `DD.MM.YYYY HH:MM:SS` also work if ISO 8601 isn't offered.

---

## Stage 1 — workouts only

Shortcuts → **+** → add these in order.

**1. Find Health Samples**
- *Sample Type* → **Workouts** (RU: **Тренировки**)
- Tap **Add Filter** → *Start Date* → **is in the last** → `7` **days**
- *Sort by* → Start Date, *Order* → Oldest First

**2. Repeat with Each** — input is the result of step 1.

Inside the repeat:

**3. Dictionary** — tap **+** four times and set:

| Key | Type | Value |
|---|---|---|
| `type` | Text | *Repeat Item* → **Workout Activity Type** |
| `start` | Text | *Repeat Item* → **Start Date** (format ISO 8601) |
| `end` | Text | *Repeat Item* → **End Date** (format ISO 8601) |
| `kcal` | Number | *Repeat Item* → **Total Energy Burned** |

To pick a property: insert the *Repeat Item* variable, tap it, then choose the
property from the list. If **Workout Activity Type** isn't offered, use
**Sample Type** or **Name** — the server accepts English *and* Russian workout
names and reports anything it can't map.

**4. Add to Variable** → name it `Workouts`

(end of repeat)

**5. Dictionary**
- Key `workouts`, type **Array**, value → the `Workouts` variable

**6. Get Contents of URL**
- URL: `https://fitness-mcp.tail4ed987.ts.net/<SECRET-PATH>/ingest/health`
- *Method* → **POST**
- *Headers* → add two:
  - `X-Ingest-Token` = your token
  - `Content-Type` = `application/json`
- *Request Body* → **JSON**
- Add one field: key `workouts`, type **Array**, value → `Workouts` variable

  (If you added step 5, you can instead set *Request Body* → **File** and pass
  the dictionary. Either works; the field-by-field form is easier to fix.)

**7. Show Result** → the output of step 6.

**Run it.** You should see something like:

```json
{"ok":true,"workouts_received":4,"workouts_created":4,
 "workouts_updated":0,"daily_metrics":0,"warnings":[]}
```

Run it a **second** time. `workouts_created` should now be `0` and
`workouts_updated` should equal `workouts_received`. That is the idempotency
guarantee working — the rolling 7-day window re-sends the same workouts and
they update in place rather than duplicating.

### If something is wrong

| Response | Meaning |
|---|---|
| `401 unauthorized` | Token header missing or wrong. Check for a trailing space. |
| `400 invalid JSON` | Request Body isn't set to JSON, or a value is empty. |
| `503 ingest is not configured` | Server-side token missing — tell me. |
| `"warnings": ["unmapped Apple workout type 'X'..."]` | It imported, but under a raw name. Send me `X` and I'll map it. |
| `workouts_received: 0` | The filter matched nothing. Widen it to 30 days and retry. |

---

## Stage 2 — add sleep

Insert before step 5.

**Find Health Samples**
- *Sample Type* → **Sleep Analysis** (RU: **Анализ сна**)
- Filter: *Start Date* **is in the last** `7` **days**

**Repeat with Each** → **Dictionary**:

| Key | Type | Value |
|---|---|---|
| `start` | Text | *Repeat Item* → Start Date (ISO 8601) |
| `end` | Text | *Repeat Item* → End Date (ISO 8601) |
| `value` | Text | *Repeat Item* → **Value** |

**Add to Variable** → `Sleep`

Then add `sleep_samples` (Array → `Sleep`) as a second field in the
*Get Contents of URL* body.

The server does the aggregation: it sums the asleep intervals into nights,
attributes each night to the day you **woke up**, and splits deep / light / REM.
Samples marked *In Bed* / *В постели* and *Awake* are excluded, so time spent
falling asleep doesn't inflate the total. Unfamiliar stage names still count as
sleep rather than being dropped.

---

## Stage 3 — add resting heart rate and steps

**Find Health Samples**
- *Sample Type* → **Resting Heart Rate** (RU: **Пульс в покое**)
- Filter: last `7` days

**Repeat with Each** → **Dictionary**:

| Key | Type | Value |
|---|---|---|
| `date` | Text | *Repeat Item* → Start Date (ISO 8601) |
| `bpm` | Number | *Repeat Item* → **Value** |

**Add to Variable** → `RestingHR`, then add `resting_hr` (Array) to the body.

Steps work the same way — *Sample Type* **Steps** (RU: **Шаги**), keys `date`
and `steps`. Steps are per-sample rather than daily totals, so the last sample
of a day wins; treat that figure as approximate.

---

## Running it

Apple blocks HealthKit while the phone is locked, so this cannot run reliably on
a timer. Two options that respect that:

- **Automation → When I unlock my iPhone**, with *Run Immediately* and *Notify
  When Run* off. It will fire often; that is harmless because re-sends update
  rather than duplicate.
- **Back Tap** (Settings → Accessibility → Touch → Back Tap → Double Tap →
  your Shortcut) when you want to push manually after a workout.

The 7-day window means missing a run costs nothing — the next one backfills.

## Verifying it end to end

**On the phone**, the Show Result step already tells you. Run twice: the second
run should report `created: 0`, `updated: N`.

**From Claude**, once a run has landed, ask:

> "List my workouts from the last 3 days and tell me which source each came from."

Sessions from the phone appear with source `apple_health`. Then:

> "What was my resting heart rate and sleep over the last week?"

**From this machine**, if you want certainty:

```bash
ssh -i ~/.ssh/id_ed25519_claude nigmetolla_zhanbota@35.226.20.162 \
  "~/.venv-fitness-mcp/bin/python -c \"
import sqlite3
c=sqlite3.connect('/home/nigmetolla_zhanbota/data/fitness-mcp/fitness.db')
c.row_factory=sqlite3.Row
for r in c.execute('''select local_date, sport_type, duration_s, kcal
                      from workouts where source=\\\"apple_health\\\"
                      order by started_at desc limit 10'''):
    print(dict(r))
\""
```

Server-side logs for a failed run:

```bash
ssh -i ~/.ssh/id_ed25519_claude nigmetolla_zhanbota@35.226.20.162 \
  "journalctl --user -u fitness-mcp.service -n 40 --no-pager | grep -i ingest"
```

## Two things worth knowing

**Overlap with the watch.** Your Xiaomi data is historical, ending 2026-07-26;
Apple Health is live from 2026-07-27, so they barely meet. If they ever do —
say you import a newer Xiaomi export — the Xiaomi record wins, because it
carries HR zones and training load that HealthKit does not expose. Nothing is
deleted either way; the loser is marked superseded and can be restored.

**Your token is a password.** It sits in the Shortcut and in
`~/.env.fitness_mcp` (mode 600) on the server. Anyone holding it *and* the
secret URL path can write to your database. If either leaks, tell me and I'll
rotate both.
