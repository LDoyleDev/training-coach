# ADR-0063: Exercise pictures are mannequins we draw from two poses

- Status: Accepted
- Date: 2026-10-21
- Deciders: Liam

## Context

The app describes each exercise in a sentence or two of text. A glance at a picture is quicker:
where you start and where you finish, and for the mobility flow (ADR-0062) each movement's
positions. Liam wants more than line figures but not photos: "mannequin-esque bodies so that it
can be seen", animated from start to finish if that can be done simply, side by side if not.
The product spec ruled out an exercise video library. The app is meant to go public, costs
nothing to run and has to work offline in the gym.

## Decision

We draw our own figures in code: one side-view mannequin, like an artist's wooden figure, with
rounded tapered limbs, ball joints and a faceless head with a small nose for direction. The far
arm and leg are a shade darker, behind the body. Colours are CSS tokens (`--fig-*`), so the
figures follow light and dark.

- **A pose is about a dozen numbers** (`frontend/src/figures/poses.ts`): where the hip is (or,
  for a plank, the balls of the feet), how far the trunk leans, how much the spine rounds or
  arches, the neck, and a target for each hand and foot. A hand can be placed on the body (on
  the hips, behind the head) so it moves with it. The elbows and knees are worked out by
  two-bone inverse kinematics (`body.ts`), so planted hands and feet stay put. An exercise is a
  start pose, an end pose, a tempo (there, hold, back, rest) and its props (mat, chair,
  kettlebell): 300-400 bytes.
- **Drawn as SVG** (`shapes.ts`, `Figure.tsx`): `<Figure slug name />` moves between the two
  poses with easing at the pace of the movement, and its "Start and end" button shows the two
  positions side by side with captions. People who ask for reduced motion start on the two
  positions; off screen it stops redrawing. `<FigureAt slug t label />` draws one still. A slug
  with no figure draws nothing, so screens can ask for one before every exercise has it.
- **A front view, or a close-up, where the side view can't show it** (added 26 Oct 2026,
  Liam): a movement that happens side-on to the body, such as the Copenhagen plank (lying on
  your side), looks face down from the side. Its figure can carry a `front` motion too: the
  mannequin posed in the plane of its chest (`front.ts`), drawn in perspective from in front of
  the chest, past the head, so the body runs away from you towards the feet and looks nothing
  like the side view (`perspective.ts`: a camera, nearer parts bigger and drawn later, the seat
  and a mat in the round, the down side in the far tone). It moves at the same pace, with the
  same captions, and is shown first, with a Front / Side switch under it. A small movement can carry an `inset`: a circle of the
  side view drawn about twice as big where the picture is empty, with a ring round the part it
  shows (the calf raise's heel on the step's edge).
- **Figures are keyed by slug**: plan exercises use their seed slug (`kb-swing`), the flow's
  movements their own.
- **Checked by tests**: limbs keep their length through the whole movement, no joint goes
  through the floor, planted hands and feet stay on their targets.

## Options considered

