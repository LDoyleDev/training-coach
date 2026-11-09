# Any level, any time: a proposal (31 Oct 2026)

Status: **decided 31 Oct 2026** (Decided, at the end; ADR-0082 to ADR-0086). Built, by step of
the Suggested order: 1 (ADRs, #495); 2, "Short on time today" (#501, #502, #509, #510, #516,
#517); 3, stop signs and the talk test (#505; checked against European sources, #556); 4: a level, marks and `failure_ok` on every step
(#506), the entry exercises (#518-#520, #523), the four preferences and "Easy on my knees"
locking steps (#531, #541), the ladders' downward migration built and dry-run (#534, released
alone); 5: minutes per session (#529), the map at that length open; 6: the step-down suggestion
and "Ease back in" (#530, #532, #533), the optional last set (#536), the easy start a follow-up
to the walk-through (ADR-0092, Decided 12); 7: the starters (S1) built, the walk-through decided
9 Nov 2026 (ADR-0092) and being built. Added 1 Nov: Away, no
equipment (#538, #539, ADR-0086). The Europe gate: layer 1, the Cloudflare rule (2-3 Nov);
layer 2 (#513); layer 3 on Account until sign-up (#515) and layer 4 (#514), released in
1.16.0. The evidence, with every
source and how far it was read, is in [any-level-research.md](any-level-research.md) (Part 1:
shorter sessions; Part 2: older, untrained and heavier people; Part 3: placing a person). This
file builds on the program builder ([program-builder.md](program-builder.md)): its levels (G),
setup (H) and starters (N) are where most of this lands.

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
| T1 **Short on time today** | On the session overview and Today: As planned, and whichever of 40, 30 or 20 minutes is shorter than the session. Today only; the plan doesn't change. What's dropped is listed before Start; the guided session, the bot's work list and the time estimate follow it | A busy day |
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

Status (9 Nov 2026): **decided**, as the walk-through in
[ADR-0092](../adr/0092-the-walk-through.md), which settles the order, the suggested-level rule,
the ladder walk and what's kept; being built (#577, stage 5). Not in it: the goal (6) and the
quick checks (3) (ADR-0092, Decided 11).

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

**The owner's answers (7 Nov 2026):**

- **Everything starts at the bottom.** A new plan has every exercise at the lowest step of its
  ladder; the walk-through then moves each one up to where the person wants to start. The aim is
  a start that is positively doable and never too hard, for anyone: old or young, fit or unfit.
- **The order:** the safety questions first (on the device, nothing stored, as 1 above). Then
  age, and how they exercise now: how often, how hard (out of breath, or able to hold a
  conversation) and for how long. Then "can you do...?" per movement: any push-ups, and how many?
  a pull-up? and so on, walking up or down from there (4 above). Take the time it needs.
- **How much they can do:** days a week, minutes per session, exercises per session, and kit and
  place.
- **The plan:** from a small set of starters Liam approves (by days a week and place), fitted to
  the answers: the starter is picked, each exercise set to its level, and the session trimmed to
  the minutes and exercise count.
- **The answers are kept,** apart from the safety questions, with a consent step at the start of
  the walk-through (`multi-user-plan.md`, Decided 2026-11-07).

### B6. The first weeks, and stepping down

Status (9 Nov 2026): the step-down suggestion is built (#530); the easy start and the re-check are
follow-ups to the walk-through, which will offer the easy start as a switch (ADR-0092, Decided 12
and 13).

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

- **Stop signs,** before the first session and one tap away in the guided session, with one
  reminder line on every session and test day. The wording lives in
  `frontend/src/session/safety.ts`; its sources are research Part 2 (Stop signs) and Part 5 (the
  European wording review, 1 Nov 2026). It needs checking by a clinician.
- **"Use the talk test, not heart-rate zones"** (decided, ADR-0083 and ADR-0085: named neutrally
  and asked without a reason; it suits people whose heart rate is slowed by medicine or paced,
  which the app doesn't ask about): the cardio zones then show the talk test instead (ICFSR
  2021; Reed and Pipe 2014).

## Starters by level

Builder N's 3- and 4-day starters suit levels 4-6. With B2 and B3 most of their exercises have
steps down to level 2-3; the ones without a low bottom (pistol, jump squat, swing at 8 kg, dips,
pull-ups, Nordics, reverse Nordic, ab rollout, HIIT) need replacing. Options:

| Option | What | Pros | Cons |
| --- | --- | --- | --- |
| S1 **"Starting" versions** (recommended) | A 2-day and a 3-day full-body starter written for levels 1-3: squat, glute bridge or step-up, push-up from the wall up, doorframe row, plank, balance, calf raise, a walk. Written and checked like N | Reviewable, like every starter so far | Two more starters in `plan.toml` |
| S2 Swap at run time | Each exercise names its entry exercise; below its bottom level the session uses that one | One starter per day count | Generated sessions are harder to review; the picker (step 7) is where swapping belongs |

### S1: the starters, by days a week and place (approved 8 Nov 2026)

Liam approved this on 8 Nov 2026 with the answers below (Decided). It replaces the 7 Nov draft
of the 2- and 3-day starters, after Liam's answers in B5: everything starts at the bottom of its ladder, the
walk-through moves each exercise up, and the session is trimmed to the person's minutes and
number of exercises.

**The short version.**

- **Three starters: 2, 3 and 4 days a week.** The same starter serves home and the gym; at the
  gym, an exercise someone is placed high on becomes a machine or a free-weight lift (Gym, below).
  There is no 1-day or 5-day starter (below).
- **One set for everyone.** Because every exercise starts at its lowest step, the same list has
  to suit a frail 80-year-old and a fit 30-year-old. So the exercises are ones whose ladders run from
  level 1 or 2 up to level 4-6 with no kit. The hip hinge, which stopped at level 3, gets three
  steps at its top (Decided, 2).
- **Every main muscle gets at least 4 sets a week** (the least shown to grow muscle) on all three,
  most of them on two days, except the rear delts on the 2-day (3, amber; judgment calls,
  below). The 3- and 4-day starters reach the full target for a few muscles.
- **Sessions are 32-42 minutes on the 2- and 3-day starters (3-day C is the short one) and 26-35
  on the 4-day**, so the 40, 30 and 20-minute versions have something to cut, and the trim cuts
  what matters least first.

**What changed since the 7 Nov draft.**

- Out: the seated press, standing hamstring curl and seated toe lift, whose ladders end at level
  2-3, and the step-up, which ends at 3 without a kettlebell. The split squat takes the step-up's
  place: it ends at level 4 with no kit and 6 with a kettlebell.
- No walk inside a session. The trim (ADR-0082) keeps cardio until the end, so at 20 minutes a
  walk would fill half the session. Cardio stays separate (Part A's note), and the easy start's
  5-10 minutes of walking (B6) still sits on top.
- The rep ranges are the ones the "Can you do...?" questions ask about (push-ups 10-18, because
  the questions ask for 10), so a yes means the person can do the bottom of the range on that step.
- New: a 4-day starter, the gym versions, and the order each session is cut in.

**How a starter becomes someone's plan.** The days a week pick the starter. Every exercise starts
on its bottom step, and the "Can you do...?" answers move each one up. The minutes per session
and the number of exercises then trim each session, in the order given below. At the gym, an
exercise placed high enough is swapped for its gym version.

**How the numbers were got, and how to read them.** Each draft was run through the seed in a scratch
database, with every exercise on its bottom step, and took the numbers the app itself gives:
`plan_coverage` for the sets, the guided estimate for the minutes, and `domain/trim.py` for the
shorter versions. (This method gives the 7 Nov draft's 35 minutes for its 2-day A.)

- **Sets a week** are what the body map counts. A set counts 1 for a muscle the exercise mainly
  works and 0.5 for one that helps, so a push-up set is 1 for the chest and 0.5 for the triceps.
- **The colours:** amber is under 4 sets a week, the least shown to grow muscle (Iversen 2021);
  light green is 4 up to the target; green is the target, which for the big muscles is 10-20 sets
  on two days or more. Some smaller muscles have their own, lower targets (calves and side delts
  8, abs 6, lower back and adductors 4).
- **Minutes** are the app's estimate: 45 seconds a set, the rests the guided session uses, both
  sides counted for one-sided exercises, and the 5-minute warm-up. It runs high for short sets;
  once someone has done a session, their own time replaces it (ADR-0061).

#### The sessions

"a + b" means the two are done in turn, set by set. The minutes are as planned and in the
shorter versions; "Short on time today" only offers lengths shorter than the session.

**2-day full body:** A and B.

| Session | Exercises, in order (sets) | As planned | At 40 / 30 / 20 min |
| --- | --- | --- | --- |
| A | squat 3 + door-frame row 3; push-up 4 + hip hinge 3; calf raise 3 + plank 3; lateral raise 3 + side plank hip dip 2 a side; balance 2 | 26 sets, 40 min | as planned / 25 min, 18 sets / 18 min, 14 sets |
| B | split squat 3 a side + push-up 4; glute bridge 3 + door-frame row 3; hip hinge 2 + lateral raise 3; calf raise 3 + curl 2; plank 2 + balance 2 | 27 sets, 42 min | 40 min, 26 sets / 27 min, 20 sets / 20 min, 12 sets |

**3-day full body:** A, B and C.

| Session | Exercises, in order (sets) | As planned | At 40 / 30 / 20 min |
| --- | --- | --- | --- |
| A | squat 3 + door-frame row 3; push-up 4 + hip hinge 3; calf raise 3 + plank 2; lateral raise 3 + curl 2; balance 2 | 25 sets, 38 min | as planned / 24 min, 18 sets / 18 min, 14 sets |
| B | split squat 3 a side + push-up 4; glute bridge 3 + door-frame row 3; lateral raise 3 + side plank hip dip 2 a side; calf raise 3 + balance 2 | 23 sets, 40 min | as planned / 25 min, 16 sets / 19 min, 12 sets |
| C | squat 3 + door-frame row 3; push-up 3 + glute bridge 3; hip hinge 2 + lateral raise 2; calf raise 2 + plank 2; balance 2 | 22 sets, 32 min | as planned / 29 min, 22 sets / 20 min, 14 sets |

**4-day upper and lower:** Lower 1, Upper 1, Lower 2, Upper 2.

| Session | Exercises, in order (sets) | As planned | At 30 / 20 min |
| --- | --- | --- | --- |
| Lower 1 | squat 3 + calf raise 3; hip hinge 3 + plank 3; split squat 2 a side + tibialis raise 2; balance 2 | 18 sets, 28 min | as planned / 20 min, 14 sets |
| Upper 1 | push-up 4 + door-frame row 4; lateral raise 3 + curl 3; side plank hip dip 2 a side | 16 sets, 28 min | as planned / 17 min, 10 sets |
| Lower 2 | split squat 3 a side + calf raise 3; glute bridge 3 + side plank hip dip 2 a side; hip hinge 2 + plank 2; squat 2; balance 2 | 19 sets, 35 min | 26 min, 16 sets / 18 min, 8 sets |
| Upper 2 | door-frame row 4 + push-up 4; lateral raise 3 + curl 3; plank 2 | 16 sets, 26 min | as planned / 20 min, 14 sets |

The shorter times assume the person's first exercise is above level 3, so ramp sets replace the
warm-up at 30 minutes or less. For someone whose first exercise is at level 3 or below, the
5-minute warm-up stays (ADR-0082), and a 20-minute session keeps 6-10 sets instead of 8-14.

#### The trim order

When a session is too long for the person's minutes, the trim (ADR-0082) takes off every fourth
set, then every third set (each exercise keeps two), then whole exercises, one at a time, in the
order below. For "how many exercises", the same order is used, so there is one list to check.

| Session | Goes first ... kept longest |
| --- | --- |
| 2-day A | side plank hip dip, lateral raise, plank, calf raise, balance, hip hinge, push-up, door-frame row; squat |
| 2-day B | plank, curl, calf raise, lateral raise, glute bridge, balance, hip hinge, door-frame row; split squat and push-up |
| 3-day A | curl, lateral raise, plank, calf raise, balance, hip hinge, push-up, door-frame row; squat |
| 3-day B | calf raise, side plank hip dip, lateral raise, glute bridge, balance, door-frame row; split squat and push-up |
| 3-day C | plank, calf raise, lateral raise, glute bridge, balance, hip hinge, push-up, door-frame row; squat |
| Lower 1 | tibialis raise, plank, calf raise, split squat, balance, hip hinge; squat |
| Upper 1 | side plank hip dip, curl, lateral raise, door-frame row; push-up |
| Lower 2 | plank, side plank hip dip, calf raise, glute bridge, split squat, balance, squat; hip hinge |
| Upper 2 | plank, curl, lateral raise, push-up; door-frame row |

The order comes from the trim's rule, not from the list: small exercises go first, starting with
those whose muscles another exercise in the session still works, and big movements that nothing
else covers go last. Within a group, the one later in the list goes first. Each list is ordered so
that rule removes what matters least. At the gym the order is the same, except where the 45°
back extension takes the glute bridge's place. As the last exercise left for the hamstrings, it
is kept until just before the push-up (2-day B, 3-day B) or the split squat (Lower 2), and in
2-day B and Lower 2 the Romanian deadlift goes just before balance. In Lower 2 the leg press
goes fourth, so the split squat is kept longest.

#### Sets a week, as the map counts them (home)

| Muscle | 2-day | 3-day | 4-day |
| --- | --- | --- | --- |
| Quads | 6, light green | 9, light green | 10, green |
| Glutes | 11.5, green | 17.5, green | 15.5, green |
| Hamstrings | 6.5, light green | 8, light green | 6.5, light green |
| Chest | 8, light green | 11, green | 8, light green |
| Lats | 6, light green | 9, light green | 8, light green |
| Upper back | 6, light green | 9, light green | 8, light green |
| Triceps | 4, light green | 5.5, light green | 4, light green |
| Biceps | 5, light green (one day) | 6.5, light green (one day) | 10, green |
| Side delts | 6, light green | 8, green | 6, light green |
| Calves | 6, light green | 8, green | 6, light green |
| Rear delts | 3, **amber** | 4.5, light green | 4, light green |
| Abs | 5.5, light green | 4.5, light green | 8, green |
| Obliques | 4.5, green | 4, green | 7.5, green |
| Lower back | 5, green | 5, green | 5, green |
| Adductors | 4.5, green | 7.5, green | 7.5, green |
| All sets a week | 53 | 70 | 69 |

Forearms are amber everywhere (0.5-1.5) and tibialis is only in the 4-day (2, green), as in the
7 Nov draft. "One day" means only one session gives that muscle 2 sets or more. That keeps it from
being green, but not from being light green.

- **At 30 minutes** every main muscle stays at 4 sets or more, except the triceps (2-3.5) on the
  2- and 3-day starters. **At 20 minutes** most main muscles keep 4-12, while the triceps,
  biceps and calves drop under 4 on the 2- and 3-day starters, and the 2-day's side delts drop to
  none. The map shows that honestly.
- **At the gym, with every swap made,** the numbers are the same apart from these (rerun on 9
  Nov 2026 with the seed's gym swaps, `[[gym_swaps]]`): the lower back 4 (green) on all three,
  where the Romanian deadlift alone would leave 2.5 (amber), as it counts it half; the 45° back
  extension in place of the glute bridge in 2-day B, 3-day B and Lower 2 makes up the rest
  (Decided 10). The hamstrings 8 on all three, from the back extension, and the glutes 10, 16
  and 14 (still green), as it counts them half where the hip thrust counts 1. The upper back 4.5 (one day), 7.5 and
  6, and the rear delts 2-4 (amber on all three), as the lat pulldown counts each half; the
  adductors 3 (amber) on the 2-day and 4.5 and 5 on the others, as the leg press counts them
  half; and the forearms 3-4, from the Romanian deadlift's grip. The minutes keep their home
  numbers, the shorter versions too. 2-day B and Lower 2 reach 8 spine-loading sets, the map's
  cap, without going over.
- **Back to back:** with the 2- and 3-day sessions queued without rest days, the map warns that
  the glutes and chest are worked on two days running (A then B). Rest places in the queue (Decided 9)
  keep them apart.

#### How far each exercise climbs

| Exercise | Bottom step (level) | Top step with no kit | With a kettlebell | At the gym, from |
| --- | --- | --- | --- | --- |
| Squat | raised seat, hands push off (1) | full depth (4) | 16 kg (5) | leg press, from "to a chair, touch and go" (3) |
| Split squat | holding a chair, short range (2) | back foot on a chair (4) | 16 kg + 8 kg (6) | stays |
| Push-up | hands on a wall (1) | archer (6) | | dumbbell bench press, from "standard" (4) |
| Door-frame row | upright, a step back (2) | one arm (6) | | chest-supported row, or the lat pulldown in 2-day B, 3-day B and Upper 2, from "leaning back, half a step in" (3) |
| Glute bridge | standing, at the counter (1) | single leg, shoulders on the sofa (5) | | barbell hip thrust, or the 45° back extension in 2-day B, 3-day B and Lower 2 (Decided 10), from "single leg, on the floor" (4) |
| Hip hinge | hands on the counter (1) | single leg, holding a bag (5; Decided 2) | | barbell Romanian deadlift, from "single leg, hand on the counter" (4) |
| Calf raise | both legs, hands on a wall (1) | one leg on a step (3) | 8 kg, pause at the top (5) | standing calf raise machine (seated in 2-day B, 3-day B and Lower 2), from one leg on a step (3) |
| Plank | hands on a counter (1) | full plank, arm reach (5) | | stays |
| Side plank hip dip | side lean on a wall (1) | top leg raised (5) | 8 kg on the hip (6) | stays |
| Lateral raise | seated, water bottles (1) | lean-away, one arm (4) | | cable lateral raise, from lean-away (4) |
| Curl | water bottles (1) | a bag, 2-4 kg (2) | 16 kg, slow (6) | incline dumbbell curl, from 8 kg (3) |
| Balance | feet together, holding the counter (1) | one leg, eyes closed (5) | | stays |
| Tibialis raise | back against a wall (2) | single leg (4) | 8 kg (5) | stays |

Nothing needs kit at its bottom step: a wall, a counter, a chair, a stair, a door frame and two
water bottles. With "Keep me off the floor", the push-up stops at a stair (level 3), the plank at a
chair seat (2), the side plank at a counter (2) and the glute bridge at its standing step (1).

#### Gym, Away, and 1 or 5 days

- **The gym starters are the home starters.** Machines start at level 3 and the barbell lifts
  and dumbbell presses at 4 (the catalogue's levels), so for anyone placed lower they would be too
  much on day one. Each exercise becomes its gym version (the table above) once the walk-through
  places the person on a home step at or above the gym exercise's level. Above that, a machine
  climbs by weight (ADR-0072). The walk-through writes each person's gym version when it makes their
  plan (Decided 5), since plans are per person now, so no new rule is needed when a session runs. The barbell
  back squat stays in the picker, as it needs coaching more than a machine does. The Romanian
  deadlift is the hip hinge's gym version from level 4, where the person can already do a
  single-leg hinge (Decided 2). The catalogue has no seated cable row: the chest-supported row ("machine or dumbbells") is
  the nearest, and the lat pulldown takes the row in one session a week.
- **Away is the same list.** Every bottom step needs no kit, and away already stops each exercise
  at its last step with no kit (ADR-0086). A hotel room has a door frame.
- **1 day a week: no starter of its own.** Two days is the WHO minimum for strength, and one
  session a week gives about three quarters of the strength gain of two (Pelland 2026: +12.7% vs
  +17.3%). Someone who can only manage one day could run the 2-day starter once a week, A one week
  and B the next. That gives each main muscle about half the 2-day's sets (2-6, mostly amber),
  which the map would show.
- **5 days: no starter either.** The 4-day already works every main muscle on two days. With the
  weekly sets equal, more days add little growth (Pelland 2026; Iversen 2021: "weekly training
  volume is more important than training frequency"), and a new person needs the rest days. A
  fifth day is better spent on the cardio the WHO also asks for (150 minutes a week; walking
  counts). The 7-day cycle stays for people training at levels 4-6, like Liam.

#### Where these are a judgment call

- **The 2-day is at the low end.** Quads, lats, upper back, side delts and calves get 6 sets,
  inside Part A's 5-7 for two short sessions but under the 7-10 for two 40-minute ones. More sets
  would push the sessions past 40 minutes, so the 40-minute version would have to cut every third
  set.
- **The rear delts are amber on the 2-day** (3 sets from the row). A band pull-apart would fix it
  but needs a band at its bottom step, so it is left to the picker.
- **The triceps only get push-ups** (0.5 a set). The armchair press-up stops at level 3 and dips
  start at 4, so neither works as a one-ladder exercise for everyone.
- **The curl stops at a 2-4 kg bag without a kettlebell.** It's a small exercise and the first to
  go when trimmed. With no kit, the picker's door-frame curl (levels 3-5) climbs further.
- **Two exercises start at level 2:** the split squat and the door-frame row (and the tibialis
  raise in the 4-day). For someone at level 1 the row is barely a pull, but a split squat holding
  a chair may be too much (question 3).
- **Balance is in every session and is kept until near the end.** It works no muscle on the map
  and isn't a small exercise, so the trim treats it as a big movement. That suits an older person
  (WHO: balance 3 days a week from 65); for a fit 30-year-old it costs about 3 minutes.
- **Calf raise and balance** turn one-legged partway up their ladders, but they are counted as both
  legs together (not "a side"), as their bottom steps are. Logging each side would need a change
  per step.
- **No neck work, HIIT, jumps or heavy loading**, as before. The 65-and-over balance and
  sit-to-stand "snack" is still the walk-through's suggestion, not part of these lists.
- **The easy start (B6) sits on top:** for the first two weeks, one or two sets of three or four of
  these exercises, with 5-10 minutes of walking.

**What the seed needs to accept these:** an exercise with a catalogue `range` can't also be used
by a session, so `range` comes off the squat, hip hinge and balance, and each session item sets
its own. `start` is 0 for every exercise in a starter. Built (8 Nov 2026) as `[[starters]]` in
`plan.toml`, with a new person on the 3-day until setup picks; someone on a starter starts every
exercise at its bottom step, leaving `start` as the owner's cycle has it (ADR-0073, addendum).

#### Decided (8 Nov 2026)

Liam's answer to these questions was "All OK to proceed", so each one is decided as proposed.

1. **One set of starters for every level.** These replace builder N's 3- and 4-day starters for
   new people, since N's start at level 4 (pistols, jump squats, swings). The 7-day cycle stays
   as Liam's own plan.
2. **The hip hinge gets three steps at its top:** single leg with a hand on the counter (4),
   single leg with no hands (5), single leg holding a bag (5), a bodyweight single-leg Romanian
   deadlift. Steps at the end of a ladder need no migration; they need questions, cues and
   figures. The gym swap can then reach the barbell Romanian deadlift at level 4, which gives the
   lower back work at the gym again. Built 8 Nov 2026: the steps, their questions, cues and figures.
3. **Someone placed at level 1 by the everyday questions gets no split squat** (0 sets, as the
   trim does). The squat still works the legs.
4. **Each ladder's questions start at the level the age and exercise questions suggest**, walking
   up or down from there (B5 step 4). The bottom step stays the default if they skip.
5. **The gym swaps are written into each person's gym version** when the walk-through makes
   their plan, from where they are placed.
6. **No 1-day or 5-day starter.**
7. **4 days as upper and lower**, as builder N has it.
8. **Balance is kept late in the trim for everyone.**
9. **Rest days are places in the queue** (builder N's last point): A, rest, B, rest, C, rest,
   rest for the 3-day; A, rest, rest, B, rest, rest, rest for the 2-day; Lower 1, Upper 1, rest,
   Lower 2, Upper 2, rest, rest for the 4-day. It keeps ADR-0006: the queue offers its next
   place every day, a missed session still moves everything back a day, and the map counts days
   correctly. The days tapped in the walk-through set where the queue starts. The other option,
   offering sessions only on the tapped days, was turned down: it adds a second rule beside the
   queue, and a missed Monday would wait until Wednesday. Built as rest days after a session
   (ADR-0091).
10. **The lower back at the gym** (Liam, 9 Nov 2026: "add a back exercise at the gym"): the 45°
    back extension takes the glute bridge's place in 2-day B, 3-day B and Lower 2, from the step
    where the bridge would become the hip thrust. The lower back is 4 at the gym, with no added
    minutes; a swap rather than an added exercise, as three more sets would add 6-7 minutes.

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
