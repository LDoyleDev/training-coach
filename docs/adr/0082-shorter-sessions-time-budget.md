# ADR-0082: Shorter sessions: short on time today, and minutes per session

- Status: Accepted
- Date: 2026-10-31
- Deciders: Liam

## Context

Liam asked for sessions that fit people with less time, down to about 40 minutes of work, for
example pairs done twice instead of three times (`docs/specs/any-level-any-time.md`, Part A).
By the estimator (`services/guided.py`), today's home resistance days are 42-44 minutes of work
plus a 5-minute warm-up (ADR-0065 addendum). Two rounds instead of three keep about 80% of the
growth on Pelland 2026's dose curve (derived; `any-level-research.md` Part 1). ADR-0053 rejected
easing a session automatically from the daily check; a shorter session the person picks is a
different thing: the person decides (product rule).

A plan review and a walk-through as four people (31 Oct) shaped the details below: the guided
session keeps sets by item index (`guided.py`, `session_progress.sets`), targets fill missing
sets from the weakest (ADR-0027) and readiness needs every planned set (ADR-0016), so a shorter
day has to record what it planned (ADR-0084), and both ship together.

## Decision

- **Two ways to set the time, both built, T1 first.**
  - **Short on time today:** on the session overview and Today, As planned, 40, 30 or 20
    minutes, for that day's session only; the plan doesn't change. The choice is kept in the
    session's progress, so a reload or another device shows it.
  - **Minutes per session:** a setting on Account (and later in setup); every session runs at
    that length unless the day says otherwise. Empty means as planned.
- **Which sessions:** strength and conditioning sessions, including the part of a conditioning
  session left after its run (ADR-0066). Recovery sessions and test days aren't trimmed. In a
  strength block the block's prescription comes first (ADR-0028), then the trim.
- **One pure trim** in `domain/` takes the items (sets, prime movers, pattern, kind), the
  estimate and the minutes, and returns each item's set count (0 means dropped; items are never
  removed from the list, so kept sets keep their indexes) and what was dropped. Each rule applies
  only while the session still doesn't fit, in this order:
  1. fourth and later sets go, from every exercise at once;
  2. third sets go, from every exercise at once, so every exercise keeps two;
  3. a cardio item (`duration_min`) shortens, never below 10 minutes; its target counts as
     dropped, not missed;
  4. whole exercises go, one at a time, by this key: first single-joint and accessory work
     (isolation, core, carry, mobility) whose prime movers another kept exercise also trains; then
     the other single-joint and accessory work; then main patterns (squat or lunge, hinge, push,
     pull) whose prime movers another kept exercise trains; main patterns not covered by any
     other last. Within a group, the exercise later in the session goes first. An exercise the
     person pins with **Keep** for the day isn't dropped;
  5. never under one set of a kept exercise, or under 60 s between two sets for the same muscle.
  - When even the floor doesn't fit, the overview says "The shortest this session gets is N
    minutes" and offers that.
  - Pairs into threes is left for later: `work_order` and the rests only know pairs (ADR-0065).
- **The estimate uses the person's pace** where it is known: the estimate without the warm-up,
  scaled by the session's "usually" (ADR-0061, which excludes the warm-up and breaks) over its
  estimate, per place (home or gym), from at least three timed sessions done as planned. Trimmed
  days don't count toward "usually". Without that, the plain estimator.
- **Fixed for the session once it starts:** the set counts, the pace factor and the minutes are
  kept in `session_progress` when the first set is kept, so a recomputation can't move indexes.
- **The warm-up in a very short session:** at 30 minutes or less the 5-minute warm-up becomes
  ramp sets: one or two easy sets of the first exercise at about half its target, well short of
  failure, not logged as work sets, counted as 2 minutes. When the first exercise's step is level
  3 or below (ADR-0083) the 5-minute warm-up stays, at any length. This amends ADR-0065's
  addendum ("a constant") and ADR-0028's warm-up line.
- **What's dropped is named before Start.** The guided session, the time estimate and the bot's
  work list follow the trimmed version once the day's minutes are chosen; the morning message,
  sent before, shows the planned length and says it can be shortened.
- **The saved workout records what was planned** (ADR-0084) and the minutes chosen.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Both, T1 first (chosen) | Helps on a busy day now; T2 reuses T1's rules for someone who always has 30 minutes | Two controls to explain |
| T1 only | Smallest | A person who always has 30 minutes chooses it every day |
| T2 only | One setting | No help on a single busy day |
| Write shorter versions of each session by hand | Reviewable | Doubles the sessions to keep; doesn't fit any minutes |

## Consequences

- `domain/trim.py` is pure and held at 100% coverage with table-driven tests pinning each rule
  and the drop key.
- `session_progress` keeps the day's minutes, set counts and pace factor; `workouts` gets a
  nullable `minutes` and the planned sets (ADR-0084). Migrations add columns; no data change.
- Settings gain minutes per session.
- The 30-minute line and the level-3 exception are choices, not findings (Iversen 2021 allows
  ramp sets in short sessions); each is one constant.