| Option                                              | Pros                                                                                                                 | Cons                                                                                                                                   |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Our own mannequins from poses (chosen)              | Ours to use anywhere; one consistent style; tiny; offline; light and dark; an exercise is two poses, not new artwork | We have to get each pose right; side view only, so twists and sideways moves need a cue in the text                                    |
| Photos from an open library (e.g. free-exercise-db) | Realistic; many exercises at once                                                                                    | Licence and model consent to check before a public app; no neck, tibialis or flow moves, so mixed styles; hundreds of KB each to cache |
| AI-generated images                                 | Any exercise, any style                                                                                              | Costs money or a key; inconsistent from one picture to the next; licence unclear                                                       |
| Stick figures                                       | Simplest                                                                                                             | Liam asked for bodies you can see                                                                                                      |
| Video links per exercise (the spec's fallback)      | No drawing at all                                                                                                    | Leaves the app; useless offline; no glance at start and end                                                                            |

## Consequences

- Every exercise and movement still needs its two poses drawn and checked; screens show nothing
  until it has them.
- One view (from the side) suits most of the plan. A movement that mainly turns or goes sideways
  shows its turn as an arm or elbow moving towards you and leans on its cue.
- Adding a prop (bench, bar, bands) is a small drawing function in `shapes.ts`.

## Addendum (26 Oct 2026): a figure can change with the ladder step

Figures stay keyed by slug. A few ladder steps change the set-up rather than the load
(`docs/specs/kit-ladder-proposal.md`, "Figures"), so `frontend/src/figures/steps.ts` maps a
slug and a step's name, as `plan.toml` writes it, to what changes over the figure: its props,
or its poses and captions too. `<Figure slug name step />` draws that; any other step, or none,
draws the figure as it is. The set screen passes the step it shows.

- The vest or backpack steps of the pull-up, chin-up and dip: a pack high on the upper back
  (`load`).
- The split squat's suitcase hold: a bell hanging from each hand, the heavier one on the
  front leg's side (`bell: 'sides'`).
- The dip's last step: dip bars (`bars`) in place of the two chairs, with its own poses.
- The dip's feet-off-floor steps: between two chairs, one each side (drawn as one, in front of the
  body: `chair.beside`), knees bent about square behind, feet up, with their own poses. The
  seats are drawn 50 cm high, so at the bottom the knees stay well off the floor.
- The curl's hammer grip: the handle stood upright round the fist (`bell: 'hammer'`). The curl
  had no figure, so this adds one.

Keyed by name, a renamed step would quietly lose its change, so a test checks every name in
`steps.ts` against the ladders in `plan.toml` (Vite may read the seed folder for it). A step that
only changes the motion, such as the overhead extension's 1.5 reps, gets no figure: its cue
says what to do, and the set screen now shows the step's cue under the step's name.

## Addendum (27 Oct 2026): every ladder step checked against its figure

All 164 ladder steps of the 62 exercises in `plan.toml` were checked against their figure. A
step whose set-up, load or movement looks different gets its own drawing in `steps.ts`; one that
changes only the tempo, a pause or the weight of a bell already drawn shows the figure as it is.
`steps.test.tsx` holds the audit: every step of an exercise with a figure must be drawn in
`steps.ts` or listed in `SAME` with the reason, so a new loaded or one-sided step can't ship
without its figure. Steps still to draw sit in its `PENDING` list until they are.

- `bell: 'goblet'`: a kettlebell held by the horns at the chest, the bell under the hands.
- `kneel` (body.ts): a pose pivoting on the knee, so a Nordic curl keeps its knees put.
- `bell: 'one'`: a one-arm swing's bell along the near forearm; `bell: 'toes'`: a bell resting
  on the near forefoot, rising with the toes.

