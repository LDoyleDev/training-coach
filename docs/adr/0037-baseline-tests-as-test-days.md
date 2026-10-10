# ADR-0037: Baseline tests are test days, defined in plan.toml, entered in the web app

- Status: Accepted
- Date: 2026-10-10
- Deciders: Liam (#74, #94)

## Context

Phase 2 needs baseline tests and retests (2-A): the product spec's performance tests over two
days, retested at the start of each block or every 4 weeks (D4), under recorded conditions so
results compare. The phase 2 overview planned a Telegram `/baseline` walk-through, written
before the web app became the main surface (ADR-0035).

## Decision

- **Definitions in `plan.toml`** (`[[tests]]`): slug, name, day (1 or 2), unit (reps, seconds,
  metres, cm), per side or not, and a cue that says how to do it the same way each time. Read
  from the bundled plan like stretches (ADR-0032), not stored. Results name a test by slug, so
  the seed refuses a plan that drops a test with results; its name and cue can change.
- **A test day is one row** (`test_days`, per person, ADR-0029): date, which day, the
  conditions (time of day, fed or fasted, slept well) and the results as a JSON list of
  `{test, side, value}`. A day is read and compared whole and has at most a dozen results, so
  a child table would add joins and ownership checks for nothing.
- **Checked before saving** (`domain.fitness_tests`): every result is a test of that day, done
  per side or not as defined (both sides, or skip it), once, within its unit's range. A test
  can be skipped; a day with nothing done isn't saved. Up to 14 days back, as past-day logs
  (ADR-0033). A token makes a repeated Save return the saved day.
- **Entered in the web app**, not Telegram (ADR-0035): one test at a time, with the
  conditions first, nothing saved until Save (ADR-0007). `/api/tests` serves the definitions,
  saves a day and lists them.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Test days with JSON results (chosen) | One row per day; whole-day reads; small | Comparing one test across days reads every day (a few dozen rows at most) |
| A results table, one row per test and side | Queries per test | Joins and a second ownership check, for a handful of rows |
| Tests as exercises in workouts | Reuses logging | Tests aren't training: they'd count as volume and move targets |
| `/baseline` in Telegram | Works without the web app | Ten typed answers in a chat; ADR-0035 moved new features to the web |

## Consequences

- Retest scheduling (#95) puts test days in the queue; the comparison view (#96) reads
  `test_days`. Measurements and photos stay 2-B.
