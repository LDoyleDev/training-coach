# ADR-0083: Every step has a level from "supported" up, with an open top, and four preferences

- Status: Accepted
- Date: 2026-10-31
- Deciders: Liam

## Context

Today's ladders start at a fit adult: a standard push-up, pull-up negatives, a split squat with
the back foot on a chair. Liam asked for every area of the body to start much lower, for older,
untrained or obese people who can't do one push-up or pull-up, and to build them up
(`docs/specs/any-level-any-time.md`, Part B; evidence in `any-level-research.md` Part 2).

Steps are matched by position in `plan.toml`, the seed only adds steps at the end, and
`ladder_steps` is unique on (exercise, position). Each person's level
(`exercise_state.ladder_step_id`) and every logged set point at the step's id, so steps can
move up to make room at the bottom without moving anyone's level or history. No migration has
moved a step yet: `b7e1c3d5f9a2` deleted two unused top steps. A walk-through as four people
(31 Oct) found muscles with no standing or seated way in, jumps too big for heavy people, and
8 kg steps with nothing below them; the catalogue in the spec (B2-B3, revised) answers them.

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
  ADR-0072's double progression. Some of today's bottom steps are easier than level 4 (a
  bottle lateral raise, a wall tibialis raise) and get the level they are.
- **Lower steps:**
  - **The same movement** extends its ladder downward (the push-up from a wall, through a
    counter, a table, a chair seat against the wall, the knees and a stair, to the floor).
  - **A different movement** is a new entry exercise: Squat (the retired `goblet-squat`, revived
    and renamed, so it keeps its history), Glute bridge, Step-up, Plank, Balance, Interval walk,
    and the frail entries in the spec (seated march, pillow squeeze, standing hamstring curl,
    armchair press-up, seated band row, band pull-apart, seated toe lifts).
  - **Household loads before kettlebells:** water bottles, a bag or a band below every step that
    starts at 8 kg.
  - **No sensible low step** (pistol and jump squats, swings, Nordic and reverse Nordic curls,
    Copenhagen planks, ab rollouts, dips, HIIT): the catalogue names an easier exercise that
    trains the same muscles.
  - **A test holds the rule:** every muscle on the body map has a step at level 1 or 2 where it
    is a prime mover, done standing or seated, with at most a chair, a wall, a counter, a table,
    a door frame, a band, bottles or a bag.
  - **Level-1 ranges start low** (3-10 reps), so a frail person can't miss the bottom on day one.
- **One migration, one release** moves every extended ladder: it parks positions to pass the
  unique constraint (as `seed.py` does for sessions), shifts the existing steps by the number of
  new ones, inserts the new rows by name, and moves `start`. Expected names are hard-coded and it
  stops before any write if a ladder isn't as expected. Like `b7e1c3d5f9a2`, it needs a Pi check
  and a dry run on a copy, with Liam's OK, before its release; downgrade after anyone logs at a
  new step means restoring the backup. Step numbers shown elsewhere (AI summaries, the share
  card) renumber; the old bottom steps gain "Can you do...?" questions (ADR-0075).
- **Marks:** floor, kneeling, impact, hanging, and balance (a fall risk: at levels 1-3 its cue
  names a counter or rail to hold).
- **Four preferences:** "Keep me off the floor", "No kneeling", "No jumping or running" and "No
  hanging". Until each person has their own sessions (builder step 5, ADR-0073), a marked step
  locks the way a step needing kit you don't have does (ADR-0071), so the ladder skips it; after
  step 5 the session can swap in the exercise's marked alternative. A cardio setting "Use the
  talk test, not heart-rate zones" sits with them, asked without a reason.
- **Preferences, not medical.** The app isn't interested in conditions or diagnoses: it never
  asks for one, a reason for a preference, or stores one. People take responsibility for what
  they feel ready and able to do; the app says to get medical advice if they need it. Wording
  stays "You choose what you're ready for".

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A: extend ladders, entry exercises where the movement differs (chosen) | One ladder keeps one movement's progress and history | A one-off migration that moves steps |
| B: every lower step its own exercise | No migration | Progress splits across exercises; moving up crosses exercises |
| Seed matches steps by name instead of position | No migration for later inserts | A rewrite of the seed's matching and renames; more risk now |
| Six levels with a closed top | Simple | Caps people who load up |

## Consequences

- `plan.toml` gains a level and marks per step, the new steps and exercises, their questions
  and cues; figures follow as poses are drawn (ADR-0063), with the figure picker coping with a
  step it has no figure for.
- Settings gain the four preferences and the talk-test setting; nothing about a person's health
  is stored.
- A fifth preference, "Easy on my knees", came out of the walk-through; it is for Liam to decide.
