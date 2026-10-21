# Program builder, equipment and home/gym versions: a plan with options

Status: **draft, 2026-10-21**, for the owner to review. Written from the code on `main` at
0.32.0 and the owner's answers in chat on 2026-10-21 (below, under Asked for). Nothing here is
decided until the questions at the end are answered; an ADR then records each decision.

## Asked for (2026-10-21)

1. **A way to set up a program:** choose exercises and levels for each muscle group, so the plan
   covers the whole body; a picture of the body whose areas change colour when they're covered.
2. **Built for everyone**, though only the owner uses it now: "no point in having a program that
   only works for me".
3. **Home or gym.** Each session in the cycle can have a home version and a gym version, picked
   on the day.
4. **Equipment at home**, added to as it's bought. A new 16 kg kettlebell lets kettlebell swings
   progress past 8 kg; new kit can also bring new movements.
5. **Weights:** in the gym, the weight carries over from last time with a + and − button.
6. **Pictures** of each exercise from start to finish (a mannequin figure, animated if it works;
   separate work, prototype in progress). The picker shows them.

## What's true today

### The plan is one shared copy

- `seed/plan.toml` is the plan; `make seed` loads it (`services/seed.py`). The plan tables carry
  no `user_id`: `exercises`, `ladder_steps`, `plan_versions`, `session_templates`,
  `template_items` (`db/models.py`). 32 exercises (2 retired), 7 sessions, 10 tests, 15
  stretches.
- **Per person already:** the place in the queue (`plan_state`, ADR-0006), the ladder step per
  exercise (`exercise_state`), settings, blocks (ADR-0028), test days (ADR-0037), every log.
- **Nobody can change the plan in the app.** `GET /api/plan` is read-only. Today's session can
  be moved, swapped or rested (ADR-0052), never edited. Ladder steps only go up, through Move up
  after a ready session (ADR-0016, ADR-0025); there is no way to choose a level.
- Multi-user decided **D1 now, D3 later** (multi-user-plan.md, Decided 7; ADR-0059 "Plans"):
  everyone on the owner's plan with their own progress; each person's own copy is the goal, and
  new code should take the person's plan where that's as cheap as assuming one.

### There is no equipment and no load

- The product spec fixes the kit: 8 kg kettlebell, pull-up bar, chairs, floor. Weight exists only
  in ladder step names: `kb-swing` is "Two-hand, 8 kg", "One-arm, 8 kg", "Heavier kettlebell".
  Seven ladders end in "Heavier kettlebell" or "Weighted backpack".
- `set_logs` has one `value` (reps, seconds or minutes). No load column, no place.
- Progression is reps within a range (ADR-0027: +10% of the top of the range per set) and then a
  harder ladder step (ADR-0016). Targets and bests are scoped to the step and the block kind
  (ADR-0028), and history follows the exercise, never the plan day (ADR-0034).

### Muscles are free text

- `exercises.muscle_groups` is a JSON list of 24 free strings (quads, lats, "shoulders",
  "grip", "posture", ...). `domain/volume.py` counts every planned set once for each tag on its
  exercise against 10-20 hard sets a week, skipping four non-muscle tags. The Plan tab shows that
  count as "Hard sets per muscle, per week".
- No movement pattern (squat, hinge, push, pull ...) and no equipment on any exercise.

## Options

### A. Whose plan: shared, or each person's own

