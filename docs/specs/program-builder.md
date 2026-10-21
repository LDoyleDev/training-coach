# Program builder, equipment and home/gym versions: a plan with options

Status: **decided 2026-10-21**: the owner answered every question (below, under Decided);
step 1's ADRs record the decisions. Written from the code on `main` at 0.32.0 and the owner's
answers in chat on 2026-10-21 (below, under Asked for). The muscle counts, bands and gym
catalogue come from a review of the research (Sources, at the end); where the evidence is thin
it says so.

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

## Decided (2026-10-21)

The owner's answers to the ten questions this plan asked. Three (2, 3 and 5) were "go with the
science"; those answers come from the research under Sources. The options they choose between
are below.

1. **Changing your own plan: both.** You edit your plan in the app, like anyone; `plan.toml` can
   still be imported into your plan for a bulk change. An import is a plan edit like any other:
   it shows what would change, and Save makes a plan version (A).
2. **Secondary muscles: fractional counting.** A set counts **1** for each primary muscle,
   **0.5** for a meaningful synergist and **0** for stabilisers. A 2026 meta-regression found
   this fit muscle growth better than counting every muscle fully or not at all (Pelland 2026).
   Two exceptions from muscle-growth studies: **glutes count 1** in deep squats and split squats
   (Kubo 2019, Plotkin 2023); **hamstrings count 0** in squats, leg press and hip thrusts (they
   did not grow). **Neck counts 0** from every compound (Conley 1997), and trunk work during
   squats and deadlifts counts 0.

   | Pattern | Counts 0.5 |
   | --- | --- |
   | Horizontal press | triceps, front delts |
   | Overhead press | triceps, side delts |
   | Rows | biceps, rear delts |
   | Pulldowns and pull-ups | biceps, upper back, rear delts |
   | Squat, lunge, leg press | adductors (leg press: glutes too) |
   | RDL and other hinges | glutes, lower back, forearms (grip) |
   | Fly | front delts |
   | Hammer curl | biceps (forearms count 1) |

   Strength may gain less than half from indirect sets (about 39% in an exploratory fit); 0.5 is
   for coverage, which is what the map shows.
3. **Targets: the science, per muscle.** Six colour bands, in fractional hard sets a week:

   | Band | Sets a week | Means |
   | --- | --- | --- |
   | Grey | 0 | Not trained |
   | Amber | 1-3 | Below the effective minimum (about 4, Iversen 2021) |
   | Light green | 4-9 | Minimum effective; enough to maintain |
   | **Green** | **10-20** | The target (Schoenfeld 2017; ACSM 2026: 10 or more) |
   | Blue | 20-30 | High, for advanced people; diminishing returns |
   | Warning | over 30 | Past the point where more showed no extra growth (Pelland 2026) |

   Green also needs the muscle on **at least two days a week** (ACSM 2026). A session with more
   than about **11 fractional sets** for one muscle gets a warning (the per-session plateau in a
   2025 preprint). Smaller muscles have their own green band, each marked **low evidence** in
   the app except calves:

   | Muscle | Green (sets a week) | Evidence |
   | --- | --- | --- |
   | Neck | 3-9 per direction (flexion, extension); lateral 2-6 per side | Low: one growth trial (Conley 1997), one pain trial (Ylinen 2003); the concussion link is an association only |
   | Tibialis | 2-6; shown as covered or not | Very low: no volume data |
   | Forearms | 4-10 (hinges 0.5; carries and wrist curls 1) | Low; grip strength predicts mortality (Leong 2015, observational) |
   | Calves | 8-16, standing and bent-knee | Moderate (Kassiano 2023) |
   | Side and rear delts | 8-20 | Low: no delt-specific volume trials. Side delts need direct raises |

