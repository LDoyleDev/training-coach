# ADR-0091: Rest places in the queue, kept as rest days after a session

- Status: Accepted
- Date: 2026-11-08
- Deciders: Liam (rest places in the queue: `any-level-any-time.md` S1, Decided 9, 8 Nov 2026);
  how they are stored follows from it
- Changes: ADR-0006 (addendum there)

## Context

The new starters run 2, 3 or 4 sessions a week (`any-level-any-time.md` S1). The queue offers its
next session every day (ADR-0006), so a 3-day queue of A, B and C would offer B the day after A,
and the body map would count A, B, C as three days running. Liam decided on 8 Nov 2026 that rest
days are places in the queue: A, rest, B, rest, C, rest, rest for the 3-day; A, rest, rest, B,
rest, rest, rest for the 2-day; Lower 1, Upper 1, rest, Lower 2, Upper 2, rest, rest for the 4-day.
The queue still offers its next place every day, a missed session still moves everything back a
day, and the map counts days correctly. Offering sessions only on tapped weekdays was turned down.

A rest place differs from a session in one way that matters: nobody logs it. If the pointer
stopped on a rest place, something would have to move it on at the end of its day, or it would
wait like a missed session.

## Decision

**A session carries its rest places: `session_templates.rest_after`, 0 to 6.** The 3-day is A
(1), B (1), C (2); the 2-day A (2), B (3); the 4-day Lower 1 (0), Upper 1 (1), Lower 2 (0),
Upper 2 (2). In `plan.toml` a session says `rest_after = N`. Every existing session has 0.

**The pointer never stops on a rest place.** It names a session, as before, and moves only when
that session is done or rested (ADR-0006). The rest days are read from the calendar: after the
planned session done last (by date, then by when it was logged), the next `rest_after` days are
rest days, and the pointer's session is offered from the day after them. If it isn't done that
day, it is offered again the next, so a missed session still shifts everything after it. Nothing
is written when a rest day passes. The rule is `domain.queue.rest_days_left`.

**Every reader of "today" says it in plain words.** On a rest day the guided session has no
session (`GET /api/session/today`: `session` empty, `rest_day` the next session),
the web page says "Rest day. No session planned today. Next: B.", the home button reads "Today:
Rest day", the morning message says "Today: rest day. No session planned. Next: B." with no Start,
Rest or Swap buttons, the evening nudge stays quiet, the daily check offers no "Rest today", the
week ahead gives each rest place its day, and the AI summary adds "Today is a rest day." The
person can still train: a session picked for today, or a typed log, counts as usual, and doing the
pointer's session on a rest day moves the queue on.

**The body map counts a rest place as a day with no training:** two sessions with a rest place
between them aren't "two days running" for the back-to-back warning.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A rest count on the session before it (chosen) | One column, default 0, so the owner's 7-day cycle is unchanged; the pointer still always names a session, so every reader of the queue (logs, buttons, swap, pick, undo) works as it did; nothing written when a day passes | A queue can't start on a rest place: the walk-through, which sets where the queue starts from the tapped days, needs a start date of its own if today should be a rest day |
| Rest places as rows in the queue (a session of kind "rest" with no items) | Literally a place in the queue | Every list of sessions (Plan page, Log page, pick menu, coverage, progress, export) would have to skip them; the pointer would wait on one until something moved it at day end: a scheduled write, or a pointer date stored and kept right by every writer |
| Sessions only on the tapped weekdays | Matches a calendar | A second rule beside the queue; a missed Monday waits until Wednesday. Turned down by Liam |

## Consequences

- A migration adds `session_templates.rest_after` (not null, default 0, 0 to 6). The release
  changes the live schema; no row's data changes, so the owner's queue behaves as before.
  Downgrading drops the column.
- The import (`plan_import`) shows a change to a session's rest days like any other.
- The weekly review still counts the sessions in the cycle as the week's plan: a starter's cycle,
  sessions and rest places together, is 7 days.
- Follow-ups: the starters in the seed with their rest places (S1); the walk-through may need a
  start date so a queue can begin on a rest day.
