# ADR-0071: Each person lists their home kit; a gym has everything; steps lock by kit

- Status: Proposed
- Date: 2026-10-25
- Deciders: Liam

## Context

The plan assumes one kit: an 8 kg kettlebell, a pull-up bar, chairs and the floor. Weight lives
only in step names, and the top of seven ladders is "Heavier kettlebell" or "Weighted backpack".
The catalogue already records the kit each ladder step needs (`needs`, ADR-0064), but the app
doesn't know what anyone owns, so it can't tell a step you can do from one you can't.

On 25 Oct 2026 Liam ordered a 16 kg kettlebell, already has elastic bands, uses stools as a
bench, is considering a weighted vest and dumbbells, and will train at a gym some days. The
program builder (`docs/specs/program-builder.md`, options C and E, Decided 4, 8 and 10) settled
the shape on 21 Oct; this records it.

## Decision

- **Home kit is per person** (an `equipment` table, `Owned`): one row per item, with a weight
  where it has one. Items: kettlebells (each weight), dumbbells (fixed pairs, or adjustable with
  a range), a weighted vest or backpack (up to N kg), resistance bands (light, medium, heavy), a
  pull-up bar, dip bars or two chairs, a bench, rings, a step or box, a mat. Account gets "My
  equipment": tap to add, and the app says what it unlocks ("16 kg kettlebell: 4 new steps").
- **A bench can be stools.** The item is "something stable to lie on": a flat bench, stools or
  a bed. Exercises that need an incline or a padded bench (the incline press, the 45° back
  extension) need the gym. Flat-bench exercises say "check it's stable before loading it".
- **A gym has everything in the catalogue** for now (Decided 8). No "away" place: travelling is
  Home with whatever is there (Decided 10).
- **Steps lock by kit.** A step whose `needs` you don't have shows locked ("needs a 16 kg
  kettlebell"). Move up goes to the next step you can do; at the last one, Progress says "top
  for your kit" and names what unlocks the next, instead of "top of the ladder". "Heavier
  kettlebell" steps become concrete steps with their weights, written in the seed with name,
  needs and cue, never generated (option C).
- **Places:** a person trains at home, a gym, or both (a setting). A session in the cycle keeps
  one place in the queue (ADR-0006) and can hold a home and a gym version
  (`template_items.place`). Today shows a Home | Gym switch when both exist, defaulting to the
  last place used (Decided 4); the choice is stored on the workout (`workouts.place`) and can
  change until the first set is kept. History follows the exercise (ADR-0034), wherever it was
  done.
- **Built before plans per person.** Kit and place are per person from the start. The gym
  versions of the sessions live in the shared plan, as the default 7-day cycle's gym version,
  until each person owns their plan (ADR-0073). So the gym arrives without the migration that
  can't be undone (Liam, 25 Oct 2026).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Per-person kit, gym has everything, concrete steps (chosen) | Honest locks; reviewable steps with cues; no gym inventory to keep | Each heavier kit needs steps written in the seed |
| Generate steps from the weights owned | No seed typing | Steps without cues, and no order a person can read |
| A kit list per gym | Matches a small gym | A second inventory to keep; nobody asked for it yet |
| Gym versions only after plans per person (the spec's order) | One migration path | Liam waits for the gym behind the riskiest step |

## Consequences

- Builder step 4: the `equipment` table, "My equipment" on Account, locked steps, and Move up
  and Progress respecting the kit. Then step 9: `template_items.place`, `workouts.place`, the
  switch on Today, and gym versions of the seven sessions in `plan.toml` from the 29-exercise
  gym catalogue (Decided 5).
- The body map and weekly sets count the version used most recently, with a switch to see "all
  home" or "all gym" (option E).
- Every new catalogue exercise needs its figure (ADR-0063) before it's offered.
- The cross-user test covers `equipment` (ADR-0029).
