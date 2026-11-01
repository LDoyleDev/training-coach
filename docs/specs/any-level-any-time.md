# Any level, any time: a proposal (31 Oct 2026)

Status: **decided 31 Oct 2026** (Decided, at the end; ADR-0082 to ADR-0085). Built, by step of
the Suggested order: 1 (ADRs, #495); 2, "Short on time today" (#501, #502, #509, #510, #516,
#517); 3, stop signs and the talk test (#505); 4 started: a level, marks and `failure_ok` on
every step (#506), the entry exercises (#507, ADR-0083's addendum), the ladders' downward
migration (#508, built; its release waits for a Pi check and a dry run); 5 started: minutes per
session on Account (#524), the map at that length open. The Europe gate: layer 2 (#513); layers
3-4 (#514, #515) open. The evidence, with every
source and how far it was read, is in [any-level-research.md](any-level-research.md) (Part 1:
shorter sessions; Part 2: older, untrained and heavier people; Part 3: placing a person). This
file builds on the program builder ([program-builder.md](program-builder.md)): its levels (G),
setup (H) and starters (M) are where most of this lands.

## Asked for (31 Oct 2026)

1. **Less time.** Sessions down to about 40 minutes of work, for example pairs done twice
   instead of three times, with enough work in them that a person still reaches failure.
2. **Much lighter ladders.** Every area of the body from "can't do one push-up or one pull-up",
   older, untrained or obese, up to today's hard steps. A person says their general fitness and
   where they're starting; the app gives exercises that fit and builds them up.
3. **A plan that fits the time a person has,** built on day by day.

## The short answers

- **40 minutes is close to today's plan.** The app's estimator puts the home resistance days at
  42-44 minutes of work and the gym days at 36-42 (table under Time). Dropping each fourth set
  brings every resistance day to 42 minutes or less; two rounds of every pair brings them to 21-28. Your own
  times may differ: the app keeps each session's usual time (ADR-0061), and a shorter version
  should use it.
- **Two rounds keep most of the result.** On the best dose curve (Pelland 2026, square root),
  two rounds instead of three keep about 80% of the muscle growth and nearly all the strength
  gain (derived, approximate). Across the week, two rounds leave every main muscle between 4
  and 11 sets: light green, above the minimum of 4 that still grows muscle.
- **Failure doesn't buy the sets back.** With the sets equal, ending closer to failure adds
  about half a percent of growth per rep (Robinson 2024), and in trained people failure and
  stopping 1-2 reps short grew the same (Refalo 2024). Failure roughly doubles the next-day
  fatigue and is advised against for older people (ACSM 2026). Where it does matter is a light,
  high-rep set (Lasevicius 2022). The proposal: an optional "last set: as many good reps as you
  can" on exercises that are safe to fail on, not the default (Failure, below).
- **The ladders can go much lower.** Each main movement gets steps below today's bottom (a wall
  push-up, a sit-to-stand, a doorframe row, a supported split squat), five new entry exercises,
  a level on every step, and marks for what a step asks of the body (the floor, kneeling, impact,
  hanging), so a person can say "keep me off the floor".
- **Setup places a person and the first sessions correct it.** Safety questions, a few everyday
  ones ("can you stand up from a chair without your hands?"), optional quick checks, then the
  "Can you do...?" questions from a suggested level. A new rule suggests a step **down** when the
  bottom of the range is out of reach, which no published system defines.

## Part A: Time

### What's true today

The estimator in `services/guided.py` (45 s a set, ADR-0065's rests, both sides counted),
without the 5-minute warm-up:

| Session | As planned | Fourth sets dropped | Two rounds | One round |
| --- | --- | --- | --- | --- |
| Legs, home | 44 min, 25 sets | 42 min, 24 sets | 28 min, 16 sets | 13 min, 8 sets |
| Legs, gym | 36, 26 | 32, 24 | 21, 16 | 10, 8 |
| Torso + neck, home | 44, 30 | 39, 27 | 28, 20 | 14, 10 |
| Torso + neck, gym | 42, 30 | 36, 27 | 26, 20 | 13, 10 |
| Arms + legs, home | 42, 27 | 36, 24 | 24, 16 | 12, 8 |
| Arms + legs, gym | 36, 27 | 32, 24 | 21, 16 | 10, 8 |
| Recovery + posture | 40, 20 (10 of them the mobility flow) | same | 38, 19 | 25, 11 |
| Cardio + core | 52, 14 (30-40 of them cardio) | same | 50, 13 | 40, 7 |

The estimator runs high for short sets and has no way to know a person's pace; a session's
"usually" (the median of its last five timed totals, ADR-0061) is the better number once there
is one.

The week's fractional sets for the main muscles, the whole cycle at home:

| Muscle | As planned | Fourth sets dropped | Two rounds |
| --- | --- | --- | --- |
| Quads | 12.5 | 12.5 | 9 |
| Glutes | 15.5 | 15.5 | 11 |
| Hamstrings | 10.5 | 10.5 | 7 |
| Chest | 11 | 9 | 6 |
| Lats | 10 | 9 | 6 |
| Upper back | 11 | 10.5 | 8 |
| Biceps | 11 | 9.5 | 7 |
| Triceps | 10 | 9 | 6 |
| Side delts | 8.5 | 7.5 | 5 |
| Calves | 8 | 6 | 4 |
| Rear delts | 9.25 | 9 | 7 |
| Abs | 7 | 7 | 5 |
| All sets in the week | 118 | 111 | 86 |

Nothing shortens a session today. ADR-0053 rejected easing a session automatically, because it
changes the plan without asking; a shorter version the person picks is a different thing.

### How a session gets shorter

Decided: [ADR-0082](../adr/0082-shorter-sessions-time-budget.md) holds the rules (fourth sets,
then third sets, then whole exercises by a fixed key, a floor, ramp sets at 30 minutes or less).
After the plan review (31 Oct), pairs into threes is left for later and the trim never removes an
item, only sets its count to 0. Progress on a shorter day:
[ADR-0084](../adr/0084-short-days-last-set-and-stepping-down.md).

### Two ways to set the time

| Option | What | For |
| --- | --- | --- |
| T1 **Short on time today** | On the session overview and Today: As planned, 40, 30 or 20 minutes. Today only; the plan doesn't change. What's dropped is listed before Start; the guided session, the bot's work list and the time estimate follow it | A busy day |
| T2 **Minutes per session** | On Account and in setup: every session runs at that length unless the day says otherwise. The body map shows the week at that length, with what it costs ("at 30 minutes: chest 6 sets, light green") | Someone who always has 30 minutes |

Recommended: both, T1 first (it helps the owner now and needs no change to how plans are
stored). T2 then reuses T1's rules.

**Progress on a shorter day.** ADR-0016 judges "ready to move up" on every planned set at the
top of the range, and fills missing sets from the weakest one. A shortened day would need its
own planned sets to be the ones judged, so two rounds at the top count as ready; a change to
ADR-0016 that needs its own ADR.

### What fits a week (for setup and the starters)

At about 1.3 minutes a hard set in pairs (derived, matching Weakley 2017), a session of work
holds about 31 sets in 40 minutes, 23 in 30 and 15 in 20 (Part 1, Throughput):

| Time a week | Each main muscle (sets a week) | Band | Structure |
| --- | --- | --- | --- |
| 3 × 40 min | 10-14 | Green | 3-day full body |
| 2 × 40 min | 7-10 | Light green to green | 2-day full body |
| 3 × 30 min | 8-11 | Light green to green; better for strength than 2 × 40 | 3-day full body |
| 2 × 30 or 3 × 20 min | 5-7 | Light green | Full body, compounds first |
| 2 × 20 min | about 4 | The minimum | Compounds only; the app says it's the minimum |

- **A 2-day full-body starter** is missing today (Decided 7 has 3-day, 4-day and the 7-day
  cycle); setup would offer it for two days a week.
- **The honest note** setup shows: two strength sessions a week meet the WHO strength advice; the
  150 minutes of moderate cardio a week (or 75 vigorous) are separate, and walking counts. Lift
  first or on another day; cycling and walking interfere with muscle less than running (Part 1,
  Concurrent training).
- **Zone 2 has no minimum in the evidence** (Storoschuk 2025): with little time, harder cardio
  does more per minute. The 7-day cycle's Long zone 2 stays as it is; it's the time-rich
  option.

### Failure

| Option | What | Evidence |
| --- | --- | --- |
| F1 Keep 1-2 reps short everywhere | Today's rule (`training-plan.md`) | Failure and 1-2 short grew the same in trained people (Refalo 2024); failure doubles acute fatigue (Refalo 2023) |
| F2 **Last set: as many good reps as you can** (recommended) | An option per person, offered with a shorter session. Only on exercises marked safe to fail on in the catalogue: isolation and stable ones (curls, lateral raises, calf and tibialis raises, leg extension and curl machines, push-ups, band work). Never on jumps, swings, pistols, Nordics, loaded hinges, carries, neck work, ab rollouts or Copenhagen planks. Off for a new person's first 8 weeks | A small gain at equal sets, seen only in trained people (Grgic 2022); matters most for light, high-rep sets (Lasevicius 2022); the "safe to fail on" list is a design choice, as no study compares injuries |
| F3 Failure on every last set | Simplest | Not supported for compound bodyweight moves or older people (ACSM 2026) |

With F2, ADR-0016's targets need a change: "+1 on every set below the best" would chase the
last set's number on the earlier sets. The last set would count for readiness and bests, not
raise the others' targets.

## Part B: From the bottom

### What's true today

- **The bottoms assume a fit adult:** a standard push-up, pull-up negatives (most start at a
  strict pull-up), a Bulgarian split squat with the back foot on a chair, a pistol "sit to chair
  on one leg", an ab rollout from the knees, HIIT at 8 all-out rounds, zone 2 at 45-75 minutes.
- **Some exercises have no sensible bottom for a beginner:** the pistol and jump squats, swings,
  Nordic curls, the reverse Nordic, Copenhagen planks, ab rollouts, dips and HIIT. A beginner
  needs different exercises there, not a lower step of the same one.
- **The seed only adds steps at the end of a ladder** (`plan.toml`'s header; steps are matched by
  position). Each person's level (`exercise_state`) and every logged set point at the step's
  id, not its position, so a one-off migration can move a ladder's steps up to make room at the
  bottom without moving anyone's level or history. No migration has moved a step yet
  (`b7e1c3d5f9a2` deleted two); ADR-0083 sets out how the one migration does it, `start`
  included.

### B1. One level scale across all ladders

Every step gets a level, so a person's general level picks a sensible start everywhere and the
placement questions only fine-tune it. The anchors follow Vivifrail's bands (Part 2, Published
progression systems) at the bottom and today's ladders at the top:

| Level | Who | Anchor |
| --- | --- | --- |
| 1 Supported | Stands up from a chair only with the hands; walking a few minutes is hard | Vivifrail A-B; the 30 s chair stand scores 0 with the arms (STEADI) |
| 2 Starting | Stands up without the hands, no push-up from the knees, walks 10 minutes | Vivifrail C |
| 3 Building | Knee push-ups, a bodyweight squat, a 20-minute walk | Vivifrail D |
| 4 Regular | 10 push-ups, a first pull-up: today's bottom steps | Today's `start` |
| 5 Strong | Today's middle steps | |
| 6 Advanced | Today's top steps | |

### B2. Steps below today's bottom (draft)

Easiest first; the existing bottom step is in bold. Push-up order follows measured load
(Ebben 2011: hands at 61 cm 41% of body mass, knees 49%, hands at 30 cm 55%, floor 64%).

| Movement | New steps below today's bottom | Levels | Kit |
| --- | --- | --- | --- |
| Push-up | Wall push-up; hands on a kitchen counter; from the knees; hands on a stair or low step; **standard** | 1, 2, 3, 3, 4 | none |
| Split squat | Split squat holding a chair, short range; split squat, full range; **back foot on a chair** | 2, 3, 4 | a chair |
| Kettlebell swing | Hip hinge to a wall, no weight; kettlebell deadlift, 8 kg; **two-hand swing** | 2, 3, 4 | 8 kg |
| Row | Doorframe row, feet close; doorframe row, feet forward; **one-arm row, 8 kg** | 1, 2, 3 | a door frame |
| Pull-up | Scapular pulls; pull-up with feet on a chair; **slow negatives** (capped at 3 sets in the first weeks: eccentric-heavy work is the soreness and rhabdomyolysis pattern, Part 2, weak evidence) | 3, 3, 4 | bar |
| Calf raise | Both legs, hands on a wall; both legs on a step; **single leg on a step** | 1, 2, 3 | a step |
| Copenhagen plank | Side-lying adduction lift; **knee on a chair** | 2, 4 | none |
| Side plank hip dip | Side lean on a wall; **on the knees** | 1, 3 | none |
| Suitcase carry | Shopping bag, 3-5 kg; **8 kg** | 1, 3 | a bag |
| Neck flexion, extension, side | Seated, hand resistance, held; **lying, slow** | 1, 3 | none |
| Zone 2, moderate cardio | Easy walk, talking in sentences (the talk test, Part 2, Cardio); **brisk walk** | 1, 2 | none |

The ranges stay on the session items, so a starter for level 1-2 sets 5-15 minutes of walking
and 8-15 reps, not the 7-day cycle's 45-75 minutes.

### B3. New entry exercises

Where the movement differs from anything in the catalogue:

| Exercise | Steps (easiest first) | Levels | Why |
| --- | --- | --- | --- |
| **Squat** (the retired `goblet-squat`, revived and renamed: it keeps its history) | Sit to stand, hands push off; arms crossed; from a lower seat; to a chair, touch and go; full depth; fast up, slow down; then its old goblet steps | 1-3, then 4+ | The bridge out of chair-only work; fast-up is the power training older people need (ICFSR 2021) |
| **Glute bridge** | Glute bridge; 3 s hold at the top; single leg; shoulders on the sofa (hip thrust); single-leg hip thrust | 2-5 | The hinge for people before swings and RDLs (ROS factsheet) |
| **Step-up** | One stair, hand on the rail; one stair, no hands; two stairs; holding 8 kg | 1-4 | Functional, and doubles as cardio (ICFSR 2021) |
| **Plank** | Hands on a counter; on the knees; full plank; with an arm reach | 1-4 | A plank before the ab rollout (Part 2, Core) |
| **Balance** (seconds) | Feet together, holding a counter; hands near it; half heel-to-toe; heel-to-toe; one leg, a fingertip on the counter; one leg; one leg, eyes closed | 1-5 | Falls fall by about a quarter with balance work (Sherrington 2019); WHO asks 3 days a week from 65. Move on at 10 s without touching (Otago, SPPB) |
| **Interval walk** (rounds) | 3 min brisk / 3 min easy, 3 rounds up to 5 | 2-3 | The step between walking and HIIT: more leg strength and fitness than steady walking, in people averaging 63 (Nemoto 2007) |

Each needs figures (ADR-0063) and its "Can you do...?" questions (ADR-0075), as every step does.

### B2-B3 revised after the evals (31 Oct 2026)

A walk-through as four people (a frail 78-year-old who can't get to the floor, a 140 kg
beginner with sore knees, a trained woman with 20 minutes, a 60-year-old on beta-blockers) found
gaps in the tables above; this list replaces them as the draft to build (ADR-0083). Easiest
first, levels in brackets; **bold** is today's bottom step. Level-1 ranges start at 3-10.

| Area | Steps |
| --- | --- |
| Squat (entry; the revived `goblet-squat`) | Raised seat (a cushion), hands push off (1); sit to stand, hands push off (1); hands on thighs (1); arms crossed (2); a lower seat (2); to a chair, touch and go (3); to a chair holding a backpack (3); full depth (4); then the old goblet steps. "Fast up, slow down" in the cue from arms crossed on |
| Push-up | Wall (1); kitchen counter (1); table (2); chair seat against a wall (2); knees (3, kneeling); stair or low step (3); **standard** (4); ... ; vest or backpack, loaded (6, open top) |
| Plank | Hands on a counter (1); a table (2); a chair seat against a wall (2); knees (3); full (4); arm reach (5) |
| Side plank | Side lean on a wall (1); forearm on a counter (2); knees (3); **today's bottom** |
| Triceps | Armchair press-up, seated, push down on the armrests to lift the hips (1); band pushdown (2); then dips for those who get there |
| Row | Seated band row (1); one-arm row with a bag, about 4 kg (2); doorframe row, feet close (2; cue: a sturdy frame, both hands, only as far back as you stay in control); doorframe row, feet forward (3); **one-arm row, 8 kg** (4) |
| Rear delts | Band pull-apart (1); then today's steps |
| Pull-up | Band pulldown (2, for "No hanging"); pull-up with feet on a chair (3); scapular pulls (3); **slow negatives** (4, capped at 3 sets in the first weeks) |
| Hinge | Counter hinge, hands on the counter, hips back (1); hip hinge to a wall (2); good morning holding a backpack (3). Deadlift as its own ladder: bag from a block (2), 8 kg (3), 16 kg (4), 24 kg (5). Swings keep **two-hand swing** (4) |
| Glute bridge (entry) | Standing hip extension at the counter (1, the off-floor version); glute bridge (2, floor); 3 s hold (2); hip thrust, shoulders on the sofa (3); single-leg bridge (4); single-leg hip thrust (5) |
| Hamstrings | Standing hamstring curl at the counter (1); standing band leg curl (2); **towel slide** (4) |
| Hip flexors | Seated march (1); standing knee lift at the counter (2); then today's steps |
| Adductors | Seated pillow squeeze (1); standing band adduction (2); side-lying adduction (3, floor); short-lever Copenhagen, bottom foot down (3); **Copenhagen, knee on a chair** (4) |
| Lower back | Counter hinge (1); back extension lying on a bed (2); **superman** (4, floor) |
| Calf | Both legs, hands on a wall (1); both legs on a step (2); **single leg on a step** (3) |
| Tibialis | Seated toe lifts (1); **wall tibialis raise** (2) |
| Shoulders, arms | Seated bottle press (1); seated bottle lateral raise (1); **bottle lateral raise** (2); bottle curl, about 1 kg (1); bag curl, 2-4 kg (2); **8 kg curl** (3) |
| Step-up (entry) | 10 cm step, hand on the rail (1); one stair, hand on the rail (2); one stair, no hands (3); holding a bag (3); holding 8 kg (4) |
| Split squat | Holding a chair, short range (2); full range (3); back foot on a low step (3); **back foot on a chair** (4) |
| Carry | Static hold beside the counter, bag 1-3 kg (1); walking along the counter (2); bag 3-5 kg (2); **8 kg** (3) |
| Balance (entry) | As in B3, every step beside a counter at levels 1-3 |
| Cardio | Easy walk, can be split into short bouts (1); bike or seated stepping (1-3, knee-friendly); interval walk from 2 rounds (2-3); **brisk walk** (2) |

**Built (#507):** the entry exercises above, in no session yet; the squat and the low steps of
existing ladders come with the migration (#508). The neck had no level 1-2 step: the draft's
seated hand-resistance hold (B2) was the candidate, and #508 adds it (Liam, 1 Nov 2026).

**Built (#508):** migration `5ebed72122f7` puts the lower steps below fifteen ladders (push-up,
side plank hip dip, kettlebell row, pull-up, calf raise, suitcase carry, curl, lateral raise,
split squat, Copenhagen plank, back extension, zone 2, and a seated hand-resistance hold below
neck flexion, extension and side bend) and brings back the Squat; ADR-0083's second addendum
lists what was left out and why.

Neck work stays out of the starting starters. For people 65 and over the walk-through suggests
a daily 10-minute balance and sit-to-stand "snack" (WHO: 3 days or more; Sherrington 2019: the
falls effect needs about 3 hours a week of balance work); that belongs to the starting starters.

### B4. What a step asks of the body, and preferences

Steps get marks: **floor** (getting down to and up from it), **kneeling**, **impact** (jumps,
running, HIIT on the feet) and **hanging**. A person can switch on "Keep me off the floor",
"No kneeling", "No jumping or running" and "No hanging"; a marked step then isn't offered, and
the session uses the exercise's marked alternative (a standing hip hinge for the glute bridge,
an incline plank for the plank). These are preferences, not conditions: the app never asks for
a diagnosis or stores one. The evidence for obesity-specific positions is practitioner advice
(Part 2, weak); the switches let the person decide.

### B5. Placement: setup, extended

Builder H's flow, with what the research adds (Part 3, Implications; Part 2, Screening):

1. **Safety questions,** our own, modelled on the ACSM 2015 screening (PAR-Q+'s licence forbids
   editing it, so the app links to the official form instead). Heart, kidney or blood-sugar
   disease; chest, jaw or arm discomfort, fainting, unusual breathlessness; a doctor's advice to
   exercise only under supervision; a recent heart event or fracture; pregnancy. **The answers
   aren't stored.** They lead to one of three notes: "see a doctor before you start" (symptoms,
   or known disease and inactive: light work only, no HIIT); "check before hard sessions"
   (known disease and active, or over 45 and new to hard effort); "start easy and build up".
   The person can continue either way.
2. **Everyday questions** in our own words, like the SF-36 and DASI items: stand up from a chair
   without your hands? climb a flight of stairs? walk 10 minutes without stopping? get down to
   the floor and up again? They suggest a level (1-3) and the floor preference. A single "rate
   your fitness" question places individuals poorly (Jensen 2018), so the app doesn't ask one.
3. **Optional quick checks,** only those safe alone: the 30 s chair stand (STEADI norms from 60),
   a push-up attempt stepping down from the floor to the knees, the counter and the wall, and a
   balance stance next to a counter. No 12-minute run or maximal test (Mittleman 1993).
4. **"Can you do...?" per movement,** starting from the suggested level and walking up or down,
   so a beginner isn't asked about archer push-ups.
5. **Kit and place** (built), **which days** (tapping the days helps people keep to it a little,
   Bélanger-Gravel 2013) and **minutes per session** (T2).
6. **Goal,** last, for emphasis only: stay independent, get stronger, build muscle, general
   fitness.
7. **The suggested starter,** shown on the body map at the chosen minutes; the person changes
   anything and saves.

### B6. The first weeks, and stepping down

- **An easy start for a new person:** two weeks of one or two sets of three or four exercises,
  well short of failure, and 5-10 minutes of cardio (ICFSR 2021). An easy first bout protects
  against soreness for about two weeks (Chen and Nosaka, small studies). This generalises
  Decided 7's "one set lower for four weeks".
- **A step-down suggestion** (new; no published system has one): two sessions in a row with most
  sets below the bottom of the range, the weaker side counted, offer the step below with a tap.
  After three weeks or more off, offer a step down too. The person decides, as with Move up.
- **Effort words for a new person:** rep counts and "stop when the next rep would lose its
  form", not reps in reserve; ACSM 2026 finds no evidence for exact effort targets.
- **A re-check** every 6-12 weeks offers the quick checks again (Vivifrail re-tests at 6 and
  12).

### B7. Stop signs and heart rate

- **Stop signs,** before the first session and one tap away in the guided session: chest, jaw or
  arm pain or pressure, dizziness or fainting, unusual breathlessness, or palpitations with any
  of these mean stop and get help (call 112 if it doesn't settle); sharp joint pain means stop
  and try an easier step; very dark urine after a hard session means see a doctor (Part 2,
  Stop signs; the wording needs checking by a clinician).
- **"Use the talk test, not heart-rate zones"** (decided, ADR-0083 and ADR-0085: named neutrally
  and asked without a reason; it suits people whose heart rate is slowed by medicine or paced,
  which the app doesn't ask about): the cardio zones then show the talk test instead (ICFSR
  2021; Reed and Pipe 2014).

## Starters by level

Builder M's 3- and 4-day starters suit levels 4-6. With B2 and B3 most of their exercises have
steps down to level 2-3; the ones without a low bottom (pistol, jump squat, swing at 8 kg, dips,
pull-ups, Nordics, reverse Nordic, ab rollout, HIIT) need replacing. Options:

| Option | What | Pros | Cons |
| --- | --- | --- | --- |
| S1 **"Starting" versions** (recommended) | A 2-day and a 3-day full-body starter written for levels 1-3: squat, glute bridge or step-up, push-up from the wall up, doorframe row, plank, balance, calf raise, a walk. Written and checked like M | Reviewable, like every starter so far | Two more starters in `plan.toml` |
| S2 Swap at run time | Each exercise names its entry exercise; below its bottom level the session uses that one | One starter per day count | Generated sessions are harder to review; the picker (step 7) is where swapping belongs |

## In the code, in outline

- **`plan.toml`:** `[exercises.levels]` per step, step marks, `failure_ok` per exercise, the
  new steps and exercises, their questions and cues, the 2-day and starting starters.
- **Seed:** steps added below an existing bottom by a one-off migration that moves the ladder up;
  a test that every step has a level.
- **`domain/`:** a pure `trim` that takes a session's items, what each trains, the minutes and
  the person's pace, and returns the shorter version; the estimate uses it.
- **Settings:** minutes per session, the four preferences, "use the talk test". They are stored
  as preferences, in the export and erased with the account; not shown over Telegram or MCP
  (ADR-0083). **`workouts`:** the minutes chosen and the sets planned (ADR-0084).
- **ADRs:** the time budget and its rules; levels and preferences; the safety questions (not
  stored); stepping down; ADR-0016's changes (a shorter day's sets; a last set to failure).

## Suggested order

Builder step 5 (plans per person) waits for Liam's go around 4 Nov; these steps don't depend on
it, except the starters, which live in `plan.toml` after it (ADR-0073).

1. **ADRs** for what Liam decides here.
2. **Short on time today** (T1) with ADR-0084's shorter-day progress rule and the stored
   planned sets: the trim, the overview and Today, the guided session and the bot. Several PRs,
   usable once all are in.
3. **Stop signs and the talk test** (B7): small.
4. **The catalogue from the bottom** (B1-B4): levels, marks, the migration, the new steps and
   exercises with questions. Mostly data and review; figures follow as poses are drawn.
5. **Minutes per session** (T2) and the map at that length.
6. **Stepping down, the easy start and the failure option** (B6, F2): the ADR-0016 changes.
7. **Setup** (builder step 10) with B5 and the starting starters.

## Risks

- **Health advice.** Safety questions, stop signs and condition notes are close to medical
  territory. The app gives general advice with its sources, never a diagnosis, and stores no
  answers; the wording should be checked by a clinician before anyone but the owner uses it.
- **Thin evidence at the bottom.** No study validates the rep counts for moving between
  bodyweight steps, any step-down rule, or the floor and position advice for people with
  obesity (Part 2 and 3, gaps). The percentages for fewer rounds are arithmetic on one model,
  shown as approximate.
- **Size.** About 6 new exercises, 30 new steps and their figures, two starters, five ADRs.
  The catalogue work is mostly review time.
- **Generated sessions** are less reviewable than written ones. Tests pin the trim's rules, and
  the person sees what's dropped before Start.
- **Volume numbers fall** on short weeks; the map shows light green honestly instead of hiding it.

## Decided (31 Oct 2026, Liam)

1. **Shorter sessions:** both. "Short on time today" (T1) first, then "Minutes per session"
   (T2). ADR-0082.
2. **The trim's order:** as proposed. **The warm-up:** a very short session swaps the 5 minutes
   for ramp sets of the first exercise; "very short" is taken as 30 minutes or less (the
   proposal's line; Liam can lower it). ADR-0082.
3. **Failure:** F2, the optional last set. ADR-0084. (ADR-0027's per-set targets already keep
   one big last set from raising the other sets' targets, so the target rule doesn't change.)
4. **The level scale:** the six levels, **open at the top**: where load can keep rising (push-ups,
   pull-ups, dips with a vest or weights) the ladder keeps going above today's top, and levels
   place people, never cap them. ADR-0083.
5. **Lower steps:** option A (extend the ladder where the movement is the same, entry exercises
   where it differs), and, where an exercise has no sensible low step, an easier exercise that
   trains the same muscles, so an older or unwell person has a way in for every muscle.
   ADR-0083.
6. **Preferences:** the four switches. They are preferences, not medical: the app isn't
   interested in conditions or diagnoses. People take responsibility for what they feel ready
   and able to do, and get medical advice if they need it. ADR-0083.
7. **Safety questions:** whatever is appropriate in Europe, researched; and the app can't be
   used outside Europe. ADR-0085: ten questions in our own words, answered on the device, three
   notes that never block; the EU and EEA only, in four layers. It supersedes B5.1 above and
   ADR-0046's stored answers.
8. **Starters:** S1, written "starting" versions (2- and 3-day). They live in `plan.toml` after
   builder step 5 (ADR-0073).
9. **Order:** as suggested, with T1 next, alongside step 5.
