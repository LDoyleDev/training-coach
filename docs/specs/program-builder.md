# Program builder, equipment and home/gym versions: a plan with options

Status: **decided 2026-10-21**: the owner answered every question (below, under Decided);
step 1's ADRs record the decisions. Written from the code on `main` at 0.32.0 and the owner's
answers in chat on 2026-10-21 (below, under Asked for). The muscle weights, bands, caps, gym
catalogue and starters come from a review of the research in
[program-builder-research.md](program-builder-research.md), which holds the evidence, the weight
of every exercise for every muscle, and the coverage tables; this file holds the decisions.

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
2. **Secondary muscles: fractional counting.** A set counts **1** for each prime mover, **0.5**
   for a meaningful synergist, **0.25** for a small part and **0** for stabilisers (Pelland 2026).
   Where growth studies measured a pairing, the weight follows them: glutes count 1 in deep
   squats and the leg press (and, as an estimate, split squats); adductors 1 in deep squats; hamstrings 0 in squats,
   leg press and hip thrusts; triceps 0.5 from pressing, biceps 0.5 from pulls. Neck, trunk
   bracing and posture drills count 0. Every exercise's weights, and which are estimates, are in
   the research file (Weights by exercise).
   - **Muscle parts compounds miss** get a flag on the map even when the muscle is green: the
     triceps **long head** (it needs an overhead extension) and the **rectus femoris** (a leg
     extension).
