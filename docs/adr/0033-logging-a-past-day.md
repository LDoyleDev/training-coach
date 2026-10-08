# ADR-0033: A past day is logged with a date line, and catching up moves the queue

- Status: Accepted
- Date: 2026-10-08
- Deciders: Liam (#104)

## Context

Every log was saved under the day it was sent, as the session at the queue's pointer. Liam
trained for a week while the Pi ran a version that couldn't take typed logs, and will sometimes
log a day late. Logging those days today would date everything wrong: the weekly review, bests
and the overload history all go by date.

## Decision

- **A date on the first line** makes a log for that day: `yesterday`, a weekday (the most
  recent one), `29 Sep` or `Tue 29 Sep`, `29/9` or `2026-09-29`. It must be 1 to 14 days back.
  A weekday that doesn't fit the date, a future date, or one too long ago is a problem shown
  before anything is saved. Today's date on top is an ordinary log. A weekday on its own counts
  only on a line without numbers, so "Sun salutation 5" is still a log.
- **The session** is named after the date (the longest session name or slug found on the line,
  so "Day 3 Torso + neck" works). Otherwise it is the planned session sharing the most
  exercises with the log. `<date> rest` logs a rest day, with no sets.
- **Filing** is as on the day: that date and that date's training block (ADR-0028), sets at the
  current ladder steps.
- **The queue:** when the past day is a planned session and nothing later is logged, the
  pointer moves to the session after it and any swap is dropped (`domain.queue.caught_up`).
  Catching up in date order therefore leaves the queue after the last session actually done,
  whatever order they came in. An older day logged afterwards adds history only.
- Past days aren't offered stretching (#98): that is for the end of a session just done.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A date line on the log (chosen) | One message per day; works by text and voice; the confirmation shows the day | A format to remember (in /help) |
| Buttons to pick the day after sending | Nothing to type | One more tap per log; harder to send a week at once |
| A date picker in the dashboard | Natural on a screen | The dashboard isn't built yet (D1) |
| Writing last week straight into the database | Quick once | No trail, nothing reusable |

## Consequences

- Names with a bracketed note ("Moderate cardio (~75-80% effort)") now also match without the
  note. Catching up found that the parser dropped brackets from the log but not from the plan's
  names, so the work-order list (ADR-0031) didn't read back for several sessions. Every
  session's list is now tested.
- The queue rule trusts the latest past day over the pointer. Logging a past day while a later
  one is still missing moves the queue, and the next past day moves it again.
