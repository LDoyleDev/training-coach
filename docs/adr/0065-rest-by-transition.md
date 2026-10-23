# ADR-0065: Rest by transition: a quick switch inside a pair, a rest after it

- Status: Accepted
- Date: 2026-10-23
- Deciders: Liam

## Context

Sessions are done in fixed pairs (ADR-0031) so one exercise rests while the other works. But
the guided session started a 60 s rest after every set, inside a pair too (`REST_SECONDS` in
`services/guided.py`), so the pairs interleaved and saved nothing. The studies say pairs of
opposing or unrelated muscles keep their reps and growth in far less time; same-muscle pairs
lose volume; more than about 90 s of rest adds nothing, and short rest costs most on
multi-joint sets (`docs/specs/program-builder-research.md`, Time efficiency: Zhang 2025,
Weakley 2017, Singer 2024, Senna 2011). Liam chose to rest by transition (program-builder.md J,
decision 1).

## Decision

- **The server decides the rest after each set** (`domain/rest.py`), and the guided session
  sends it with each set (`rest_seconds`, `switch`):
  - inside a pair, the move to the other exercise: **15 s**, shown as "Switch to <exercise>";
  - after a round of a pair: **60 s**, or **90 s** when the two share a prime mover: a muscle
    one exercise counts fully for (weight 1) and the other at least half (pistol squat +
    single-leg RDL, both glutes). The neck is one muscle in the catalogue though its
    directions oppose, so a neck pair doesn't share;
  - a set done on its own (an unpaired exercise, or the longer exercise's extra sets): **90 s**
    for a compound pattern (squat, hinge, lunge, pushes, pulls, carry), **60 s** otherwise;
  - after the last set: none.
- The rest stays adjustable during it (+15 s, Skip rest), and its end still buzzes.
- **The session's time estimate uses the same rests** (`guided._minutes`), so "about N min" on
  Home and the overview match what the session runs.
- `rest_seconds` on the session (60) stays for pages loaded before this change.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Rest by transition, from the catalogue (chosen) | Pairs save time; follows the studies; nothing to maintain per exercise | The rules are fixed; a heavy set can't ask for more than +15 s taps |
| A rest per exercise in `plan.toml` | Full control | Another number to keep for every exercise; easy to drift from the evidence |
| Keep 60 s after every set | Simple | Pairs save nothing (the reason for this change) |

## Consequences

- The current week's estimates drop: Legs 64 to 55 min, Torso 52 to 44, Arms 55 to 47.
  Recovery goes 20 to 22: back extensions are a hinge, so they rest 90 s.
- Later, in the builder's spec: a third, light exercise in a pair's rest (tri-sets), pairs on
  the Recovery day, and drop-set or rest-pause set types for isolation exercises.
- Amends ADR-0031's timing; the pairs themselves are unchanged.
