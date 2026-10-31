# ADR-0084: Progress on a shorter day, an as-many-as-you-can last set, and stepping down

- Status: Accepted
- Date: 2026-10-31
- Deciders: Liam

## Context

ADR-0082 lets a day run shorter. ADR-0016 judges "ready to move up" on every planned set at the
top of the range in the last two sessions, a missing set counting as 0, and ADR-0027 fills
missing sets from the weakest (`domain/targets.py` `_performed`). Re-running the trim later
can't say what a past day planned (the pace factor and the plan drift), so a shortened day would
never count as ready and would drag the dropped sets' targets down. Liam chose F2
(`docs/specs/any-level-any-time.md`, Failure): an optional last set to failure where it is safe.
And no rule today suggests a step down for someone below the bottom of the range, which matters
for people starting low (ADR-0083).

## Decision

- **The saved workout records its plan:** per exercise, the number of sets planned that day and
  which set, if any, was the last set to failure (a JSON map on `workouts`). Workouts saved
  before this have no map and keep today's rules.
- **A shorter day is judged on its own sets,** and ships with ADR-0082's trim.
  - **Readiness:** every set planned that day at the top of the range, in each of the last two
    sessions at the step. A day counts only if it planned at least two sets of the exercise,
    or every set when the prescription has fewer (a 1-set hang or neck exercise); "the last
    two" are the last two days that count, so a 1-set day neither blocks nor helps. A day
    that planned more sets than today's prescription is judged on all it planned.
  - **Targets:** a set the day didn't plan is neither a miss nor a 0: it isn't replayed for that
    session. A set that comes back after being dropped starts from the next target of the last
    set that day planned (the nearest set before it), as ADR-0072's built rule does for loads,
    with its miss count reset; its baseline is the first session at the step that planned it.
- **Last set: as many good reps as you can.** A per-person option, off by default, offered with
  shorter sessions.
  - Only on exercises marked `failure_ok` in the catalogue: isolation and stable ones (curls,
    lateral raises, calf and tibialis raises, leg extension and curl machines, push-ups, pull-ups
    stopping at the first rep that isn't full, band work). Never on jumps, swings, pistols,
    Nordics, loaded hinges, carries, neck work, ab rollouts or Copenhagen planks.
  - Locked while a person is new: until they have trained 8 weeks, or always at level 3 or
    below (ADR-0083).
  - The set shows its usual target as a floor ("at least 10, then as many good reps as you
    can"). Its reps count for readiness and bests. For that set's own next target it counts as
    its target met, so one big set doesn't set a target the next ordinary day can't reach.
- **Step down, suggested.** The app offers the step below with "Step down" and "Not yet", as Move
  up does; nothing changes without the tap. No published system defines this rule; it is ours.
  - When two sessions in a row at a step, not counting the first session there, missed their
    targets with most sets below the bottom of the range (the weaker side counted).
  - Not for a loaded step (the weight is what to lower, ADR-0072), sessions in a strength block,
    or a level chosen "For today" (ADR-0080).
  - At a ladder's first step it names the easier exercise for the same muscles (ADR-0083), or
    offers a lower range.
  - After 21 days or more away, one prompt for the return ("Ease back in: one step down today"),
    not one per exercise.
- **An easy start** for a person at level 3 or below, or who says they're new to training: the
  first two weeks run three or four exercises of one or two sets (ICFSR 2021), then
  program-builder's Decided 7 (one set lower for four weeks). A trained person skips it.
- **Effort words for levels 1 to 3:** "stop when the next rep would lose its form", not reps in
  reserve; and on every exercise, "breathe out as you push; don't hold your breath".

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| F1: 1-2 reps short everywhere | Today's rule | Leaves the small gain on light, high-rep sets |
| F2: optional last set where safe (chosen) | The gain where it is real, the risk kept out | A catalogue flag and an option to explain |
| F3: failure on every last set | Simplest | Not supported for compound bodyweight moves or older people (ACSM 2026) |
| Re-run the trim to know a past day's plan | Nothing stored | Drifts with pace and plan changes; wrong history |
| Step down automatically | No tap | Against the product rule: the person decides |

## Consequences

- `domain/progression.py` and `domain/targets.py` take each session's planned sets; both stay
  pure and at 100% coverage, with table tests for old rows without a map.
- `plan.toml` gains `failure_ok` per exercise; settings gain the last-set option.
- The step-down suggestion sits next to Move up on the web, the bot and the weekly review.

## Addendum: the last set as built (#535)

- **Where:** strength and conditioning sessions, the ones a day can shorten (ADR-0082). A recovery
  session runs every set as usual, though Prone Y-T-W in it is `failure_ok`.
- **Fixed with the length:** whether a day has the option is kept with the set counts when its
  first set is kept, so turning it on or off later reaches the next session, and a save the next
  morning marks what the person was shown.
- **The mark:** `workouts.planned[slug]["failure_set"]`, the set number as the log numbers it
  (a skipped set before it moves it up). A last set not done gets no mark; a typed log has no
  plan, so the bot's work list names the set but its reps count as done.
- **Targets:** at or above its target, the set counts as its target met, its baseline session
  included (the target it was shown, so the bottom of the range the first time). Below its
  target it is an ordinary miss, held or eased.
- **The lock:** 8 weeks from the first done workout. "Or at level 3 or below" joins
  `domain.last_set.available` once placement gives a person a level (ADR-0083).
