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
- **Figures are keyed by slug**: plan exercises use their seed slug (`kb-swing`), the flow's
  movements their own.
- **Checked by tests**: limbs keep their length through the whole movement, no joint goes
  through the floor, planted hands and feet stay on their targets.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Our own mannequins from poses (chosen) | Ours to use anywhere; one consistent style; tiny; offline; light and dark; an exercise is two poses, not new artwork | We have to get each pose right; side view only, so twists and sideways moves need a cue in the text |
| Photos from an open library (e.g. free-exercise-db) | Realistic; many exercises at once | Licence and model consent to check before a public app; no neck, tibialis or flow moves, so mixed styles; hundreds of KB each to cache |
| AI-generated images | Any exercise, any style | Costs money or a key; inconsistent from one picture to the next; licence unclear |
| Stick figures | Simplest | Liam asked for bodies you can see |
| Video links per exercise (the spec's fallback) | No drawing at all | Leaves the app; useless offline; no glance at start and end |

## Consequences

- Every exercise and movement still needs its two poses drawn and checked; screens show nothing
  until it has them.
- One view (from the side) suits most of the plan. A movement that mainly turns or goes sideways
  shows its turn as an arm or elbow moving towards you and leans on its cue.
- Adding a prop (bench, bar, bands) is a small drawing function in `shapes.ts`.
