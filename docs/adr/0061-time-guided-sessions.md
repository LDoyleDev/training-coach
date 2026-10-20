# ADR-0061: Time each set of a guided session

- Status: Accepted
- Date: 2026-10-20
- Deciders: Liam

## Context

Liam asked for timestamps: when a session starts, how long it takes, how long each set and
each rest lasts. Over time the app should know how long each session usually takes, because
knowing a session can be done quickly is a reason to get it done.

The guided session (D1, #117) already walks through the sets one screen at a time, with a rest
countdown between them, and keeps each confirmed set on the server (`session_progress`) so the
session resumes on any device. Nothing records when anything happened: a workout has only
`created_at`, the moment it was saved.

## Decision

**What is recorded.** For each set of a guided session, two times from the phone: when its
screen appeared (`started_at`) and when it was confirmed (`done_at`). Everything else is
worked out from them, so nothing is recorded twice:

- a set takes `done_at - started_at`;
- the rest before a set is the gap since the set before it was confirmed (the countdown, any
  "+ 15 s", or less after "Skip rest");
- a gap of more than 10 minutes is a **break** (Leave, the phone put away), not a rest, and
  doesn't count toward the session's time;
- the session runs from the first set's start to the last set's confirm, less its breaks.

A set's screen appears when Start is tapped, when a rest is skipped, when a session is resumed,
and when a rest runs out (timed from the rest's end, even if a locked phone shows it later). A set fixed with Back keeps the times of its first confirm, so a correction never
looks like a long set.

**Where it is kept.** While the session runs, with each set in `session_progress.sets` (the
same JSON that already resumes it on another device). On save, on the set's rows in
`set_logs` (`started_at`, `done_at`; both sides of a one-sided set share them), so the times
belong to the sets they time, follow them through /undo (ADR-0060) and go out in the data
export. Workouts logged any other way (text, voice, an AI's proposal, a past day, stretching)
have no times.

**Checks.** The phone's clock is trusted, since these are the person's own times, but not
blindly: a set's times are kept only when the start is before the end, neither is in the
future (a minute's slack) and both are from the last 36 hours. Times failing that are dropped
and the set is kept: a phone with a wrong clock never stops a log.

**Showing it** (#266): the saved screen says how long the session took, split into sets and
rests, plus any breaks ("Took 41 min: 22 on sets, 19 resting"). The overview before Start says
how long this session usually takes in place of the plan's estimate, and Progress lists each
timed session's usual, last and fastest time. "Usually" is the median of the session's last
five timed totals, so one slow day doesn't move it much. All are whole minutes.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Two times per set from the phone, the rest derived (chosen) | One fact each; works offline between keeps; rests include "+ 15 s" and skips as they happened | Trusts the phone's clock (checked) |
| The server stamps each set when it is kept | Server clock | Only the confirm, not when the set started; a slow network shifts every time |
| Record every screen change as an event | Every interval, even unused ones | A log of taps to store and interpret; the sets already mark each change |
| Start and end on the workout only | One row | Can't say how long sets or rests take, which Liam asked for |

## Consequences

- `set_logs` gains two nullable columns; `session_progress.sets` entries gain two optional
  keys. Old rows and old browsers keep working without them.
- The warm-up and the stretching after a session aren't timed. Stretching could record its
  own start and end later the same way.
- A session spread over two devices with different clocks gets a slightly wrong rest at the
  changeover; the break rule keeps a large error out of the total.
