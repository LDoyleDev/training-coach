# ADR-0064: Exercises name fixed muscles with weights; sets count fractionally

- Status: Accepted
- Date: 2026-10-22
- Deciders: Liam

## Context

The program builder (`docs/specs/program-builder.md`, step 2) needs facts about every exercise:
which muscles it trains and how much, its movement, the strain it shares with other exercises,
and the kit each ladder step needs. Until now an exercise had `muscle_groups`, 24 free tags
mixing muscles ("quads"), vague groups ("shoulders", "core", "grip") and qualities ("posture",
"power"). Every planned or logged set counted once for every tag, which overstates secondary
muscles: a pull-up counted as a full set for the biceps. A meta-regression found that counting
a synergist as half a set fitted muscle growth best (Pelland 2026), and growth studies measured
some pairings directly (`program-builder-research.md`). Liam chose "go with the science" and
fractional counting (program-builder.md, Decided 2).

## Decision

- **A fixed list of 21 muscles** (`domain/muscles.py`). Each exercise in `plan.toml` lists its
  muscles with a weight: **1** prime mover, **0.5** synergist, **0.25** a small part. A
  stabiliser isn't listed and counts 0. The weights are the research file's table, Weights by
  exercise; most are estimates and the file says which.
- **Qualities** (posture, power, mobility, conditioning) are kept apart from muscles and never
  count as sets. Chin tucks and the cardio and mobility exercises have qualities only.
- **Muscle parts** that compounds barely grow (the triceps long head, the rectus femoris), a
  **movement pattern**, the **stress** shared with other exercises (spine, grip) and the **kit
  each ladder step needs** (`kettlebell:16`, `pull-up bar`, `backpack`) are catalogue facts too.
  Household things (chairs, a bed, a wall, water bottles, a stair) need nothing.
- **Only loaded squats load the spine.** A squat or lunge carries spine stress only on steps
  that need a weight (kettlebell, dumbbells, backpack); bodyweight and jump squats don't.
  Hinges, swings, back extensions, carries and bent-over rows always do.
- **Counting is fractional everywhere volume is counted:** the Plan tab's weekly sets, the
  weekly review (web and Telegram) and the stretching routine's "most-worked muscles".
- **The facts live in the bundled plan**, read through `bundled_plan()` like an exercise's
  summary and the stretches. The `exercises.muscle_groups` column is dropped: nothing logged
  refers to an exercise's muscles, and one home avoids a copy that can drift. The seed refuses
  an unknown muscle, pattern, stress or kit, a weight other than 1, 0.5 or 0.25, needs for a
  step that isn't in the ladder, and a part whose muscle the exercise doesn't train.
- **"Heavier kettlebell" steps need a 16 kg kettlebell** until step 4 of the plan replaces
  them with concrete steps.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Fixed muscles with weights, in the bundled plan (chosen) | Matches the growth evidence; one home; reviewable in `plan.toml`; no new tables | Volume numbers drop for the same plan; stretches had to move to the fixed list |
| Keep free tags, count each fully | No change | Overstates secondary muscles; "shoulders", "core" and "grip" can't be coloured on a body map |
| Fixed muscles, primary or secondary only (1 or 0.5) | Simpler | Can't say a squat doesn't train the hamstrings (0) or that pulldowns barely reach the rear delts (0.25) |
| Store the weights in the database | Queryable in SQL | A second copy of catalogue facts the seed must keep in step; per-person plans (step 5) share the catalogue anyway |

## Consequences

- The Plan tab, the weekly review and Telegram show fractional sets (7.5, 6.25). The current
  plan's numbers drop: only glutes, lats and upper back reach 10 (training-plan.md, Weekly hard
  sets). The release notes should say so; the plan itself is unchanged.
- The stretches name fixed muscles: "shoulders" and "grip" went, "core" became abs. The
  adductors, now counted from split squats and pistols, have no stretch yet.
- The body map (step 3) and the warnings read these facts; the bands per muscle come with it.
- The gym exercises (the 29 in program-builder.md, Decided 5) join the catalogue at step 8,
  with load; the overhead kettlebell triceps extension joins when a session uses it.
- Downgrading brings `muscle_groups` back empty; the older version's seed refills it on start.
