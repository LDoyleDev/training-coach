# ADR-0006: The plan is an ordered queue; missed sessions shift everything back

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

The weekly plan (legs, zone 2, upper, moderate cardio, legs + core, intervals, arms/rest) has
an order that matters for recovery. Liam decided: if a session is missed, the order is kept and
every later session moves back one day.

## Decision

Model the plan as a cyclic sequence of session templates with a pointer to the next session.
Each day the morning message offers the session at the pointer. The pointer advances only when
a session is logged as done or deliberately marked "rest" (a planned rest counts as done). If
the day ends with nothing logged, the pointer stays, so the same session is offered tomorrow
and everything after it shifts one day.

## Consequences

- "Today's session" is derived state, not a calendar lookup; weekday labels in the UI are
  projections from the pointer.
- The domain logic is pure and fully unit-tested (skips, rest, multiple skips, week wrap, DST).
- A "swap day" or "skip this session" action must be explicit and logged.

## Addendum (2026-11-08): rest places

A session can have rest places after it (ADR-0091): once it is done, the next days are rest days,
read from the calendar, and the pointer's session is offered after them. The pointer still names
a session and moves only as above, so a missed session still shifts everything back a day.
