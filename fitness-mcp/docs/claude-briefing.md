# Briefing for Claude (paste into claude.ai)

Paste everything below the line into a new claude.ai conversation once the
`fitness` connector is added. It gives Claude the context the tool descriptions
alone cannot: where the data came from, what the gaps mean, and which numbers
are easy to misread.

The connector URL is deliberately **not** included — the connector already
holds it, and its secret path should not be pasted into chat history.

---

I've connected a custom MCP connector called **fitness** that exposes my own
training data. Before answering questions with it, read this — several fields
are easy to misinterpret, and a couple of the traps produce confident wrong
answers rather than obvious errors.

## Where the data comes from

Five sources merged into one database, plus daily wellness and health data.
Every workout carries the `source` it came from, and every tool takes an
optional `source` filter, so any of them can be reported on alone or combined.

**Xiaomi / Mi Fitness export** (`xiaomi_export`, 238 workouts) — from my watch.
The richest source and the only one going back to mid-2025. Carries heart rate,
calories, distance, elevation, and all the sleep / resting-HR / stress data.

**My Telegram pull-up bot** (`pullup_bot`, 80 sessions) — a calisthenics tracker
I built. The **only** source with set-level detail: individual rep counts per
set, plus RPE. Started 2026-03-29.

**Hevy** (`hevy_export`, 103 sessions, 2022-12-09 to 2026-04-26) — my gym
logbook: barbell, dumbbell and machine work, set by set with real loads. This
is a **second, separate training modality**, not a duplicate of the pull-up bot
and not a replacement for it. It is also the only source that goes back before
mid-2025.

**Apple Health export** (`apple_health_export`, 96 visible) — the full HealthKit
archive from my iPhone and Apple Watch. Originally 133 sessions; 37 were the same
rides already held by Xiaomi or Strava and were merged into them. It is the
**only** source covering 2026-07-27 onward — the Xiaomi and Strava exports both
stop at 2026-07-26 — so it is what fills the recent weeks.

It also carries **52 daily health metrics across 307 days**, which is everything
the other sources never had: body mass, body fat, VO2 max, HRV, blood oxygen,
respiratory rate, energy burned, walking gait, mindful minutes. Reach these with
`list_health_metrics` first, then `health_metrics` — the names must match
exactly.

**Strava bulk export** (`strava_export`, 4 visible) — originally 129 activities,
but **125 turned out to be the same sessions as Xiaomi records**, matching
within 0–1 seconds, because Strava was being fed from the watch. Those were
merged into their Xiaomi rows. Only 4 are genuinely Strava-only. This is
expected and correct — do not report it as missing Strava data.

## The traps, in order of how badly they mislead

**"0 reps" before March 2026 does NOT mean no strength training.** Rep counts
only exist where the bot recorded them, and the bot started 2026-03-29. In 2025
I was doing plenty of strength work — Xiaomi logged 88 `strength` and 20
`high_bar` sessions — it just wasn't counted rep by rep. Never conclude I
stopped training or "had no strength phase" from a zero rep count.

**`null` never means zero.** It means that source never recorded the field.

**`estimated_1rm` and `best_set_by_weight` are null for the *bodyweight*
work only.** Bot-sourced pull-ups, push-ups and dips carry no external load, so
a null there is an absence of data, not a weakness and not a missing PR — don't
estimate a 1RM from bodyweight. Hevy-sourced lifts *do* carry loads and return
real numbers. Which one you are looking at is in `source`.

**Weighted and bodyweight versions of a movement are separate exercises.**
`pullups` (bot, bodyweight, up to 20 in a set) and
`подтягивания (с утяжелителем)` (Hevy, with added weight) are the same movement
but deliberately not merged, because merging would wreck both the rep records
and the 1RM. Hevy exercise names are Hevy's own, mostly Russian and lowercased;
bot names are short English ones.

**Added weight is not total weight.** On weighted bodyweight movements
`weight_kg` is the load *added* to me. "+15 kg × 3" is right; "a 15 kg
pull-up" is not.

**`total_reps` mixes modalities.** Once Hevy is included, a bodyweight pull-up
rep and a loaded squat rep both count as one rep. It is a volume proxy, not a
load measure. Filter by `source` if that distinction matters.

**`sessions` and `training_days` are different.** I log up to six cycling
commutes in a day: 6 sessions, 1 training day. Use `training_days` for "how
often do I train".

**`duration_s` means different things by source.** Xiaomi reports *active* time
(paused time excluded); Strava reports *elapsed*. Fine for trends, but don't
present cross-source duration comparisons as precise.

**`hr_distribution` is not measured time-in-zone.** The data has one average and
one max HR per session, not a time series, so each session's whole duration is
attributed to the single zone its average falls in. Zones are fractions of the
highest max HR observed (191 bpm), not a lab-measured max. Say so if you quote it.

**Stress covers only 69 of 390 days.** The band samples it in specific modes
only. Sparse stress data is a sensor limitation, not a sign of anything.

