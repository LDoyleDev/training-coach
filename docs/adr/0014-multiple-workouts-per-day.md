# ADR-0014: Several workouts per day

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

The data model (step 1-A) needed a rule for how many workouts a day can hold. Liam asked for
training twice in a day to be possible.

## Decision

- `workouts` has no uniqueness on `local_date`: any number of workouts per day.
- A workout with `template_id` set completes that planned session. With status `done` or
  `rest` it advances the queue by one (ADR-0006). Two planned sessions in one day advance the
  queue twice.
- A workout with `template_id = NULL` is an extra, unplanned session. It is logged and counts
  towards history and personal bests, but never moves the queue.
- The evening nudge is suppressed as soon as any workout exists for that day, whatever its
  status (`done`, `rest` or `skipped`): a deliberate skip is an answer, not an omission.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Many per day (chosen) | Matches real training; simple rows | "Today's workout" is a list, not a row |
| One per day, sets merged | Simplest queries | Loses which session a set belonged to; can't do two planned sessions |

## Consequences

- Queries for "today" return a list; the bot shows each logged session separately.
- Logging flow (1-E) asks which session a log belongs to only when it is ambiguous (default:
  the next planned session if not yet done today, otherwise an extra session).