3. **Targets: the science, per muscle.** Six colour bands, in fractional hard sets a week:

   | Band | Sets a week | Means |
   | --- | --- | --- |
   | Grey | 0 | Not trained |
   | Amber | 1-3 | Below the effective minimum (about 4, Iversen 2021) |
   | Light green | 4-9 | Minimum effective; enough to maintain |
   | **Green** | **10-20** | The target (Schoenfeld 2017; ACSM 2026: 10 or more) |
   | Blue | 20-30 | High, for advanced people; diminishing returns |
   | Warning | over 30 | Past the point where more showed no extra growth (Pelland 2026) |

   Green also needs the muscle on **at least two days a week** (ACSM 2026). Smaller muscles have
   their own green band, each marked **low evidence** in the app except calves:

   | Muscle | Green (sets a week) | Evidence |
   | --- | --- | --- |
   | Neck | 3-9 per direction (flexion, extension); lateral 2-6 per side | Low |
   | Tibialis | 2-6; shown as covered or not | Very low |
   | Forearms | 4-10 | Low |
   | Calves | 8-16, standing and bent-knee | Moderate |
   | Side and rear delts | 8-20 | Low |
   | Front delts | Covered at 4 or more; no direct work suggested | Low: presses cover them |

   **Caps and warnings** (the evidence is in the research file, Overload):

   | Warning | When |
   | --- | --- |
   | Too much in one session | More than **11 fractional sets** for one muscle in one session (a preprint's plateau) |
   | Too much in a week | Over 30 fractional sets (the warning band) |
   | No rest between | **4 or more** fractional sets for one muscle on two days in a row |
   | Spine loading | More than **8 spine-loading hard sets** in one session (loaded squats, hinges, swings, back extensions, carries, bent-over rows; not bodyweight or jump squats), or heavy hinges on two days in a row |
   | Grip | More than about 8 grip-heavy sets in a session: suggest straps or a grip-free option |
   | Redundant | Direct front-delt work when presses already cover them; any exercise whose muscles are all green already |

   The spine, grip and rest-day warnings have no study behind them; the app says so.

4. **Home or gym on the day:** the last place used, with the switch on Today to change it (E).
5. **Gym exercises first:** the 29-exercise catalogue below, chosen from the research and
   Huberman's Foundational Fitness Protocol. The picker offers **lengthened-position** options
   first, which grew more muscle in head-to-head trials: overhead triceps extension, seated leg
   curl, Romanian deadlift, deep split squat, calf raises paused in the stretch (Maeo 2021, Maeo
   2023, Kassiano 2023). Huberman's protocol also pairs each muscle with a shortened-position
   exercise; that pick has the weakest support, except the leg extension, the only way to train
   the rectus femoris. Each exercise's muscle weights are in the research file.

   | # | Exercise | Pattern | Equipment | Simpler option |
   | --- | --- | --- | --- | --- |
   | 1 | Back or hack squat | squat | barbell / machine | goblet squat |
   | 2 | Bulgarian split squat | lunge | dumbbells | split squat |
   | 3 | Leg press | squat | machine | wall sit |
   | 4 | Leg extension | knee extension | machine | reverse Nordic |
   | 5 | Romanian deadlift | hinge | barbell / dumbbells | single-leg DB RDL |
   | 6 | Seated leg curl | knee flexion | machine | slider curl / Nordic |
   | 7 | Hip thrust | hip extension | barbell / machine | glute bridge |
   | 8 | 45° back extension | hinge | bench | bird-dog |
   | 9 | Copenhagen plank | adduction | bench | side-lying adduction |
   | 10 | Standing calf raise, paused in the stretch | plantarflexion | machine / step | single-leg on a step |
   | 11 | Seated calf raise | plantarflexion | machine | bent-knee DB raise |
   | 12 | Tibialis raise | dorsiflexion | tib bar | wall tib raise |
   | 13 | DB bench press | horizontal push | dumbbells | push-up |
   | 14 | Incline DB press | incline push | dumbbells | feet-elevated push-up |
   | 15 | Cable fly / pec deck | fly | cable / machine | band fly |
   | 16 | Seated DB overhead press | vertical push | dumbbells | pike push-up |
   | 17 | Cable lateral raise | abduction | cable | band raise |
   | 18 | Lat pulldown / pull-up | vertical pull | machine / bar | band pulldown |
   | 19 | Chest-supported row | horizontal pull | machine / dumbbells | inverted row |
   | 20 | Reverse pec deck / face pull | horizontal abduction | machine / cable | band pull-apart |
   | 21 | Incline DB curl | elbow flexion | dumbbells | band curl |
   | 22 | Hammer curl | elbow flexion | dumbbells | band hammer curl |
   | 23 | Overhead cable triceps extension | elbow extension | cable / dumbbell | band overhead extension |
   | 24 | Wrist curl / reverse wrist curl | wrist | dumbbell | towel wring |
   | 25 | Farmer carry | carry | dumbbells | suitcase carry |
   | 26 | Neck flexion / extension | neck | plate / harness | manual isometrics |
   | 27 | Neck lateral flexion | neck | plate / band | manual isometrics |
   | 28 | Cable crunch / hanging knee raise | trunk flexion | cable / bar | dead bug |
   | 29 | Pallof press / side plank | anti-rotation | cable / band | side plank |

   Rows 5, 6, 10, 21 and 23 are the lengthened-position picks, with deep range on 1 and 2. Home
   exercises already in the plan stay as they are and gain muscle weights; the home catalogue
   gains an **overhead kettlebell triceps extension**, the one home exercise for the long head.
6. **Weights:** kg only. Default increments barbell 2.5 kg, dumbbells 2 kg per hand, machines
   5 kg; each person can change theirs (D). Pounds when someone needs them.
7. **Starters for new people:** the 7-day cycle, plus a 3-day full-body and a 4-day
   upper/lower starter (H). Both are in the research file (Coverage): about 80 sets a week in
   19-22 exercises, every main muscle green on two or more days, at most 6 fractional sets for a
   muscle in one session. Beginners start one set lower per exercise for four weeks.
8. **A gym is complete:** every gym has everything in the catalogue, for now (C).
9. **No custom exercises at first:** only catalogue exercises, each with pictures, checked
   muscles and kit. People ask for additions to the catalogue instead.
10. **No "away" place:** travelling is Home, with whatever kit is there, or bodyweight only.

**What this meant for the plan.** Counted with the weights above, the plan's
78 sets a week reach the green band's 10 sets for 3 of the 10 main muscles (glutes, lats, upper
back), but legs are trained on one day, so quads, glutes and hamstrings fail the two-day rule:
2 are green (lats, upper back). Glutes also pass the per-session cap on Legs. Triceps get 6 sets with no long-head work; side delts 5.5. The research
file (Coverage) lists three changes with the home kit that make 8 of the 10 green at 93 sets;
the owner applied them with two more sets (curls and lateral raises) on 23 Oct 2026, so all ten
are green at 95 sets (`training-plan.md`). Huberman's shape (each
muscle twice a week, a compound plus a lengthened exercise, under an hour) stays; what the
evidence adds is sets. Monthly alternation between heavier and lighter schedules is harmless but
not reliably better (ACSM 2026), so it stays optional. **Later options**, not in these steps: a
strength mode (about 3-6 sets of the target lift a week over 2-3 days, at about 80% of a one-rep
max) and a maintenance mode (about a third of the building volume, at the same intensity).

