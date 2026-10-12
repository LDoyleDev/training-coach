# ADR-0057: A pace setting for how big a step the targets take

- Status: Accepted
- Date: 2026-10-12
- Deciders: Liam

## Context

ADR-0027 set each set's next target to its last value plus a step of about 10% of the top of
the range. It left a pace setting for later: some people want smaller steps they always hit,
others bigger ones. `docs/specs/phase-2-decisions.md` section 1 sketched three paces.

## Decision

A per-person setting, **pace**, with three values. It changes only the step:

| Pace | Reps | Timed | Duration (cardio) |
| --- | --- | --- | --- |
| Steady | +1 | +5 s | +1 min |
| Standard (default) | ADR-0027: 10% of the range top, halves up, at least 1 | 10%, whole 5 s, at least 5 s | +1 min |
| Fast | the standard step, at least 2 | the standard step, at least 10 s (whole 5 s) | +2 min |

Examples: 5-12 pull-ups, last 8/7/6/5 -> steady 9/8/7/6, standard 9/8/7/6, fast 10/9/8/7.
15-25 tibialis, last 18/16/15 -> steady 19/17/16, standard and fast 21/19/18.

- **Everything else is ADR-0027 unchanged:** per set from what you did, a miss holds the target,
  two misses ease to last value + 1, never above the top of the range, no history means the
  bottom of the range, and the move-up rule (ADR-0016, ADR-0025) is the same.
- **Stored** in the person's settings row (`settings.pace`), standard by default; the migration
  gives every existing person standard, so nothing changes until they choose.
- **Changed** on the web (Account, "Messages and settings": three buttons, each with one line
  saying what it means) and in the bot's /settings (a row of three buttons), like the other
  training setting there, training blocks.
- **Applies everywhere targets appear:** all of them come from `services/today.session_plan`,
  which reads the pace once per session and passes it to `domain/targets.targets`. The session
  page, the guided session, the bot's morning message and /today use it. The weekly review
  shows no per-set targets, so it has nothing to change.
- **Past targets are replayed at today's pace.** A miss is judged against the target the
  current pace would have given, since nothing but the logged sets is stored (ADR-0027). After
  a change of pace, a set that was hit at the old pace can count as a miss at a faster one for
  one session; it holds, then steps again.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Three named paces in settings (chosen) | One choice, easy to explain; the domain stays a small table | No per-exercise control |
| A pace per exercise | Fine control | Many settings for a one-person app; nobody asked |
| Store the pace each target was given | Exact replay after a change | A new column on every set for a rare edge; ADR-0027 avoided storing targets |

## Consequences

- `domain/targets.py` takes a `Pace` (default standard), keeping existing callers and tests
  valid; its table-driven tests cover each pace and stay at 100%.
- `/api/settings` gains `pace` (read and change); dashboard API types regenerated.
- A change of pace takes effect at the next targets shown; nothing is recomputed or stored.