4. **Home or gym on the day:** the last place used, with the switch on Today to change it (E).
5. **Gym exercises first:** the 29-exercise catalogue below, chosen from the research and
   Huberman's Foundational Fitness Protocol. The picker offers **lengthened-position** options
   first, which grew more muscle in head-to-head trials: overhead triceps extension, seated leg
   curl, Romanian deadlift, deep split squat, calf raises paused in the stretch (Maeo 2021, Maeo
   2023, Kassiano 2023). Huberman's protocol also pairs each muscle with a shortened-position
   exercise; that pick has the weakest support.

   | # | Exercise | Pattern | Primary (1) | Secondary (0.5) | Equipment | Simpler option |
   | --- | --- | --- | --- | --- | --- | --- |
   | 1 | Back or hack squat | squat | quads, glutes | adductors | barbell / machine | goblet squat |
   | 2 | Bulgarian split squat | lunge | quads, glutes | adductors | dumbbells | split squat |
   | 3 | Leg press | squat | quads | glutes, adductors | machine | wall sit |
   | 4 | Leg extension | knee extension | quads | - | machine | reverse Nordic |
   | 5 | Romanian deadlift | hinge | hamstrings | glutes, lower back, forearms | barbell / dumbbells | single-leg DB RDL |
   | 6 | Seated leg curl | knee flexion | hamstrings | - | machine | slider curl / Nordic |
   | 7 | Hip thrust | hip extension | glutes | - | barbell / machine | glute bridge |
   | 8 | 45° back extension | hinge | lower back | glutes, hamstrings | bench | bird-dog |
   | 9 | Copenhagen plank | adduction | adductors | obliques | bench | side-lying adduction |
   | 10 | Standing calf raise, paused in the stretch | plantarflexion | calves | - | machine / step | single-leg on a step |
   | 11 | Seated calf raise | plantarflexion | calves (soleus) | - | machine | bent-knee DB raise |
   | 12 | Tibialis raise | dorsiflexion | tibialis | - | tib bar | wall tib raise |
   | 13 | DB bench press | horizontal push | chest | front delts, triceps | dumbbells | push-up |
   | 14 | Incline DB press | incline push | chest (upper) | front delts, triceps | dumbbells | feet-elevated push-up |
   | 15 | Cable fly / pec deck | fly | chest | front delts | cable / machine | band fly |
   | 16 | Seated DB overhead press | vertical push | front delts | side delts, triceps | dumbbells | pike push-up |
   | 17 | Cable lateral raise | abduction | side delts | - | cable | band raise |
   | 18 | Lat pulldown / pull-up | vertical pull | lats | biceps, upper back, rear delts | machine / bar | band pulldown |
   | 19 | Chest-supported row | horizontal pull | upper back, lats | biceps, rear delts | machine / dumbbells | inverted row |
   | 20 | Reverse pec deck / face pull | horizontal abduction | rear delts | upper back | machine / cable | band pull-apart |
   | 21 | Incline DB curl | elbow flexion | biceps | forearms | dumbbells | band curl |
   | 22 | Hammer curl | elbow flexion | forearms (brachioradialis) | biceps | dumbbells | band hammer curl |
   | 23 | Overhead cable triceps extension | elbow extension | triceps | - | cable / dumbbell | band overhead extension |
   | 24 | Wrist curl / reverse wrist curl | wrist | forearms | - | dumbbell | towel wring |
   | 25 | Farmer carry | carry | forearms, upper traps | obliques, abs | dumbbells | suitcase carry |
   | 26 | Neck flexion / extension | neck | neck (flexors / extensors) | - | plate / harness | manual isometrics |
   | 27 | Neck lateral flexion | neck | neck (lateral) | - | plate / band | manual isometrics |
   | 28 | Cable crunch / hanging knee raise | trunk flexion | abs | - | cable / bar | dead bug |
   | 29 | Pallof press / side plank | anti-rotation | obliques | abs | cable / band | side plank |

   Rows 5, 6, 10, 21 and 23 are the lengthened-position picks, with deep range on 1 and 2. Home
   exercises already in the plan (pull-ups, split squats, tibialis raises, neck work) stay as
   they are and gain the same muscle weights. The research didn't verify an incline-curl trial,
   and found no growth data on front-delt volume.
6. **Weights:** kg only. Default increments barbell 2.5 kg, dumbbells 2 kg per hand, machines
   5 kg; each person can change theirs (D). Pounds when someone needs them.
7. **Starters for new people:** the 7-day cycle, plus 3-day and 4-day full-body starters (H).
8. **A gym is complete:** every gym has everything in the catalogue, for now (C).
9. **No custom exercises at first:** only catalogue exercises, each with pictures, checked
   muscles and kit. People ask for additions to the catalogue instead.
10. **No "away" place:** travelling is Home, with whatever kit is there, or bodyweight only.

**What this means for the current plan.** Huberman's protocol, as reconstructed by a third
party, gives about 6-9 fractional sets per muscle a week. The current plan has the same shape
(`docs/specs/training-plan.md` already counts only 9 sets for hamstrings and chest and 6 for
calves, with every tag counted fully), so expect much of the map light green, not green, until
sets are added. The 7-day shape stays on offer as a template, with that said. Monthly
alternation between heavier and lighter schedules is harmless but not reliably better (ACSM
2026), so it stays optional. **Later options**, not in these steps: a strength mode (about 3-6
sets of the target lift a week over 2-3 days, at about 80% of a one-rep max) and a maintenance
mode (about a third of the building volume, at the same intensity).

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
and the starters, and can still be imported into the owner's plan as one versioned edit
(Decided 1).

### B. The catalogue: fixed muscles, patterns and needs

Each exercise in the catalogue gains:

