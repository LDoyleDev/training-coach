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

## Decision

- **Two ways to set the time, both built, T1 first.**
  - **Short on time today:** on the session overview and Today, As planned, 40, 30 or 20
    minutes. It applies to that day's session only; the plan doesn't change. The choice is kept
    with the session's progress, so a reload or another device shows it, and the saved workout
    records the minutes chosen.
  - **Minutes per session:** a setting on Account (and later in setup). Every session runs at
    that length unless the day says otherwise. Empty means as planned.
- **One pure trim** in `domain/` takes a session's items (sets, what each trains, single-joint or
  a main pattern), the estimate and the minutes, and returns the shorter version and what it
  dropped. Each rule applies only while the session still doesn't fit, in this order:
  1. fourth and later sets go;
  2. the third round goes, so every exercise keeps two sets;
  3. pairs become threes where three exercises with no shared prime mover sit next to each
     other, at 20 minutes or less;
  4. whole exercises go: first those whose muscles another kept exercise in the session also
     trains as a prime mover, then single-joint exercises; the main patterns (squat or lunge,
     hinge, push, pull) last;
  5. never under one set of a kept exercise, or under 60 s between two sets for the same muscle.
- **The estimate uses the person's pace** where it is known: when a session has a "usually"
  time (ADR-0061), the trim scales the estimator by usually over the estimate for that session.
- **The warm-up in a very short session:** at 30 minutes or less the 5-minute warm-up is
  replaced by ramp sets: one or two easy sets of the first exercise at about half its target,
  well short of failure, not logged as work sets and counted as 2 minutes. Above 30 minutes the
  warm-up stays 5 minutes.
- **What's dropped is named before Start.** The guided session, the bot's work list and the time
  estimate all follow the trimmed version.
- **Progress on a shorter day** is judged on that day's own sets (ADR-0084).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Both, T1 first (chosen) | Helps on a busy day now; T2 reuses T1's rules for someone who always has 30 minutes | Two controls to explain |
| T1 only | Smallest | A person who always has 30 minutes chooses it every day |
| T2 only | One setting | No help on a single busy day |
| Write shorter versions of each session by hand | Reviewable | Doubles the sessions to keep; doesn't fit any minutes |

## Consequences

- `domain/trim.py` is pure and held at 100% coverage with table-driven tests pinning each rule.
- The session's progress keeps the minutes chosen; `workouts` gets a nullable `minutes` column
  so progress can tell a shortened day (ADR-0084). A migration, no data change.
- Settings gain minutes per session. The body map can later show the week at that length.
- The 30-minute line for ramp sets is a choice, not a finding (Iversen 2021 allows ramp sets in
  short sessions); it is one constant.
