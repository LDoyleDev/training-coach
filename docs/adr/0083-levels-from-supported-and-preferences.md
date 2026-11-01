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
- **How the preferences are kept:** on the server as settings, named neutrally, in the export
  and erased with the account; not exposed over Telegram or the MCP read tools (ADR-0047 C).
  Whether a stored preference such as "Keep me off the floor" could count as health data by
  inference (CJEU C-21/23) is on the lawyer's list with ADR-0085's points; the privacy notice
  draft names them.

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

## Addendum (31 Oct 2026): the entry exercises as built (#507)

- **Seventeen entry exercises,** in the catalogue and in no session yet: glute bridge, step-up,
  plank, knee lift, adductor squeeze, standing hamstring curl, hip hinge, deadlift, seated toe
  lift, armchair press-up, band pushdown, seated band row, band pull-apart, band pulldown,
  seated press, balance and interval walk. Two items the spec writes together became one ladder
  where the movement is the same (seated march and the standing knee lift, the pillow squeeze
  and band adduction), and two exercises where it isn't (the armchair press-up and the band
  pushdown; the band pulldown apart from the pull-up ladder, so "No hanging" still progresses).
- **A range on an exercise no session uses** (`range` in `plan.toml`, not stored): the range a
  session would give it, whose bottom its "Can you do...?" questions ask for. A session item's
  range wins; the seed refuses both. Ladders from level 1 counted in reps are 3-10.
- **Left to the migration (#508):** the squat (the sit-to-stand steps go below the retired
  `goblet-squat`'s goblet steps, which needs positions to move; a separate `squat` would split
  its history as option B does), and the low steps that are the same movement as a ladder
  (bottle and bag curls, the seated bottle lateral raise, the back extension on a bed).
- **The rule's test** lists the muscles still without a way in: chest, biceps, calves, forearms,
  upper traps and obliques until #508, and the neck, whose low step the revised list dropped.
- **Balance** is a new quality and pattern (`balance`): counted in seconds, never as sets.

## Addendum (31 Oct 2026): the migration as built (#508)

- **One migration, `5ebed72122f7`,** moves fifteen ladders and the Squat; the steps, levels and
  marks are hard-coded in it and plan.toml matches them (a test holds both). The Squat is the
  retired `goblet-squat`, un-retired and renamed, with eight sit-to-stand steps below its goblet
  steps; "Fast up, slow down" is in its cues from "arms crossed" on.
- **Nothing stored refers to a position** but `ladder_steps.position`: levels, sets, a session in
  progress, replaced workouts and events name step ids, which the migration keeps. `start` is in
  plan.toml only; it moves by the same number, so it names the same step and nobody's starting
  point changes. Placing people lower is setup's job (builder step 10).
- **Left out, as different movements** (option A puts those in entry exercises, as #519 did with
  the seated band row): the doorframe rows (a bodyweight two-hand pull, not the one-arm row) and
  side-lying adduction (closer to the adductor squeeze than the Copenhagen plank). Either can be
  added later without a migration, as a new exercise or at the top of the adductor squeeze. The
  hamstrings' low steps are the standing hamstring curl entry (#518), so the towel slide ladder
  is unchanged. The cardio row's bike or seated stepping is a mode of zone 2's easy walk.
- **Exercise names stay** ("Single-leg calf raise", "Bulgarian split squat", "One-arm kettlebell
  row", "Kettlebell curl", "Kettlebell lateral raise") although their new bottom steps aren't
  that: renaming is the seed's job and needs no migration, so it can follow on its own. The
  same goes for the neck exercises' "(lying ..., head off edge)".
- **A seated way in for the neck** (Liam, 1 Nov 2026): "Seated, hand resistance, held" (1) below
  the lying bottom step of neck flexion, extension and side bend: the head pressed gently into
  the hand and held 5 s, each hold one rep. The way-in rule now holds for every muscle, with no
  waiting list.