| Option | What | Pros | Cons |
| --- | --- | --- | --- |
| A1 Keep one shared plan, add editing | The builder edits `plan.toml`'s tables for everyone | Smallest | Only works while there's one person; contradicts "built for everyone" |
| A2 **Each person owns their sessions** (recommended) | `session_templates` and `template_items` become per person (`Owned`, `user_id`); `exercises` and `ladder_steps` stay shared as the **catalogue**. A starter plan (today's `plan.toml`) is copied into a person's rows when they join | Few foreign keys move: workouts, `plan_state` and `session_progress` already point at `session_templates`; scoping is enforced at run time (ADR-0029), and `test_user_scope` pins the list | Every query of sessions becomes per person; the seed stops changing anyone's sessions after the copy |
| A3 New `plans`, `plan_sessions`, `plan_items` tables | A plan as its own object, several per person | Room for "switch plan" later | Every foreign key to `session_templates` moves; a large migration for no need yet |

With A2 this **replaces D1 with D3** for the plan itself. It needs no part of multi-user steps
4-11 (invites, roles, Telegram), so it can be built and used by the owner alone; when invites
arrive, redeeming one copies a starter and runs the setup (H).

**Plan versions per person.** `plan_versions` (ADR-0034) becomes per person: every saved edit
makes a version (date, a short "what changed"), and workouts keep recording the version in force
on their date. The starter's two versions are copied with it.

**The owner's workflow changes.** Today a plan change is an edit to `plan.toml` and `make seed`.
After A2 the owner's plan is edited in the app like anyone's; `plan.toml` holds the catalogue
and the starters. See question 1.

### B. The catalogue: fixed muscles, patterns and needs

Each exercise in the catalogue gains:

- **Muscles from a fixed list**, primary and secondary, replacing the free tags. About 18:
  neck, chest, front delts, side delts, rear delts, upper back, lats, biceps, triceps, forearms,
  core, lower back, glutes, hip flexors, quads, hamstrings, calves, tibialis. "shoulders" and
  "grip" map onto these; posture, power, mobility and conditioning become **qualities**, kept
  apart from muscles (as `NON_MUSCLE_TAGS` does now).
- **A movement pattern:** squat, hinge, lunge, horizontal push, vertical push, horizontal pull,
  vertical pull, carry, core, isolation, mobility, cardio. Swap offers the same pattern first.
- **What it needs, per ladder step:** for example `needs = ["kettlebell:16"]` or
  `["pull-up bar"]` or `["barbell", "rack"]`. Bodyweight steps need nothing.
- **How it gets harder:** `ladder` (bodyweight or fixed kit, as today) or `load` (a barbell,
  dumbbells, a machine: one step, the weight goes up, see D).
- **Pictures:** a pose id per exercise (start and end), from the mannequin work.

The seed validates all of these as it does today (unknown muscle, unknown kit: refused).

### C. Equipment and places

- **Places:** a person trains at home, at a gym, or both (a setting).
- **Gym:** assumed to have everything in the catalogue. A gym missing something is question 8.
- **Home kit**, per person (`equipment`, `Owned`): one row per item, with a weight where it has
  one. Kettlebells (each weight), dumbbells (fixed pairs, or adjustable with a range), pull-up
  bar, dip bars or two chairs, bench, resistance bands (light/medium/heavy), weighted backpack
  (up to N kg), rings, a step or box, a mat. Account gets "My equipment": tap to add, and the
  app says what it unlocks ("16 kg kettlebell: 3 new steps in swings, split squats, rows").
- **Ladders become concrete.** "Heavier kettlebell" is replaced by real steps, each with what it
  needs. Swings: two-hand 8 kg, one-arm 8 kg, two-hand 16 kg, one-arm 16 kg, two-hand 24 kg.
  A step whose kit you don't have shows locked, "needs a 16 kg kettlebell". Move up skips to the
  next step you can do; at the last one you can do, Progress says "top for your kit: a 16 kg
  kettlebell unlocks the next step" instead of "top of the ladder".
- **Concrete steps, not generated ones** (recommended): each step written in the seed with its
  name, needs and cue, reviewable like today's ladders. Generating steps from the weights owned
  would save typing but give steps no cues and no order a person can read.

### D. Load: weight on sets, and how it goes up

For `load` exercises (B) only. Ladder exercises keep ADR-0016/0027 unchanged; a kettlebell at
home stays a ladder step, because 8 to 16 kg is a different exercise, not a small step.

- **Each set records its load** (`set_logs.load_kg`, nullable; empty for bodyweight).
- **It carries over:** the set screen starts at the load of the same set last time, at the same
  place, with − and + buttons in the kit's increment. No typing.
- **Double progression** (needs an ADR alongside ADR-0027): reps go up within the range as
  ADR-0027 says. When every set reaches the top of the range in a session, the next session
  adds the smallest increment and the reps start again at the bottom. A missed target holds, as
  in ADR-0027. Increments by kit: barbell 2.5 kg, dumbbells 2 kg (per hand), machines 5 kg; a
  person can change theirs (question 6).
- **Scope:** targets and bests for a load exercise are per load as well as per block kind, so a
  heavier weight starts from its own baseline, as a new ladder step does (ADR-0034).
- **Blocks (ADR-0028):** a strength block on a load exercise is 4-8 reps at a heavier load,
  instead of the next ladder step.

### E. Home and gym versions of a session

- A session in the cycle keeps one place in the queue (ADR-0006) and can hold **two versions**:
  home and gym. `template_items` gains `place` (home or gym). A session with one version is done
  there; a session with none for a place is offered as "home version not set up yet".
- **On the day:** Today shows a Home | Gym switch when both exist. The default comes from the
  last place used (or a weekly pattern, question 4). The choice is stored on the workout
  (`workouts.place`) and can change until the first set is kept.
- **History follows the exercise** (ADR-0034), so pull-ups at home and in the gym are one
  history; a gym barbell squat and a home split squat are two, as they should be.
- **The body map and weekly sets** are worked out for the week as planned: by default the
  versions you used most recently, with a switch to see "all home" or "all gym".

### F. The picker and the body map (Plan tab)

- **The body map:** a front and back figure, the same mannequin style as the exercise pictures,
  each region coloured by planned hard sets a week: grey none, amber under 10, green 10-20, red
  over 20 (`TARGET_MIN_SETS`, `TARGET_MAX_SETS` in `domain/volume.py`). Tap a region: its sets,
  where they come from, and the exercises that would add to it.
- **Counting:** a primary muscle counts each set as 1; a secondary one as 0.5 (recommended;
  today every tag counts 1, which overstates). Small muscles (neck, tibialis, forearms) may want
  a lower band. Questions 2 and 3.
- **The picker:** from a region, a session, or Swap on an exercise. It lists catalogue exercises
  that train it, can be done with the kit at that place, and fit the pattern; each with its
  pictures, level and what it needs. Pick one: choose the session and version, sets and range
  (defaults from the catalogue), and the starting level (G).
- **Editing a session:** add, swap, remove, reorder, pair (ADR-0031), sets and range. Nothing
  changes until **Save**, which makes a plan version; the map updates as you edit.
- **Warnings, not rules:** a region left grey; the same muscle hard on two days in a row; a
  session that will take over an hour (from the timings, ADR-0061); pushing without pulling.

### G. Choosing the starting level

| Option | What |
| --- | --- |
| G1 **"Can you do ...?" questions** (recommended) | Walk the ladder from the bottom: "Can you do 8 good push-ups?" Yes moves on, No stops there. Two or three questions per exercise, written in the seed per step |
| G2 From the baseline tests (ADR-0037) | Max push-ups 20+ starts at step 3, and so on: a mapping per test. Good for the tested exercises only |
| G3 "Let the app find out" | Start at the easiest step; the first session is the baseline (ADR-0034) and Move up does the rest. Slow for a strong beginner |

G1 for everything, G2 as a suggestion where a test exists, G3 always available. A level can be
set by hand on the Plan tab too (down as well as up; it records an event, like Move up does).

### H. Setting up, for a new person (and the owner, again)

A short flow, one question per screen, every step skippable:

1. Where do you train? Home, gym, or both.
2. What's at home? The kit list (C).
3. How many days a week? A starter for it (question 7); today's 7-day cycle is the first.
4. Your levels (G).
5. The body map for the result; Save. Then the Plan tab for anything else.

The owner runs it once after A2 lands, starting from their current plan instead of a starter.

### I. Pictures in the builder

Every catalogue exercise and step shows its start and end pose (mannequin, animated, or two
frames with reduced motion). The picker needs them most: it's where people meet exercises they
don't know. New gym exercises (D) add perhaps 25 poses to the roughly 100 already planned.

## API, in outline

- `GET /api/catalogue`: exercises with muscles, pattern, steps, needs, pose ids.
- `GET /api/equipment`, `PUT /api/equipment`; `GET /api/equipment/unlocks?add=kettlebell:16`.
- `GET /api/plan` becomes the person's plan, with versions per place; `POST /api/plan/changes`
  saves a batch of edits against the plan's revision (a stale revision is refused, as day
  clashes are, ADR-0060) and returns the new version.
