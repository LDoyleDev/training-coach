# Training plan

The plan the coach runs, and why. Data: `backend/src/training_coach/seed/plan.toml`.
Decision record: ADR-0017.

## Basis

Huberman's Foundational Fitness Protocol (Huberman Lab ep. 94, "Fitness Toolkit"), built with
Andy Galpin, adapted to home equipment (8 kg kettlebell, pull-up bar, chairs for dips, floor):

| Huberman (ep. 94) | This plan |
| --- | --- |
| Sun: long endurance, zone 2, 60-75 min | Long zone 2, 45-75 min (30 min minimum) |
| Mon: legs (quads, hamstrings, calves; tibialis first) | Legs |
| Tue: heat/cold, recovery | Recovery + posture (+ core, grip, neck side work; optional sauna/cold) |
| Wed: torso push/pull + neck | Torso + neck |
| Thu: moderate cardio, ~35 min at 75-80% | Cardio + core: 30-40 min, then a core + hips block |
| Fri: high intensity, 20-30 s all-out / 10 s rest x 8-12 | High intensity, 20 s / 10 s x 8-12 |
| Sat: arms, calves, neck | Arms + legs (calves, a second leg block) |

Since 23 Oct 2026 ("Coverage + core", ADR-0064) the plan departs from Huberman's days in four
ways, so every main muscle gets 10 or more hard sets on two or more days
(`program-builder-research.md`, Coverage): the light core, grip and neck side work moved from
Arms to Recovery; Arms carries split squats, hamstring curls and an overhead triceps extension,
so legs are trained twice a week and the triceps' long head is reached; and a few sets were
added where muscles fell short (calves, curls, push-ups, dips, lateral raises). And the
trunk and hips the lifts miss get their own work (`program-builder-research.md`, Core and hips):
Recovery adds reverse Nordics and side plank hip dips, and the moderate cardio day, now "Cardio
+ core", ends with ab rollouts, Copenhagen planks, back extensions and side plank hip dips.

The queue starts at Legs (freshest at the start of the cycle) and keeps this order; missed days
shift everything back (ADR-0006).

## Training rules (Galpin, from the Huberman Lab guest series)

- **Volume:** 10-20 hard sets per muscle group per week, on two or more days. The table below
  counts secondary movers as half a set or less (ADR-0064).
- **Effort:** stop 1-2 reps short of failure on most sets.
- **Reps:** hypertrophy 6-30 reps (mostly 8-15). Bodyweight progression comes from harder
  ladder variations, which keeps sets inside the range.
- **Order within a session:** power (jumps, swings) -> strength -> hypertrophy -> small muscles.
- **Pairs (ADR-0031):** resistance sessions are done in pairs of exercises that don't compete for
  the same muscles, alternating set by set, so one rests while the other works. The order
  above applies to each pair's first exercise; the second can be a small muscle (calves,
  tibialis, core, neck) that fills the bigger lift's rest, so small-muscle work can come
  early. Sessions list every set in the order it's done.
- **Session length:** ~10 min warm-up + 50-60 min of work.
- **Neck:** controlled flexion, extension and side bending, plus chin tucks; no neck bridges.
  About 10-15 reps, twice a week (Torso and Recovery).
- **Posture / upper back:** rear-delt reverse fly with the chest supported, prone Y-T-W, back
  extensions, chin tucks, dead hangs.

## Weekly hard sets per muscle group

Counted from `plan.toml`, fractionally (ADR-0064): a set counts 1 for each muscle its exercise
lists as a prime mover, 0.5 for a synergist and 0.25 for a small part (pull-ups: 1 for lats, 0.5
for biceps and upper back, 0.25 for rear delts and forearms). The weights, and why, are in
`program-builder-research.md` (Weights by exercise). CI checks that this table matches
`plan.toml`. All ten main muscles are in their target band on two or more days; the body map
on the Plan tab shows the same numbers. Abs, obliques, lower back, hip flexors and adductors
are measured against their own, lower bands (low evidence; Core and hips).

