# ADR-0084: Progress on a shorter day, an as-many-as-you-can last set, and stepping down

- Status: Accepted
- Date: 2026-10-31
- Deciders: Liam

## Context

ADR-0082 lets a day run shorter. ADR-0016 judges "ready to move up" on every planned set at the
top of the range in the last two sessions, a missing set counting as 0, and ADR-0027 fills
missing sets from the weakest. A shortened day would then never count as ready and would drag
the dropped sets' targets down. Liam chose F2 (`docs/specs/any-level-any-time.md`, Failure): an
optional last set to failure where it is safe. And no rule today suggests a step down for
someone below the bottom of the range, which matters for people starting low (ADR-0083).

## Decision

- **A shorter day is judged on its own sets.** Ready means every set planned that day (after the
  trim) at the top of the range, in each of the last two sessions at the step. A set the trim
  dropped is neither a miss nor a 0: its next target comes from the last session in which that
  set was done.
- **Last set: as many good reps as you can.** A per-person option, off by default, offered with
  shorter sessions.
  - Only on exercises marked `failure_ok` in the catalogue: isolation and stable ones (curls,
    lateral raises, calf and tibialis raises, leg extension and curl machines, push-ups, band
    work). Never on jumps, swings, pistols, Nordics, loaded hinges, carries, neck work, ab
    rollouts or Copenhagen planks.
  - Off for a person's first 8 weeks, counted from their first logged session.
  - The set shows its usual target as a floor ("at least 10, then as many good reps as you
    can"). Its reps count for readiness and bests. ADR-0027's per-set targets mean it doesn't
    raise the other sets' targets.
- **Step down, suggested.** When two sessions in a row at a step have most sets below the bottom
  of the range (the weaker side counted), or after 21 days or more without the exercise, the app
  offers the step below with "Step down" and "Not yet", as Move up does. Nothing changes without
  the tap. No published system defines this rule; it is ours.
- **An easy start.** A new person's first two weeks run at most two sets of each exercise, then
  program-builder's Decided 7 (one set lower for four weeks) continues.
- **Effort words for levels 1 to 3:** "stop when the next rep would lose its form", not reps in
  reserve.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| F1: 1-2 reps short everywhere | Today's rule | Leaves the small gain on light, high-rep sets |
| F2: optional last set where safe (chosen) | The gain where it is real, the risk kept out | A catalogue flag and an option to explain |
| F3: failure on every last set | Simplest | Not supported for compound bodyweight moves or older people (ACSM 2026) |
| Step down automatically | No tap | Against the product rule: the person decides |

## Consequences

- `domain/progression.py` and `domain/targets.py` learn the day's planned sets; both stay pure
  and at 100% coverage.
- `plan.toml` gains `failure_ok` per exercise; settings gain the last-set option.
- The step-down suggestion sits next to Move up on the web, the bot and the weekly review.
