# ADR-0017: The training plan follows Huberman's Foundational Fitness Protocol

- Status: Accepted
- Date: 2026-10-01
- Deciders: Liam

## Context

The first plan was a home-equipment adaptation with two leg days and no recovery day, no neck
work and little posture work. Liam asked for the plan to fully reflect Huberman's protocol,
including neck and posture training, while staying efficient.

## Decision

Adopt the seven-day structure of Huberman Lab ep. 94 (built with Andy Galpin): legs, recovery
(+ posture), torso + neck, moderate cardio, high intensity, arms + calves + neck, long zone 2.
Programming follows Galpin: 10-20 hard sets per big muscle group per week, power before
strength before hypertrophy, sessions of about 60 min. Details and sources:
`docs/specs/training-plan.md`.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Huberman's structure (chosen) | Matches the protocol; neck twice a week; a recovery day; every muscle direct + indirect | Legs trained directly once a week |
| Keep two leg days | More leg volume | No recovery day; drifts from the protocol |

## Consequences

- The previous plan was never deployed to the Pi, so no data migration is needed. A local dev
  database seeded with the old plan will fail the seed (removed sessions); delete it and run
  `make migrate seed`.
- CI checks that neck and posture work appear at least twice a week, that every major group is
  trained, that quads, glutes, lats, upper back, biceps and triceps get 10-20 sets a week, and
  that the weekly-sets table in `docs/specs/training-plan.md` matches `plan.toml`. Hamstrings
  and chest (9) and calves (6) are below 10 by choice, to keep sessions under an hour.
- Monthly strength/hypertrophy blocks are a follow-up feature.