**The wearable changed on 2026-07-26, and resting HR jumps because of it.** Mi
Band figures run to that date, Apple Watch figures from 2026-07-27. Resting HR
reads roughly 10 bpm higher on the Apple Watch, so `recovery_metrics` over any
range crossing that date reports a "worsening" trend that is a hardware change,
not my recovery. Check the `sources` field on the day rows and compare within
one device, not across the switch.

**A metric starting late means I didn't own the sensor yet.** Steps go back to
2025-11-05 from the iPhone, but heart rate, sleep, VO2 max and HRV only start in
late July 2026 when the Apple Watch arrived. That is equipment history, not a
habit that suddenly began. Same for the 8 days of dietary data in Jan-Feb 2026 —
I tried a food logger briefly and stopped.

**Never read an absent day as a zero in `health_metrics`.** Days with no
readings are simply missing from `days`. A day the watch spent on the charger is
not a day I took no steps.

**Respect `kind` before quoting a health metric.** `cumulative` metrics
(step_count, active_energy_burned) mean the daily `total`. `discrete` ones
(heart_rate, body_mass, vo2_max) mean `avg`/`min`/`max`, and their `total` is
deliberately null — summing 300 heart-rate readings is not a number.

## Useful things to know

`sport_type` values: `running`, `cycling`, `strength`, `high_bar`, `walking`,
`swimming`, `workout`, `pingpong`, `tennis`, `horse_riding`. **`high_bar` is
pull-up bar work** recorded by the watch — it's kept separate from `strength`
deliberately, and it overlaps with what the bot tracks rep by rep.

Dates are local calendar dates in **Asia/Almaty**, `YYYY-MM-DD`, both ends of
every range inclusive.

Sleep is attributed to the day I **woke up**. `recovery_metrics` reports a
trend comparing the first half of a range against the second — it's a plain
two-halves comparison, not a regression, so don't present it as statistics. A
*falling* resting heart rate means improving recovery.

Recent shape of things, for grounding:

| Month | Sessions | Training days | Reps | Duration | Distance |
|---|---|---|---|---|---|
| 2026-03 | 13 | 8 | 996 | 17.9 h | 2.4 km |
| 2026-04 | 35 | 23 | 1,800 | 16.3 h | 31.4 km |
| 2026-05 | 45 | 23 | 1,474 | 18.9 h | 75.3 km |
| 2026-06 | 49 | 24 | 1,683 | 13.9 h | 79.2 km |
| 2026-07 | 79 | 27 | 2,673 | 47.9 h | 438.0 km |
| 2026-08 | 73 | 23 | 923 | 51.0 h | 550.4 km |

Records: **20 pull-ups** in one set (2026-06-21) and **56 push-ups**
(2026-07-05). Biggest day was 2026-07-10 — 300 pull-ups over 33 sets *and* 600
push-ups over 31 sets.

Resting HR and sleep must be quoted with the device in mind. Over Aug-Sep 2026
(Apple Watch) resting HR averages about **59 bpm** and sleep about **7.2 h**.
The older Mi Band figures average about 48 bpm — that gap is the two devices
measuring differently, not a decline. Do not compare across 2026-07-26.

August 2026 shows high duration and distance with low reps: that is a genuine
shift toward cycling and running, not missing strength data.

## Known data quirks

- One corrupted row: 2026-04-05 pull-ups says `completed=40` but its sets sum to
  80, with a UI button label leaked into notes. The set breakdown is used.
  Treat that day's total as uncertain.
- Sets flagged `inferred: 1` were reconstructed from a session total. They count
  toward volume but are excluded from single-set records. There is exactly one,
  on 2026-04-07.
- Bot sessions and Xiaomi sessions are **not** merged even on the same day —
  the bot has reps, the watch has heart rate, and merging would discard one.
  Some days legitimately show both.
- Bot data syncs hourly; Xiaomi, Strava, Hevy and Apple Health are manual
  imports. Hevy is re-exported roughly weekly and re-imported over itself,
  which is safe.
- Apple's cumulative daily metrics (steps, distance, energy) are taken from the
  single device that recorded the most that day, because HealthKit stores the
  iPhone's and the Watch's overlapping copies of the same walk. This matches
  the Health app closely, but a day split across two devices can read slightly
  low. Never add two devices' figures together.
- The Apple archive's ECG recordings and GPS workout routes are not imported.
- Hevy sessions carry **no heart rate at all** and their `duration_s` is elapsed
  gym time including rest between sets, so they inflate `sessions_without_hr`
  in `hr_distribution`. That is missing coverage, not a change in training.
- A Hevy session's `distance_m` is only whatever a cardio machine inside that
  session recorded (a treadmill warm-up), not distance covered training.
- Warm-up sets are labelled by Hevy and are excluded from personal records — a
  light ramp-up set is not an attempt at a best effort.
- A watch record and a Hevy record of the same gym session are **not** merged,
  for the same reason bot and watch records are not: only one of them knows
  what was lifted.

## What I'd like from you

Use the tools rather than guessing, prefer `training_summary` over pulling every
workout and summing it, and when a number is absent say so plainly instead of
substituting zero. If something looks contradictory, tell me — a couple of the
quirks above are real bugs in my own bot, and I'd rather find more.
