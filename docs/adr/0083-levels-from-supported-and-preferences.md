# ADR-0083: Every step has a level from "supported" up, with an open top, and four preferences

- Status: Accepted
- Date: 2026-10-31
- Deciders: Liam

## Context

Today's ladders start at a fit adult: a standard push-up, pull-up negatives, a split squat with
the back foot on a chair. Liam asked for every area of the body to start much lower, for older,
untrained or obese people who can't do one push-up or pull-up, and to build them up
(`docs/specs/any-level-any-time.md`, Part B; evidence in `any-level-research.md` Part 2). Steps
are matched by position in `plan.toml` and the seed only adds steps at the end, but each
person's level (`exercise_state.ladder_step_id`) and every logged set point at the step's id,
so a one-off migration can make room at the bottom without moving anyone's level or history, as
`b7e1c3d5f9a2` did.

## Decision

- **A level on every step,** 1 to 6:

  | Level | Who |
  | --- | --- |
  | 1 Supported | Stands up from a chair only with the hands; walking a few minutes is hard |
  | 2 Starting | Stands up without the hands; no push-up from the knees yet; walks 10 minutes |
  | 3 Building | Knee push-ups, a bodyweight squat, a 20-minute walk |
  | 4 Regular | Today's bottom steps |
  | 5 Strong | Today's middle steps |
  | 6 Advanced | Today's top steps, and everything above |

  Levels place a person and pick a sensible start; they never cap progress. **The top is
  open:** where load can keep rising (push-ups, pull-ups and dips with a vest, a backpack or
  weights), steps keep being added above today's top at level 6, and loads keep rising by
  ADR-0072's double progression.
- **Lower steps:**
  - **The same movement** extends its ladder downward (a wall push-up, then a counter, the knees
    and a low step below the standard push-up; a doorframe row below the one-arm row), with a
    one-off migration per ladder that moves the existing steps up.
  - **A different movement** is a new entry exercise: Squat (the retired `goblet-squat`, revived
    and renamed, so it keeps its history), Glute bridge, Step-up, Plank, Balance and Interval
    walk.
  - **No sensible low step** (pistol and jump squats, swings, Nordic and reverse Nordic curls,
    Copenhagen planks, ab rollouts, dips, HIIT): the catalogue names an easier exercise that
    trains the same muscles, for example a band hamstring curl for the Nordic, side-lying
    adduction for the Copenhagen, a dead bug for the rollout, a band pushdown for dips.
  - **A test holds the rule:** every muscle on the body map has at least one step at level 1 or
    2 that is done standing or seated, with at most a chair, a wall, a counter, a door frame or a
    band.
- **Marks and four preferences.** Steps carry marks: floor, kneeling, impact, hanging. A person
  can switch on "Keep me off the floor", "No kneeling", "No jumping or running" and "No
  hanging"; a marked step then isn't offered and the exercise's marked alternative is.
- **Preferences, not medical.** The app isn't interested in conditions or diagnoses: it never
  asks for one, a reason for a preference, or stores one. People take responsibility for what
  they feel ready and able to do; the app says to get medical advice if they need it. Wording
  stays "You choose what you're ready for".

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A: extend ladders, entry exercises where the movement differs (chosen) | One ladder keeps one movement's progress and history | A migration per ladder extended downward |
| B: every lower step its own exercise | No migration | Progress splits across exercises; moving up crosses exercises |
| Six levels with a closed top | Simple | Caps people who load up |

## Consequences

- `plan.toml` gains a level and marks per step, the new steps and exercises, their "Can you
  do...?" questions (ADR-0075) and cues; figures follow as poses are drawn (ADR-0063).
- Each downward extension is a migration that moves step positions and `start`. Like
  `b7e1c3d5f9a2`, its release needs a Pi check and a dry run on a copy, with Liam's OK.
- Settings gain the four preferences. The picker and placement read levels; nothing about a
  person's health is stored.