- `GET /api/plan/coverage?place=`: weekly sets per muscle for the map.
- `PUT /api/plan/levels`: starting levels.
- Today and the guided session take `place`; kept sets carry `load_kg`.

## Suggested order (small PRs, each usable on its own)

1. **ADRs:** each person's own plan (A2; amends ADR-0059's Plans and multi-user Decided 7),
   equipment and places (C, E), load and double progression (D).
2. **Catalogue facts:** fixed muscles, patterns, needs in `plan.toml`; no behaviour change. The
   Plan tab's volume chart uses the fixed list.
3. **Body map, read-only**, on the Plan tab, from the current plan.
4. **Equipment** on Account; concrete kettlebell and backpack steps; locked steps; Move up and
   Progress respect the kit. The 16 kg example works from here.
5. **Plans per person** (A2): the migration copies the plan to every user; the seed keeps the
   catalogue and starters; the canary test (multi-user L2) covers the plan routes.
6. **Edit the plan:** set level, swap, sets and range; Save makes a version.
7. **The picker and an interactive map:** add and remove exercises; add a session.
8. **Load:** gym exercises in the catalogue, `load_kg`, carry-over with − and +, double
   progression.
9. **Home and gym versions**, `workouts.place`, the switch on Today.
10. **Setup flow** (H) and the level questions (G1).

