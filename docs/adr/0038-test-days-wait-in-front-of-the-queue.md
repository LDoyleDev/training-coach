# ADR-0038: Test days stand in front of the queue while a round is due

- Status: Accepted
- Date: 2026-10-10
- Deciders: Liam (D4, #95)

## Context

D4 decided the retest cadence (each block start with blocks on, every 4 weeks without) and
that test days go into the queue like sessions: the order is kept and everything shifts by two
days. Test days are entered in the web app (ADR-0037). The queue (ADR-0006) is a cycle of
session templates with a pointer and a short list of swapped-in sessions.

## Decision

- **A due test day stands in front of the queue; it isn't a queue entry.** `domain.retests`
  works out from the saved test days (and the block start, with blocks on) whether day 1 or
  day 2 is due on a date. While one is due it is today's plan in the morning message, the
  nudge and the week ahead, and the queue simply waits: no session is done, so the pointer
  doesn't move and every later session shifts by the days the tests take.
- **Saving the test day is what completes it.** Not doing it leaves it due the next day, so
  "push to tomorrow" needs no button. **Train <session> instead** shows the waiting session as
  Start does; doing it moves the queue as usual and the test day is still due tomorrow.
- **Cadence:**
  - day 2 is due on a later day than day 1, until it's done;
  - with blocks on, a round is due from the first day of each block (a block that starts
    while paused is due on the first day back);
  - with blocks off, a round is due 4 weeks after the last round's day 1.
- **The baseline is started by hand** from the web app's tests page. Nothing is due until a
  first test day exists, so shipping this doesn't change the schedule until Liam begins; the
  baseline's day 2 is then due like any other. The first round is named "Baseline tests", later
  ones "Retest".
- The morning message names the tests and links to `<public URL>/tests`. A test day saved today
  counts as something logged, so it silences the evening nudge.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Due test days in front of the queue (chosen) | No queue or schema change; can't get out of step with the test days saved | The week ahead simulates rounds as well as the queue |
| Test days as session templates queued by a job | Rest, swap and pick work unchanged | Templates with no exercises; a job that must run exactly once per round; the queued entry and the saved results can disagree |
| A baseline due automatically when none exists | Nudges Liam to start | Changes tomorrow's plan the moment it ships, unasked |

## Consequences

- `services.today.today` (with a time zone) and `week` carry the test day; the bot shows it.
  The web app's session page says so too (separate change).
- Rest and Swap on a test day: Rest isn't offered (not doing the tests is the rest), and Swap is
  **Train <session> instead**.
