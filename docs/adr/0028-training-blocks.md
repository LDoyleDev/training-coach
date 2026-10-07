# ADR-0028: Optional 4-week strength and hypertrophy blocks

- Status: Accepted
- Date: 2026-10-07
- Deciders: Liam

## Context

Huberman's protocol alternates monthly between strength (lower reps, higher intensity) and
hypertrophy (more reps, less intensity). The app runs hypertrophy ranges only (#26). With
bodyweight work, "heavier" means a harder ladder step, not more load. Liam decided on optional
4-week blocks (D2 in `docs/specs/phase-2-decisions.md`): you choose whether to train in blocks,
and a strength block is followed by a hypertrophy block.

## Decision

- **A per-person setting**, off by default: "Train in blocks". Turning it on starts a
  **strength block** that day; blocks then alternate every 4 weeks (strength, hypertrophy, ...).
  Turning it off returns to the plan's ranges at once.
- **The block clock stops while paused:** days with the bot paused (from the settings events)
  don't count towards the 4 weeks, so a lost week never shortens a block.
- **Strength block,** for rep-counted exercises in resistance sessions:
  - the next ladder step after the current one (at the top of a ladder, the top step with a
    "3 s lowering, pause at the bottom" cue);
  - 4-8 reps;
  - 3 or 4 sets: the planned sets, raised to 3 and capped at 4.
- **Hypertrophy block, or blocks off:** the plan's ranges and sets at the current step, as today.
- **Not affected:** timed and duration exercises, and the cardio sessions.
- **Scope of history:** each workout records its block kind (`strength`, `hypertrophy`, or none
  when blocks are off; none counts as hypertrophy). Targets (ADR-0027), progression (ADR-0016)
  and personal bests (ADR-0025) look only at sessions with the same ladder step **and** block
  kind, so strength sets never become targets for hypertrophy sets.
- **Moving up** is offered in hypertrophy blocks (and with blocks off) only. The ladder state
  stays the hypertrophy step; a strength block trains one step above it without moving it.
- **Messages:** the morning message names the block ("Week 2 of 4, strength") and, before every
  resistance session, adds "about 10 minutes of warm-up first". `/settings` shows the setting and
  the current block. A retest is due at the start of each block (D4; built with the baseline
  tests, 2-A).
- No deload week for now.

## Consequences

- A migration adds the block kind to workouts and the setting (with the date blocks started) to
  user settings. Existing workouts have no block kind and count as hypertrophy.
- `domain/` gains pure block maths (block number and kind for a day, paused days excluded),
  held at 100% coverage.
- The next hypertrophy step's first session after a strength block is still a "first session"
  for bests and targets, since the strength history at that step has a different block kind.
