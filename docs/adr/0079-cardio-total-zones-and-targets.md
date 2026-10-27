# ADR-0079: All cardio counts, split by heart-rate zone, against targets from the plan

- Status: Accepted
- Date: 2026-10-27
- Deciders: Liam

## Context

Liam's week of 20-26 Oct 2026: on Thursday "Cardio + core", a 43-minute run typed as moderate
cardio (the band showed an average of 139 bpm, but no heart rate was stored then: it was before
the reader). On Monday "Long zone 2", a 66-minute band walk (average 124, held 137) he counted
with Count it. ADR-0055 logged a counted import as its zone 2 minutes, so the workout held 35
minutes of zone 2 and the other 31 showed nowhere. The totals counted only zone 2 and moderate
by what was logged, and the zone 2 target was 180-200 minutes a week from `plan.toml`, which
two cardio sessions a week can't reach.

Liam (26-27 Oct): count all the cardio over the last 7 days and show how much of it was in
each zone; show what is left of each target; and set the targets from the plan's sessions and
the time a person has, not from one fixed number.

## Decision

- **All cardio counts in the total**, over the last 7 days (ADR-0077): every zone 2 and
  moderate-cardio log in a done workout. HIIT logs rounds and has no window of time, so it
  stays out (`services/cardio_totals.py`).
- **The total is split by zone**: below zone 1 ("easy"), zones 1-5 (ADR-0055's Karvonen bands)
  and "zone 3+ (no heart rate)". Minutes with heart rate split by each minute's zone, from the
  per-minute samples kept for the workout's window (`domain.zones.measured`, the same rule as an
  import's zone minutes: a reading lasts until the next, at most 5 minutes), with the person's
  zones as they are now. Minutes without heart rate count in the zone the person picked when
  logging (ADR-0067): zone 2 as zone 2, moderate as zone 3+. Nothing is re-classified: a log
  keeps its kind, the split only says what the heart rate showed.
- **A workout's window**: a counted import's start and end; a typed log with a start (ADR-0067)
  runs from its start for its minutes, so a walk logged by hand splits too when the band was
  worn. Once the samples are gone (8 days), a counted import splits by its stored zone minutes,
  the rest below zone 1.
- **A counted band workout counts its full minutes** (amends ADR-0055's "logged as its zone 2
  minutes"). Stored data is not rewritten: a workout linked to an import
  (`imported_workouts.workout_id`) takes its minutes and window from the import, so Monday's
  walk shows 66 minutes, 35 of them in zone 2. **Count it now logs the whole walk** (66, not
  35), as a typed walk logs its minutes, so the log, the day list, personal bests (a zone 2
  "best" is a session's minutes), the weekly review and what a connected AI reads all say the
  same; the zone 2 figure everywhere comes from the split. When a walk is offered is unchanged:
  with heart rate, only when it holds at least 5 minutes of zone 2.
- **Zone 2 minutes are the split's zone 2** everywhere they are shown: the Cardio page, Home's
  card, Telegram's "Counted." reply and the weekly review (which stays Monday to Sunday).
  Moderate stays "logged as moderate".
- **Targets come from the plan plus the person's extra cardio** (`domain.cardio.targets`, read
  in one place, `cardio_totals.targets`). The zone 2 target is the sum of the cycle's zone 2
  prescriptions (sets x the minutes range: Long zone 2, 45-75 today); the total target is the
  sum of all the cycle's cardio in minutes (zone 2 45-75 plus moderate 30-40: 75-115). They are
  worked out from the session templates, so a plan change moves them.
- **Extra cardio a week** (`settings.extra_cardio_min`, 0-600, default 0): walks or rides
  outside the sessions, set on the Plan page (none, 30, 60, 120 or a number). It is easy cardio
  by nature, so it adds to both targets.
- **What's left** is the minutes to the low end of each range; inside the range is "on target",
  and over it is fine, never a warning.
- `[targets] zone2_minutes = [180, 200]` is gone from `plan.toml` and the seed. 180-200
  (Huberman's Foundational Fitness Protocol, Nov 2022) is now the long-term idea a person
  reaches with extra time, not the default (`docs/specs/training-plan.md`).

With his real week and no extra: cardio 109 of 75-115 minutes (on target), zone 2 35 of 45-75
(10 left).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Split from heart rate, the rest by the kind picked; targets from the plan plus extra (chosen) | Every minute counts once; the person's pick stands where there is no heart rate; targets fit the plan | Zone figures move a little as resting heart rate moves the zones |
| Rewrite old counted workouts to their full minutes | One source of minutes | Changes stored data; Liam chose not to |
| Keep logging zone 2 minutes only, add the rest from the import | Old and new logs alike | The log says 35 for a 66-minute walk; bests and the AI see the short figure |
| Re-classify a log by its heart rate | Kinds match the heart rate | The app would decide; Liam: it observes and suggests, the person decides |
| A fixed target in `plan.toml` (240 total, 180-200 zone 2) | Simple | Out of reach on two cardio sessions; doesn't follow the plan or the person's time |

## Consequences

- API: the Cardio week (`WeekView`) and Home's week gain the total, both targets, what's left
  of each and the zone minutes (`ZonesView`); Settings gains `extra_cardio_min`. A migration
  adds the column (default 0).
- The weekly review's zone 2 figure is the split's, so a past week whose typed zone 2 logs had a
  start and heart rate can read lower than before.
- Every reader of a cardio set's minutes takes a counted import's full minutes
  (`cardio_totals.counted`): the totals, Home's list, the day view, personal bests and the
  Progress trend (so Telegram's /progress), what a connected AI reads (the summary and an
  exercise's history over MCP), the day-clash question and the share picture.
- The web shows the total, the zone rows and the Plan page's extra cardio setting (the web PR).
