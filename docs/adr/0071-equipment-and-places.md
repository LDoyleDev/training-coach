# ADR-0071: Each person lists their home kit; a gym has everything; steps lock by kit

- Status: Accepted
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

## Built (backend, 25 Oct 2026)

Decided while building, within this ADR:

- **No kit listed, nothing locks.** Everyone starts with no kit (`settings.kit_saved_at`
  empty) and nothing is filled in for anyone. Until a person saves a kit, every step stays open,
  so the app works as before; Progress says `kit_listed: false` and the page can ask them to add
  their kit. Saving an empty list is a kit: bodyweight only.
- **Matching:** a kettlebell must be the exact weight (`kettlebell:16`); dumbbells match a fixed
  pair of that weight or an adjustable set whose range covers it; a vest or backpack "up to N kg"
  meets any need up to N; other kit is there or not. `dumbbells` and `backpack` needs may name a
  load (`dumbbells:12`, `backpack:10`); bands carry a strength (light, medium, heavy) on the item,
  not yet in needs. A step or box (`box`) joins the kit list; the ab wheel, already a need, is an
  item too. An item can carry a short note ("two stools").
- **Top for your kit:** a person whose next steps are all locked gets `unlock` ("a 16 kg
  kettlebell unlocks Heavier kettlebell") on Progress, on the saved-session feedback and in
  `/progress` on Telegram, in place of "top of the ladder". Move up skips locked steps; a stale
  press at the top for the kit answers `no_next_step`.
- **A locked level by hand is allowed** (the person decides): `POST /api/progress/{slug}/level`
  moves them and answers with a `warning` naming the missing kit.
- The AI summary (and MCP `get_summary`) lists the home kit; the guide is version 3 (#349 took
  2). The export includes `equipment`.
- The concrete steps are proposed, not built: `docs/specs/kit-ladder-proposal.md`.
