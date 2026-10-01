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
| Tue: heat/cold, recovery | Recovery + posture (optional sauna/cold) |
| Wed: torso push/pull + neck | Torso + neck |
| Thu: moderate cardio, ~35 min at 75-80% | Moderate cardio, 30-40 min |
| Fri: high intensity, 20-30 s all-out / 10 s rest x 8-12 | High intensity, 20 s / 10 s x 8-12 |
| Sat: arms, calves, neck | Arms, calves + neck (+ core, grip) |

The queue starts at Legs (freshest at the start of the cycle) and keeps this order; missed days
shift everything back (ADR-0006).

## Training rules (Galpin, from the Huberman Lab guest series)

- **Volume:** 10-20 hard sets per muscle group per week; each muscle trained directly once and
  indirectly once per week.
- **Effort:** stop 1-2 reps short of failure on most sets.
- **Reps:** hypertrophy 6-30 reps (mostly 8-15). Bodyweight progression comes from harder
  ladder variations, which keeps sets inside the range.
- **Order within a session:** power (jumps, swings) -> strength -> hypertrophy -> small muscles.
- **Session length:** ~10 min warm-up + 50-60 min of work.
- **Neck:** controlled flexion, extension and side bending, plus chin tucks; no neck bridges.
  About 10-15 reps, twice a week.
- **Posture / upper back:** rear-delt reverse fly with the chest supported, prone Y-T-W, back
  extensions, chin tucks, dead hangs.

## Weekly hard sets per muscle group

Direct sets only, counted from `plan.toml` (CI checks the big groups stay within 10-20).

| Group | Sets | From |
| --- | --- | --- |
| Glutes | 18 | jump squat, swing, split squat, pistol, RDL, back extension |
| Biceps | 13 | pull-up, row, chin-up, curl |
| Upper back | 12 | pull-up, row, reverse fly, Y-T-W |
| Triceps | 12 | dip, push-up, pike, diamond |
| Quads | 10 | jump squat, split squat, pistol |
| Lats | 10 | pull-up, row, chin-up |
| Hamstrings | 9 | swing, RDL, hamstring curl |
| Chest | 9 | dip, push-up, diamond |
| Neck | 9 | flexion, extension, side bend, chin tuck (Torso + Arms + Recovery days) |
| Lower back | 8 | swing, RDL, back extension |
| Calves | 6 | twice a week (Legs + Arms) |
| Shoulders (front/side/rear) | 6 / 4 / 5 | pike + presses / lateral raise / reverse fly + Y-T-W |
| Core, grip, tibialis | 3-5 each | hanging raises, dead hang, tibialis raises |

Conditioning covers Galpin's endurance adaptations: long zone 2 (long-duration endurance),
moderate cardio (muscular endurance / threshold), high intensity (anaerobic and VO2 max).

## Known limits

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
