# Briefing for Claude (paste into claude.ai)

Paste everything below the line into a new claude.ai conversation once the
`fitness` connector is added. It gives Claude the context the tool descriptions
alone cannot: where the data came from, what the gaps mean, and which numbers
are easy to misread.

The connector URL is deliberately **not** included — the connector already
holds it, and its secret path should not be pasted into chat history.

---

I've connected a custom MCP connector called **fitness** that exposes my own
training data. Before answering questions with it, read this — it covers things
the tool descriptions don't, and several fields are easy to misinterpret.

## What the data is

Two sources, merged into one database:

**My Telegram pull-up bot** (`source: pullup_bot`) — a calisthenics tracker I
built. 80 sessions, 2026-03-29 to 2026-07-24, 6,818 total reps across pull-ups,
push-ups, dips and squats. This is the only source with **set-level detail**:
individual rep counts per set, plus RPE.

**Strava bulk export** (`source: strava_export`) — 129 activities, 2025-12-25 to
2026-07-26: 46 runs, 36 strength sessions, 21 rides, 11 workouts, 11 walks,
4 swims. This is the only source with **duration, distance, heart rate and
calories**. It has no set-level data at all.

Combined monthly picture:

| Month | Sessions | Training days | Reps | Duration | Distance |
|---|---|---|---|---|---|
| 2025-12 | 5 | 3 | 0 | 6.2 h | 22.9 km |
| 2026-01 | 9 | 8 | 0 | 15.1 h | 20.0 km |
| 2026-02 | 12 | 10 | 0 | 16.3 h | 3.1 km |
| 2026-03 | 8 | 8 | 125 | 12.3 h | 0.0 km |
| 2026-04 | 31 | 23 | 1,281 | 11.8 h | 29.0 km |
| 2026-05 | 45 | 23 | 1,474 | 19.2 h | 75.3 km |
| 2026-06 | 49 | 24 | 1,683 | 14.1 h | 78.8 km |
| 2026-07 | 50 | 22 | 2,255 | 31.7 h | 253.6 km |

Personal records: **20 pull-ups** in a single set (2026-06-21) and **56 push-ups**
(2026-07-05). My biggest day was 2026-07-10: 300 pull-ups across 33 sets *and*
600 push-ups across 31 sets.

## How to read the numbers

These matter more than they look:

**Dates are local calendar dates in Asia/Almaty**, format `YYYY-MM-DD`, and both
ends of every range are inclusive. Timestamps are stored UTC internally, but
every query filters on the local date — the question is which day I trained.

**`null` never means zero.** It means the source never recorded that field. A
null duration on a bot session means the bot doesn't track duration, not that
the session was instantaneous.

**`sessions` and `training_days` are different numbers.** I sometimes log six
separate cycling commutes in one day. That's 6 sessions and 1 training day. Use
`training_days` for "how often do I train", `sessions` for "how many activities
are recorded". Don't treat a high session count as high frequency.

**`estimated_1rm` and `best_set_by_weight` are null for everything.** All my
strength work is bodyweight — no external load was ever recorded. This is an
absence of data, not a weakness and not a missing PR. Do not describe it as a
gap in my training, and do not try to estimate a 1RM from bodyweight. For
bodyweight work the real records are `best_set_by_reps` and
`best_session_total_reps`.

**`hr_distribution` is an approximation, not measured time-in-zone.** The data
has one average and one max HR per session, not a heart-rate time series, so
each session's whole duration is attributed to the single zone its average falls
in. Zones are fractions of the highest max HR observed (191 bpm), not a true
max. If you quote these numbers, say what they are.

**`recovery_metrics` returns empty.** Resting HR, sleep and stress come only
from a Xiaomi export I've requested but haven't received. Empty means **no data
source is connected** — it does not mean poor recovery, bad sleep, or an
elevated resting heart rate. Don't infer anything from the absence.

**Sets flagged `inferred: 1`** were reconstructed from a session total when the
per-set breakdown was missing. They count toward volume but are excluded from
single-set records, so they can't fake a PR. There is exactly one, on 2026-04-07.

## Known quirks in the data

- **Strength work is split across both sources.** The bot has my reps; Strava
  has duration, HR and calories for what is often the same workout. On 6 days
  both recorded the same session, and they are deliberately **not merged** —
  merging would suppress one side's data. Those days count as 2 sessions.
- **One corrupted row**: 2026-04-05 pull-ups says `completed=40` but its sets sum
  to 80, and a UI button label leaked into its notes. The set breakdown is used
  as the source of truth. Treat that day's total as uncertain.
- **The data is a snapshot as of 2026-07-26.** New bot workouts won't appear
  until an automatic sync is added. Strava and Xiaomi are manual imports by design.

## What I'd like from you

Use the tools rather than guessing, prefer `training_summary` over pulling every
workout and adding it up, and when a number is absent say so plainly instead of
substituting zero. If something looks contradictory, tell me — a couple of the
quirks above are real bugs in my own bot, and I'd rather find more of them.