| Group | Sets | From |
| --- | --- | --- |
| Glutes | 15.5 | split squat (Legs + Arms), pistol, jump squat, swing, RDL, back extension (Recovery + Cardio) |
| Chest | 11 | dip, push-up, diamond |
| Quads | 12.5 | split squat (Legs + Arms), pistol, jump squat, reverse Nordic (the rectus femoris) |
| Hamstrings | 10.5 | hamstring curl (Legs + Arms), RDL, swing |
| Lats | 10 | pull-up, row, chin-up |
| Upper back | 10 | row, Y-T-W, reverse fly, pull-up, chin-up |
| Biceps | 10 | curl (Arms + Torso), pull-up, row, chin-up |
| Triceps | 10 | overhead extension (the long head), dip, push-up, pike, diamond |
| Side delts | 8.5 | lateral raise (Arms + Torso), pike |
| Front delts | 8.5 | pike, dip, push-up, diamond |
| Calves | 8 | twice a week (Legs + Arms) |
| Rear delts | 7.25 | reverse fly, row, Y-T-W, pull-up, chin-up |
| Abs | 7 | ab rollout, hanging raise, side plank hip dip |
| Neck | 7 | flexion, extension, side bend (Torso + Recovery days) |
| Adductors | 6.5 | Copenhagen plank, split squat, pistol |
| Forearms | 6.5 | dead hang, curl, hanging raise, pull-up, chin-up, swing |
| Obliques | 5.75 | side plank hip dip (Recovery + Cardio), Copenhagen plank, ab rollout |
| Lower back | 5.5 | back extension (Recovery + Cardio), swing, RDL |
| Hip flexors | 3 | hanging raises |
| Tibialis | 3 | tibialis raises |

Conditioning covers Galpin's endurance adaptations: long zone 2 (long-duration endurance),
moderate cardio (muscular endurance / threshold), high intensity (anaerobic and VO2 max).

**Zone 2 target: 180-200 minutes a week**, built up over time (Huberman's Foundational Fitness
Protocol). The long zone 2 session gives 45-75 of them; walks, rides and easy runs on other days
make up the rest (they log as zone 2 through its aliases). The weekly review shows the week's
zone 2 and moderate cardio minutes against it (#124); the target is `[targets] zone2_minutes`
in `plan.toml`.

## Known limits

- Upper traps get nothing: no study shows shrugs grow them (Core and hips).
- The core bands (abs 6-12, obliques 4-10, lower back 4-10, hip flexors 3-8, adductors 4-10)
  are estimates: no growth trial sets a dose for these muscles. On the general 10-20 band they
  would show light green.
- Skipping the optional Recovery day now also skips the hanging raises, dead hangs, neck side
  work, reverse Nordics and half the oblique work.
- Once the split squats and pistols hold a kettlebell, Legs passes the 8-set spine-loading
  limit (12 sets at the top steps: swing, both squats, RDL); the map warns then.
- Most muscles sit at the bottom of their band: a skipped set drops lats, upper back, biceps
  and triceps below 10.
- Legs outgrow an 8 kg kettlebell first. A 16 kg (then 24 kg) bell is the most useful upgrade;
  the ladders already include "heavier kettlebell" steps.
- Huberman alternates monthly between strength blocks (4-8 reps, 3-4 sets, 2-4 min rest) and
  hypertrophy blocks (8-15 reps, 2-3 sets, ~90 s rest). The app runs hypertrophy ranges for
  now; block periodisation is a planned feature.

## Sources

- [Huberman Lab ep. 94 "Fitness Toolkit" notes (Podcast Notes)](https://podcastnotes.org/huberman-lab/episode-94-fitness-toolkit-protocols-tools-to-optimize-physical-health-huberman-lab/)
- [Neck exercises (Huberman Lab AI, from episode content)](https://ai.hubermanlab.com/s/9bd7a81e-c7fe-11ee-bd9b-b7ccfbd13a66)
- [Galpin's guide to strength and hypertrophy (Huberman Lab readable notes)](https://www.hubermanlab.readablepods.com/blog/build-strength-grow-muscles/)
- [Galpin guest series: training for fitness and longevity (Podcast Notes)](https://podcastnotes.org/huberman-lab/guest-series-dr-andy-galpin-optimize-your-training-program-for-fitness-longevity-huberman-lab/)
- [Huberman's workout routine: neck, calves, tibialis (WellnessPulse)](https://wellnesspulse.com/fitness/huberman-workout-routine/)
- [Foundational Fitness Protocol (Huberman Lab newsletter, Nov 2022)](https://www.hubermanlab.com/newsletter/foundational-fitness-protocol)