## What's true today

### The plan is one shared copy

- `seed/plan.toml` is the plan; `make seed` loads it (`services/seed.py`). The plan tables carry
  no `user_id`: `exercises`, `ladder_steps`, `plan_versions`, `session_templates`,
  `template_items` (`db/models.py`). 32 exercises (2 retired), 7 sessions, 10 tests, 15
  stretches.
- **Per person already:** the place in the queue (`plan_state`, ADR-0006), the ladder step per
  exercise (`exercise_state`), settings, blocks (ADR-0028), test days (ADR-0037), every log.
- **Nobody can change the plan in the app.** `GET /api/plan` is read-only. Today's session can
  be moved, swapped or rested (ADR-0052), never edited. Levels are the one exception: Move up
  after a ready session, Not yet, or any step by hand on the Plan page (ADR-0016, ADR-0025,
  ADR-0075).
- Multi-user decided **D1 now, D3 later** (multi-user-plan.md, Decided 7; ADR-0059 "Plans"):
  everyone on the owner's plan with their own progress; each person's own copy is the goal, and
  new code should take the person's plan where that's as cheap as assuming one.

### There is no equipment and no load

- The product spec fixes the kit: 8 kg kettlebell, pull-up bar, chairs, floor. Weight exists only
  in ladder step names: `kb-swing` was "Two-hand, 8 kg", "One-arm, 8 kg", "Heavier kettlebell".
  Seven ladders ended in "Heavier kettlebell" or "Weighted backpack" (concrete since step 4).
- `set_logs` has one `value` (reps, seconds or minutes). No load column, no place.
- Progression is reps within a range (ADR-0027: +10% of the top of the range per set) and then a
  harder ladder step (ADR-0016). Targets and bests are scoped to the step and the block kind
  (ADR-0028), and history follows the exercise, never the plan day (ADR-0034).

### Muscles are fixed, with weights (step 2, ADR-0064)

- Each exercise in `plan.toml` names muscles from a fixed list of 21 with a weight (1, 0.5,
  0.25), qualities apart, a movement pattern, its shared stress and the kit each ladder step
  needs. `domain/volume.py` counts fractionally against 10-20 sets a week; the Plan tab, the
  weekly review and the stretching routine use it. Until step 2 these were 24 free tags, each
  set counting once per tag.

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

- **Muscles from a fixed list**, each with its weight (1, 0.5 or 0.25, Decided 2), replacing the
  free tags: `muscles = { quads = 1, glutes = 1, adductors = 1 }`, plus the muscle parts it
  reaches (`parts = ["triceps long head"]`) for the flags. About 21: neck, chest, front
  delts, side delts, rear delts, upper back, upper traps, lats, biceps, triceps, forearms, abs,
  obliques, lower back, glutes, hip flexors, adductors, quads, hamstrings, calves, tibialis.
  "shoulders", "core" and "grip" map onto these; posture, power, mobility and conditioning
  become **qualities**, kept apart from muscles (as `NON_MUSCLE_TAGS` does now). Each muscle's
  bands (Decided 3) live with the list.
- **A movement pattern:** squat, hinge, lunge, horizontal push, vertical push, horizontal pull,
  vertical pull, carry, core, isolation, mobility, cardio. Swap offers the same pattern first.
- **Whether it loads the spine or the grip**, for the shared-stress warnings (Decided 3).
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
- **Warnings, not rules:** the caps in Decided 3, plus a region left grey, a muscle on only one
  day a week, a flagged muscle part, a session that will take over an hour (from the timings,
  ADR-0061), and pushing without pulling.
- **Lengthened-position options first** in the picker's list where a muscle has one (Decided 5).

### G. Choosing the starting level

| Option | What |
| --- | --- |
| G1 **"Can you do ...?" questions** (recommended) | Walk the ladder from the bottom: "Can you do 8 good push-ups?" Yes moves on, No stops there. Two or three questions per exercise, written in the seed per step |
| G2 From the baseline tests (ADR-0037) | Max push-ups 20+ starts at step 3, and so on: a mapping per test. Good for the tested exercises only |
| G3 "Let the app find out" | Start at the easiest step; the first session is the baseline (ADR-0034) and Move up does the rest. Slow for a strong beginner |

G1 for everything, G2 as a suggestion where a test exists, G3 always available. A level can be
set by hand on the Plan tab too (down as well as up; it records an event, like Move up does).
**Set by hand: done** (ADR-0075): the Plan page's ladder panels, with Move up and Not yet, and
every "Ready to move up" links there. G1's questions are in the seed (ADR-0075) and the flow that
asks them comes with step 10; G2 is still to come.

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