Pictures arrive alongside, as poses are drawn: the set screen first, then the picker. Steps 2-4
help the owner straight away with no change to how plans are stored; step 5 is the point of no
return and should wait until 2-4 have settled.

## Risks

- **Step 5's migration** touches the busiest tables. Every read of `session_templates` must be
  bound to a person; the run-time binding makes a forgotten filter safe, and `test_user_scope`
  fails until the new owned tables are listed. A backup and a dry run first, as for any Pi data
  change.
- **The seed's job changes** after step 5: a catalogue change (a new exercise, a fixed cue)
  still reaches everyone; a starter change reaches only new people.
- **Bad plans:** a free builder lets someone plan 40 sets of chest. Warnings (F) and starters
  keep that rare; nothing stops it, by design.
- **Volume numbers move** when secondary muscles count half: the weekly review and the Plan tab
  will show lower numbers for the same plan. Say so in the release notes.
- **Size:** about ten PRs, several of them near the 400-line limit. The catalogue (step 2) and
  the gym exercises (step 8) are mostly data and review time.

## Questions

1. **After step 5, how do you change your own plan:** only in the app, or should `plan.toml`
   stay your plan's source with an "apply" step? (Recommended: the app, so you use what members
   will.)
2. **Secondary muscles** count half a set? (Recommended: yes.)
3. **Small muscles** (neck, tibialis, forearms): a lower green band, say 6-12 sets? Or the same
   10-20?
4. **Home or gym on the day:** default to the last place used, a weekly pattern you set (gym on
   weekdays, home at weekends), or ask every time?
5. **Gym exercises first:** which do you want in the catalogue? A suggested first set: back
   squat, Romanian deadlift, bench press, overhead press, barbell row, lat pulldown, seated cable
   row, leg press, leg curl, calf raise machine, cable face pull, dumbbell curl, triceps
   pushdown.
6. **Increments:** barbell 2.5 kg, dumbbells 2 kg per hand, machines 5 kg as defaults, changeable
   per person? kg only, or pounds as well?
7. **Starters for new people:** only your 7-day cycle at first, or 3- and 4-day full-body
   starters too?
8. **A gym without some kit:** treat every gym as complete for now, or let people untick what
   theirs lacks?
9. **Custom exercises** a person types in themselves (no pictures, no checked muscles)? Suggested:
   not at first; ask for additions to the catalogue instead.
10. **Travelling:** a third place, "away" (bodyweight only), or is home with no kit enough?