- **Muscles from a fixed list**, each with its weight (1 or 0.5, Decided 2), replacing the free
  tags: `muscles = { quads = 1, glutes = 1, adductors = 0.5 }`. About 21: neck, chest, front
  delts, side delts, rear delts, upper back, upper traps, lats, biceps, triceps, forearms, abs,
  obliques, lower back, glutes, hip flexors, adductors, quads, hamstrings, calves, tibialis.
  "shoulders", "core" and "grip" map onto these; posture, power, mobility and conditioning
  become **qualities**, kept apart from muscles (as `NON_MUSCLE_TAGS` does now). Each muscle's
  bands (Decided 3) live with the list.
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
- **Gym:** has everything in the catalogue (Decided 8).
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
  person can change theirs. Kilograms only (Decided 6).
- **Scope:** targets and bests for a load exercise are per load as well as per block kind, so a
  heavier weight starts from its own baseline, as a new ladder step does (ADR-0034).
- **Blocks (ADR-0028):** a strength block on a load exercise is 4-8 reps at a heavier load,
  instead of the next ladder step.

### E. Home and gym versions of a session

- A session in the cycle keeps one place in the queue (ADR-0006) and can hold **two versions**:
  home and gym. `template_items` gains `place` (home or gym). A session with one version is done
  there; a session with none for a place is offered as "home version not set up yet".
- **On the day:** Today shows a Home | Gym switch when both exist. The default is the last
  place used (Decided 4). The choice is stored on the workout
  (`workouts.place`) and can change until the first set is kept.
- **History follows the exercise** (ADR-0034), so pull-ups at home and in the gym are one
  history; a gym barbell squat and a home split squat are two, as they should be.
- **The body map and weekly sets** are worked out for the week as planned: by default the
  versions you used most recently, with a switch to see "all home" or "all gym".

### F. The picker and the body map (Plan tab)

- **The body map:** a front and back figure, the same mannequin style as the exercise pictures,
  each region coloured by planned fractional hard sets a week in the six bands of Decided 3,
  with each muscle's own green band (replacing `TARGET_MIN_SETS` and `TARGET_MAX_SETS` in
  `domain/volume.py`). Tap a region: its sets, where they come from, how many days, and the
  exercises that would add to it. A "low evidence" note sits on the bands that need it.
- **Counting:** fractional (Decided 2). Today every tag counts 1, which overstates.
- **The picker:** from a region, a session, or Swap on an exercise. It lists catalogue exercises
  that train it, can be done with the kit at that place, and fit the pattern; each with its
  pictures, level and what it needs. Pick one: choose the session and version, sets and range
  (defaults from the catalogue), and the starting level (G).
- **Editing a session:** add, swap, remove, reorder, pair (ADR-0031), sets and range. Nothing
  changes until **Save**, which makes a plan version; the map updates as you edit.
- **Warnings, not rules:** a region left grey; a muscle on only one day a week; over about 11
  fractional sets for one muscle in one session; the same muscle hard on two days in a row; a
  session that will take over an hour (from the timings, ADR-0061); pushing without pulling.
- **Lengthened-position options first** in the picker's list where a muscle has one (Decided 5).

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
3. How many days a week? A starter for it: 3-day or 4-day full body, or the 7-day cycle
   (Decided 7).
4. Your levels (G).
5. The body map for the result; Save. Then the Plan tab for anything else.

The owner runs it once after A2 lands, starting from their current plan instead of a starter.

### I. Pictures in the builder

Every catalogue exercise and step shows its start and end pose (mannequin, animated, or two
frames with reduced motion). The picker needs them most: it's where people meet exercises they
don't know. The 29 gym exercises (Decided 5) add about 25 new poses to the roughly 100 already
planned; split squats, pull-ups, tibialis raises and neck work already have theirs.

## API, in outline

- `GET /api/catalogue`: exercises with muscles, pattern, steps, needs, pose ids.
- `GET /api/equipment`, `PUT /api/equipment`; `GET /api/equipment/unlocks?add=kettlebell:16`.
- `GET /api/plan` becomes the person's plan, with versions per place; `POST /api/plan/changes`
  saves a batch of edits against the plan's revision (a stale revision is refused, as day
  clashes are, ADR-0060) and returns the new version.
- `GET /api/plan/coverage?place=`: fractional weekly sets and days per muscle, with each
  muscle's band, for the map.
- `POST /api/plan/import`: `plan.toml`'s plan as a pending change to the owner's plan, to review
  and save (Decided 1).
- `PUT /api/plan/levels`: starting levels.
- Today and the guided session take `place`; kept sets carry `load_kg`.

## Suggested order (small PRs, each usable on its own)

1. **ADRs:** each person's own plan (A2; amends ADR-0059's Plans and multi-user Decided 7),
   equipment and places (C, E), load and double progression (D).