| Exercise | Step | What changes | Figure |
| --- | --- | --- | --- |
| Tibialis raise | Back against wall, heels forward | | the figure |
| | Heels further from wall | feet further out, more weight on the wall | own poses |
| | Single leg | one foot works, the other off the floor | own poses |
| | Holding 8 kg on toes | a bell resting on the toes | bell on the toes |
| Jump squat | Bodyweight, full rest | | the figure |
| | Pause at bottom, then jump | a pause | none |
| | Holding 8 kg | a bell at the chest | goblet hold |
| Kettlebell swing | Two-hand, 8 kg | | the figure |
| | One-arm, 8 kg; One-arm, 16 kg | one hand on the bell, the other free | one-arm bell |
| | Two-hand, 16 kg; Two-hand, 24 kg | a heavier bell | none |
| Bulgarian split squat | Bodyweight, back foot on chair | | the figure |
| | Goblet hold, 8 kg; Goblet hold, 16 kg | a bell at the chest | goblet hold |
| | Goblet hold, 3 s lowering; Goblet hold 16 kg, 3 s lowering | a bell at the chest, the tempo | goblet hold |
| | Suitcase hold, 16 kg + 8 kg | a bell in each hand | bells at the sides |
| Pistol squat | Sit to chair on one leg | sits down to a chair behind, a shorter range | own poses, chair |
| | Lower box | sits down to a low box | own poses, box |
| | Full pistol | | the figure |
| | Holding 8 kg | a bell at the chest | goblet hold |
| Single-leg RDL | 8 kg | | the figure (a bell in the hand) |
| | 8 kg, pause at bottom; 16 kg; 16 kg, pause at bottom | a pause, a heavier bell | none |
| Hamstring curl | Towel slide, both legs | | the figure |
| | Towel slide, single leg | one heel slides, the other leg held up straight | own poses |
| | Nordic curl negatives | kneeling, heels anchored, lowered from the knees, hands catch | own poses |
| | Full Nordic curl | the same, pulled back up by the hamstrings | own poses |
| Single-leg calf raise | Bodyweight on a step | | the figure |
| | Holding 8 kg; 8 kg, 2 s pause at top | a bell in the hand on the working side | own arms, bell |
| Pull-up | Strict pull-up | | the figure |
| | Slow negatives; Pause at top | the tempo, a pause | none |
| | Vest or backpack, 5, 10 and 15 kg | a pack on the upper back | pack |
| Dip (chairs) | Feet on floor | | the figure |
| | Feet off floor; with 5 kg; 10 kg | between two chairs, feet up; a pack | own poses, pack |
| | Dip bars, bodyweight, full range | bars in place of chairs | own poses |
| One-arm kettlebell row | 8 kg | | the figure (a bell in the hand) |
| | 8 kg, 3 s lowering; 16 kg; 16 kg, 3 s lowering; 16 kg, pause at top | the tempo, a heavier bell | none |
| Push-up | Standard | | the figure |
| | Feet elevated | feet on a chair, the body sloping down | to draw |
| | Deficit | hands raised on blocks, the chest below them | to draw |
| | Archer | one arm bends, the other stays straight out wide | to draw |
| Pike push-up | Feet on floor | | the figure |
| | Feet on chair | feet on a chair, more upside down | to draw |
| | Wall handstand push-up negatives | upside down, feet on a wall | to draw |
| Chin-up | Strict | | the figure |
| | 3 s lowering | the tempo | none |
| | Vest or backpack, 5, 10 and 15 kg | a pack on the upper back | pack |
| Diamond push-up | Standard | | the figure |
| | Feet elevated | feet on a chair | to draw |
| Kettlebell curl | 8 kg | | the figure |
| | 8 kg, slow tempo; 8 kg, 3 s lowering, pause at top; 16 kg, slow tempo | the tempo, a heavier bell | none |
| | 16 kg, hammer grip | the handle upright | hammer grip |
| Copenhagen plank | Knee on a chair | | the figure |
| | Knee on a chair, 3 s lowering | the tempo | none |
| | Ankle on a chair; Ankle on a chair, 3 s lowering | top leg straight, the ankle on the seat | to draw |
| Reverse Nordic | Lean back about 30 degrees | | the figure |
| | Lean deeper, 3 s lowering | further back | to draw |
| | To the floor, hands push you back | all the way down, hands to the floor | to draw |
| | To the floor and back, no hands | all the way down and back | to draw |
| 45° back extension (#397) | Bodyweight; Holding a plate | a plate at the chest | the figure; plate |
| The other gym exercises | one step each | | the figure |

No figure yet, so nothing to vary; these steps will need a drawing when their exercise gets one:
goblet squat (none: the bell is always at the chest), reverse lunge (a bell; a step under the
front foot), rear-delt fly (one arm), suitcase carry (a bell in each hand), the three neck
exercises (a hand or a weight on the head), overhead extension (a heavier bell), lateral raise
(one arm, leaning away), hanging raise (straight legs, toes to the bar), dead hang (one hand),
prone Y-T-W (bottles), back extension (on the bed's edge; a bell at the chest), chin tuck
(lying), ab rollout (a wheel; standing), side plank hip dip (straight legs; top leg up; a bell on
the hip). Mobility and the three cardio entries have no single figure.