### J. Time: rest inside pairs, fillers and kit (to decide)

The evidence and timings are in the research file (Time efficiency). The guided session rests
60 s after every set, inside a pair too, so pairs save no time today. Resting only after the
pair (15 s to move, 60 s after, 90 s when the two share a prime mover), with neck work and
other light items in a pair's rest, takes the current week from 197 to about 162 minutes and the
proposed one from 226 to about 187, for the same sets; every exercise still gets 104 s or more
between its own sets. To decide:

1. **Rest per transition** in the guided session and its time estimate (amends ADR-0031's
   timing; the pairs stay). **Done** (ADR-0065): 15 s to switch, 60 s after a pair or 90 s
   when it shares a prime mover, straight sets 90 s compound or 60 s small. Still to come:
   decisions 2 and 5 below.
2. **A third, light item in a pair** (the seed allows exactly two neighbours today), and pairs on
   the Recovery day.
3. **Pairing rules for the editor (step 6):** no shared prime mover without the longer rest, not
   two grip-heavy exercises, at most one spine-loading exercise per pair.
4. **Warm-up** 10 or 5 minutes (5 saves 15 minutes a week; a choice, not a finding).
   **Decided 30 Oct 2026** (ADR-0065 addendum): 5 minutes, in the guided session, its time
   estimate and the warm-up line before a resistance session.
5. **Drop sets and rest-pause:** an optional set type for isolation exercises, counted at
   matched volume, later. They save little inside pairs.
6. **Kit order** for the equipment step: 16 kg kettlebell, then a weighted vest; each saves
   4-7 minutes a week, far less than the rest change.

### K. Core and hips: the muscles the plan misses (decided 23 Oct 2026)

**Applied 23 Oct 2026** (plan version "Coverage + core"): decisions 1, 2 and 4 in `plan.toml`
and `domain/coverage.py`, the moderate cardio day renamed "Cardio + core"; decision 3 in the
app. All four were accepted as proposed.

The evidence, the block and its coverage are in the research file (Core and hips). The coverage
update (PR #289) left abs, obliques, lower back, hip flexors and adductors amber or grey, the
rectus femoris unreached and the upper traps grey. No growth trial exists for the trunk
muscles, so the choices rest on EMG, strength trials and estimates. The decisions:

1. **Own bands for the trunk and hips** (low evidence): abs 6-12, obliques 4-10, lower back
   4-10, hip flexors 3-8, adductors 4-10, in place of the general 10-20.
2. **The block:** reverse Nordic + side plank hip dip on Recovery; ab rollout + Copenhagen
   plank and back extension + side plank hip dip after the moderate cardio. Four new exercises,
   household kit (an ab wheel optional). Abs, obliques, lower back and adductors go green on two
   days, the rectus femoris is reached, hard sets 93 → 106, about 16-22 minutes a week more.
3. **"After your run" in the app** (done, ADR-0066): a conditioning session keeps its other
   items open that day once the cardio is logged (from the band, Telegram or the web), so the
   block is guided, saved with the day's workout and its ladders move.
4. **Upper traps stay grey** at home: no study shows shrugs grow them; a gym version can add
   farmer carries. **Revisited 25 Oct 2026:** with the 16 kg kettlebell coming, Liam chose
   suitcase carries on Recovery and Cardio + core (upper traps 0 → 4, an estimate), with band
   face pulls for the rear delts (7.25 → 9.25), plan version "Rear delts + carries".

### L. Gym versions of the sessions (proposed 27 Oct 2026, accepted by Liam as proposed 28 Oct 2026)

Builder step 9 puts a gym version on four of the seven sessions (`gym = [...]` in `plan.toml`).
The rules each one follows: the session's focus and order (power, then compounds, then small
muscles); about the same sets, and no muscle more than 1.5 fractional sets below the home
version (a test holds this, ADR-0064); the pairing rules (J3: at most one spine-loading or
grip-heavy exercise a pair, no shared prime mover except the neck pair the home version has);
loaded compounds at 6-10 or 8-12 and isolation work at 10-15 or 12-18, so double progression
has room (ADR-0072), every top at 18 or lower (ADR-0078); lengthened-position picks first
(Decided 5). Home exercises a gym does no better stay: the tibialis raise, neck work, the
Copenhagen plank, carries, chin-ups and diamond push-ups.