2. **Catalogue facts:** fixed muscles with their weights, patterns, needs in `plan.toml`. The
   Plan tab's volume chart uses the fixed list and fractional counting.
3. **Body map, read-only**, on the Plan tab, from the current plan, with the six bands and each
   muscle's own band.
4. **Equipment** on Account; concrete kettlebell and backpack steps; locked steps; Move up and
   Progress respect the kit. The 16 kg example works from here.
5. **Plans per person** (A2): the migration copies the plan to every user; the seed keeps the
   catalogue and starters; the canary test (multi-user L2) covers the plan routes.
6. **Edit the plan:** set level, swap, sets and range; Save makes a version. Import from
   `plan.toml` the same way.
7. **The picker and an interactive map:** add and remove exercises; add a session.
8. **Load:** the 29 gym exercises in the catalogue, `load_kg`, carry-over with − and +, double
   progression.
9. **Home and gym versions**, `workouts.place`, the switch on Today.
10. **Setup flow** (H), the 3- and 4-day starters, and the level questions (G1).

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
  will show lower numbers for the same plan, much of it light green (see "What this means for
  the current plan" under Decided). Say so in the release notes.
- **Thin evidence:** the small-muscle bands are reasoned defaults more than findings. Keep them
  in one place so a better study changes one number.
- **Size:** about ten PRs, several of them near the 400-line limit. The catalogue (step 2) and
  the gym exercises (step 8) are mostly data and review time.

## Sources

Read as abstracts and summaries rather than full texts; a few primary PDFs could not be fetched.

- Pelland, Remmert, Robinson, Hinson & Zourdos 2026, *Sports Medicine* 56:481-505: fractional
  counting fits best; no extra growth seen beyond about 31 fractional sets a week.
  https://doi.org/10.1007/s40279-025-02344-w
- Remmert et al. 2025, preprint: about 11 fractional sets per muscle per session; indirect sets
  worth about 39% for strength (exploratory). https://sportrxiv.org/index.php/server/preprint/view/460
- Mannarino 2021: curls grew the biceps about twice as much as rows.
  https://paulogentil.com/pdf/Single-Joint%20Exercise%20Results%20in%20Higher%20Hypertrophy%20of%20Elbow%20Flexors%20Than%20Multijoint%20Exercise.pdf
- Kubo 2019: full squats grew the glutes and adductors; the hamstrings did not grow.
  https://doi.org/10.1007/s00421-019-04181-y
- Plotkin 2023: squats and hip thrusts grew the glutes alike.
  https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2023.1279170/full
- Maeo 2023, *European Journal of Sport Science*: overhead triceps extensions grew every head
  more. The pressing finding (Wakahara 2013) is from a secondary report.
- Maeo 2021: seated leg curls grew the hamstrings more than prone.
  https://pubmed.ncbi.nlm.nih.gov/33009197/
- Kassiano 2023: calf raises in the stretched position. https://pubmed.ncbi.nlm.nih.gov/37015016/
- Schoenfeld, Ogborn & Krieger 2017: graded gains up to 10 or more sets a week.
  https://researchgate.net/publication/305455324
- Baz-Valle 2022: 12-20 sets as good as more than 20 in trained men, except triceps.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8884877/
- ACSM 2026 position stand, from its announcement: 10 or more sets per muscle, each muscle twice
  a week.
  https://www.newswise.com/articles/acsm-unveils-landmark-2026-resistance-training-guidelines-first-update-in-17-years
- Iversen 2021: at least 4 sets a week. https://pmc.ncbi.nlm.nih.gov/articles/PMC8449772
- Bickel 2011, maintenance: https://pubmed.ncbi.nlm.nih.gov/21131862/; Spiering 2021:
  https://pubmed.ncbi.nlm.nih.gov/33629972/
- Conley 1997: neck growth from neck work only. https://pubmed.ncbi.nlm.nih.gov/9189733
- Ylinen 2003, *JAMA*: neck strengthening and chronic neck pain.
  https://doi.org/10.1001/jama.289.19.2509
- Elliott 2021 and Daly 2021: neck strength and concussion, an association only.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7838928/
- Winters 2013: no shin-splint treatment proven better than another.
  https://www.springermedicine.com/treatment-of-medial-tibial-stress-syndrome-a-systematic-review/22253724
- Leong 2015, *Lancet*: grip strength and mortality (observational).
  https://doi.org/10.1016/S0140-6736(14)62000-6
- Huberman, Foundational Fitness Protocol:
  https://hubermanlab.com/newsletter/foundational-fitness-protocol; a third-party
  reconstruction: https://www.boostcamp.app/users/andrew-huberman-foundational-fitness-protocol
