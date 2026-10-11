# ADR-0051: Changing today on the web: Rest, Push, Swap and Undo

- Status: Accepted
- Date: 2026-10-11
- Deciders: Liam

## Context

Rest today, Swap, Push to tomorrow and `/undo` existed only in Telegram (ADR-0022, ADR-0048).
The web app is the main surface, so a day must be runnable from either one alone
(ux-flow-plan C2, C3). Two gaps showed up when the web used the same services:

- After Rest today or Push on a normal session, the queue keeps pointing at it (it waits a
  day, ADR-0006), so the web's Today still showed it as today's session.
- After "Pick another session", the web shows the picked one, and the bot's rule that the
  offered session can't be picked left no way back to the planned one that day.

## Decision

- New owner-only routes under `/api/today` (`rest`, `push`, `next`, `choices`, `pick`, `undo`)
  call `services/queue_actions.py` and `services/undo.py`, the same as the bot's buttons and
  `/undo`. Each change names the session the page shows; a different one now is a 409, and
  nothing changes. Each answer carries the new Today and what Undo would take back.
- A session held for tomorrow today (a `skipped` workout from Rest today or Push) means there is
  nothing left to guide today (`guided.today` returns none), whichever surface held it. Typed
  and voice logs keep their rule (`workout_log.target`).
- Picking the offered session itself is allowed: it takes back an earlier pick that day.
  "Do the next one first" is offered only while the page shows the planned session.
- Undo on the web works like `/undo`: "Undo: <what>", then a confirm tap, sending the change's
  event id so an old page can't take back a newer change.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Same services, new thin routes (chosen) | One rule set for both surfaces; existing tests cover the logic | A small change to `guided.today` and `pick` |
| Web-only queue logic | Free to differ | Two sets of rules that drift; the bot and web disagree |

## Consequences

- A rest or push from Telegram empties the web's Today too, and the other way round.
- Undo on the web is offered right after a change or a saved log (guided or cardio).
- Tests: `tests/api/test_change.py`, `frontend/src/session/ChangeToday.test.tsx`.