| Session | Home version (sets) | Gym version (sets) | Why |
| --- | --- | --- | --- |
| Legs | jump squat 3 + tibialis raise 3; KB swing 3 + calf raise 4; Bulgarian split squat 3 + hamstring curl 3; pistol squat 3 + single-leg RDL 3 (25) | jump squat 3 + tibialis raise 3; **back squat** 3 × 6-10 + **standing calf raise** 4 × 10-15; **barbell RDL** 3 × 6-10 + **leg extension** 3 × 10-15; **seated leg curl** 4 × 8-12 + **hip thrust** 3 × 8-12 (26) | Power first as at home; the squat and RDL carry the load, the leg extension reaches the rectus femoris, the seated curl and paused calf raise train in the stretch. Quads 7.5, adductors 3, calves 4 as at home; glutes 9 (10.5), hamstrings 7 (7.5). Spine-loading sets 6, under the 8 cap |
| Recovery + posture | posture, core, grip, neck side work, mobility | same as home | Light on purpose: nothing at a gym makes a recovery day better |
| Torso + neck | pull-up 4 + dip 4; KB row 3 + push-up 4; pike push-up 3 + reverse fly 3; neck flexion 2 + extension 2; lateral raise 3 + KB curl 2 (30) | **lat pulldown** 4 × 8-12 + **DB bench press** 4 × 6-10; **chest-supported row** 3 × 8-12 + **incline DB press** 4 × 8-12; **seated DB overhead press** 3 × 8-12 + **reverse pec deck** 3 × 12-18; neck flexion 2 + extension 2; **cable lateral raise** 3 × 12-18 + **incline DB curl** 2 × 10-15 (30) | One for one by pattern: every muscle has the home version's sets (chest 8, lats 7, upper back 6.5, front delts 7, rear delts 5.5, biceps and triceps 5.5, side delts 4.5); only the forearms lose a set. Pull-ups stay at home, where the bar is |
| Cardio + core | 30-40 min cardio; ab rollout 3 + Copenhagen plank 2; back extension 2 + side plank hip dip 2; band face pull 2 + suitcase carry 2 | the same cardio on a machine; **cable crunch** 3 × 10-15 + Copenhagen plank 2; **45° back extension** 2 × 10-15 + **Pallof press** 2 × 10-15 a side; **reverse pec deck** 2 × 12-18 + suitcase carry 2 | Cable work that loads the trunk and can add weight. Abs 4 (3.5), obliques 4 (4.75); the 45° bench moves 1 set from the lower back to the hamstrings. The cardio is counted once in the week's targets |
| High intensity | intervals | same as home | Bike or rower sprints at a gym are the same session |
| Arms + legs | chin-up 3 + diamond push-up 3; Bulgarian split squat 3 + overhead triceps extension 3; hamstring curl 3 + KB curl 4; lateral raise 4 + calf raise 4 (27) | chin-up 3 + diamond push-up 3; **leg press** 3 × 10-15 + **overhead cable triceps extension** 3 × 10-15; **seated leg curl** 3 × 10-15 + **incline DB curl** 4 × 10-15; **cable lateral raise** 4 × 12-18 + **seated calf raise** 4 × 10-15 (27) | Every muscle exactly as at home. The overhead cable extension keeps the long head, the incline curl trains the biceps in the stretch, the seated calf raise is the bent-knee calf work Decided 3 asks for |
| Long zone 2 | 45-75 min | same as home | A treadmill or bike is the same session |

Three gym catalogue exercises are in no session yet: the hammer curl, wrist curls and the cable
fly. They can be logged by text or voice and are there for the editor (steps 6 and 7).

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

1. **ADRs** (written and accepted by Liam 2026-10-25): equipment and places (C, E: ADR-0071), load and
   double progression (D: ADR-0072), each person's own plan (A2: ADR-0073; amends ADR-0059's
   Plans and multi-user Decided 7). **Order changed (Liam, 25 Oct 2026):** the gym steps come
   before plans per person, so the build order is 4, 8, 9, then 5, 6, 7, 10. The gym versions
   live in the shared plan until step 5.
2. **Catalogue facts** (done, ADR-0064): fixed muscles with their weights, patterns, needs in
   `plan.toml`. The Plan tab's volume chart uses the fixed list and fractional counting.
3. **Body map, read-only** (done): on the Plan page, from the current plan (each open session also shows its own map on a heat scale, and the week's is at the bottom: ADR-0069), with the six bands
   and each muscle's own band (`GET /api/plan/coverage`, `domain/coverage.py`). It shows the
   per-session, back-to-back, one-day, muscle-part, spine and grip warnings; a day for a muscle
   is a session with 2 or more of its sets (research file, Coverage). Read as built:
   - the two-day rule applies to the ten main muscles and those on the general band; the small
     muscles with their own band (neck, tibialis, forearms, rear and front delts) count as
     covered on one day;
   - neck is one muscle in the catalogue, so its 3-9 band counts flexion, extension and side
     work together;
   - spine-loading sets are counted at the step each person is on, so a split squat counts
     once it holds a kettlebell;
   - left for later: "heavy hinges on two days in a row" (needs load, step 8), the redundant
     and push-without-pull warnings and a session's length (editing, step 6), and the
     exercises that would add to a muscle (the picker, step 7).
4. **Equipment** on Account; concrete kettlebell and backpack steps; locked steps; Move up and
   Progress respect the kit. The 16 kg example works from here. **Backend done** (ADR-0071,
   Built): the `equipment` table, `/api/equipment`, locks on Progress and Move up. **Web
   done:** "My equipment" on Account (tap to add, what an item unlocks before adding it),
   locked steps and "Top for your kit" on the Plan page's levels and on Progress. The concrete
   steps are in `plan.toml` (accepted 25 Oct 2026,
   [kit-ladder-proposal.md](kit-ladder-proposal.md)), with step cues and band strengths. Still
   to come: figures for the new set-ups (the proposal's Figures section).
5. **Plans per person** (A2): the migration copies the plan to every user; the seed keeps the
   catalogue and starters; the canary test (multi-user L2) covers the plan routes. What reads
   the plan today and a draft migration: [plans-per-person.md](plans-per-person.md).
6. **Edit the plan:** set level (done, ADR-0075), swap, sets and range; Save makes a version. Import from
   `plan.toml` the same way.
7. **The picker and an interactive map:** add and remove exercises; add a session.
8. **Load:** the 29 gym exercises in the catalogue, `load_kg`, carry-over with − and +, double
   progression. **Built** (ADR-0072, Built): `set_logs.load_kg`, the weight on the set screen
   with − and + from last time, typed and spoken weights ("rows 10 10 9 at 16"), the suggested
   next weight (a tap), targets and bests per weight, the chart's period per weight with a kg
   strip, and 23 gym exercises (the other six are home ladders already). The AI's proposals
   and the summaries show weights too, and each person's own increments (Weight steps on
   Account) and the next weight owned at home are built.
9. **Home and gym versions**, `workouts.place`, the switch on Today. **Places built** (ADR-0071,
   Built): where you train on Account (home, gym or both), `workouts.place`, and
   `template_items.place` for a session's two versions. **Gym versions in `plan.toml`**
   (accepted 28 Oct 2026: L above) for Legs, Torso + neck, Cardio + core and Arms + legs;
   Progress shows their exercises to someone who trains at a gym. **The day's place** in the
   API: the guided session, the bot's messages and typed logs follow it, with the switch as
   `PUT /api/session/place`. **Built:** the Home | Gym switch on Today, which asks before
   dropping kept sets. **Built:** the next weight owned at home (ADR-0072) and the body map's
   home or gym view (`?place=`, Home | Gym on Plan for someone at both), which the exercise
   lists follow.
10. **Setup flow** (H), the 3- and 4-day starters, and the level questions (G1). It also asks
   the country of residence from the EU and EEA list and refuses "Somewhere else" (ADR-0085);
   until then it is set on Account (`/api/account/residence`).

Pictures arrive alongside, as poses are drawn: the set screen first, then the picker. Steps 2-4, 8 and 9
help the owner straight away with no change to how plans are stored; step 5 is the point of no
return and waits until they have settled (ADR-0073).

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
- **Thin evidence:** the small-muscle bands, the 0.25 weights and the spine, grip and rest-day
  warnings are reasoned defaults more than findings, and two key figures (the weekly curve, the
  11-set session cap) rest on summaries of papers that couldn't be fetched. Keep each in one
  place, the catalogue and the band list, so a better study changes one number.
- **Size:** about ten PRs, several of them near the 400-line limit. The catalogue (step 2) and
  the gym exercises (step 8) are mostly data and review time.

## Sources

In [program-builder-research.md](program-builder-research.md), each marked with how far it was
read.
