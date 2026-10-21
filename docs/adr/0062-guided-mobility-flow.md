# ADR-0062: Guide the mobility flow one movement at a time

- Status: Accepted
- Date: 2026-10-21
- Deciders: Liam

## Context

The Recovery day's "Mobility flow (hip flexors, thoracic spine, hamstrings)" was one item with
a sentence of description and a 10-minute counter to confirm. Nothing said which movements to
do, how long each takes or how to do them, and there was no timer. Liam used it and it wasn't
clear what should happen. He asked for a standard flow, researched for what it is meant to
achieve, guided by the app with a vibration and a sound he can choose at each change.

## Decision

**The flow.** Eight movements, 600 s in all, standing to kneeling to all fours to lying (three
position changes). The four whole-body moves take 60 s; the four one-sided moves take 45 s a
side.

| # | Movement | Time | For |
| --- | --- | --- | --- |
| 1 | Standing Y-reach | 60 s | Upper back and shoulders, warming up |
| 2 | Hip hinge (bodyweight good morning) | 60 s | Hamstrings |
| 3 | Half-kneeling hip-flexor stretch, tailbone tucked | 45 s a side | Front of the hips |
| 4 | Kneeling lunge with rotation | 45 s a side | Hips and upper-back rotation |
| 5 | Cat-cow | 60 s | The whole spine |
| 6 | All-fours upper-back rotation | 45 s a side | Upper-back rotation |
| 7 | Lying hamstring floss | 45 s a side | Hamstrings and the sciatic nerve |
| 8 | Glute bridge | 60 s | Hip extension, using the new range |

Each has a start and end position (for its picture), one or two cues, breathing, pacing and an
easier option. The content lives in `seed/plan.toml` under `[mobility]`, validated strictly
(unique slugs, whole minutes, logged as an exercise counted in minutes) and read from the
bundled plan like the stretches (ADR-0032): nothing logged refers to a movement. The movement
slugs also name their pictures. One safety line is shown with it: "If something hurts, use the
easier option or skip it. See a physio if pain persists." It is framed as moving often and
feeling looser, not as fixing posture.

**Why these.** Controlled dynamic stretching improves range of motion without the short-term
strength loss of static holds of 60 s or more (Behm 2016; Opplert and Babault 2018), so the
flow is mostly slow reps with short end-range holds and suits a recovery day or a warm-up. Each
area gets about 60 s or more in total, in line with ACSM's guidance per muscle group. The hip
flexor stretch tucks the tailbone first, which beat the usual version in a 2024 crossover
trial (Gonzalez-de-la-Flor). Hamstring sliders ("flossing") gave small gains over static
stretching in two 2025 meta-analyses, both rating the evidence weak. The thoracic drills are
widely used by physiotherapists but have little outcome data. The bridge comes last so the new
hip range is used under muscle control. Posture and pain are only loosely linked (Swain 2020),
hence the framing.

**Who should change what.** Knee pain kneeling: pad the knee or stand in a split stance (3,
4). Wrist pain: fists or forearms, or the side-lying open book (4-6). Sciatica or disc
symptoms: skip or shrink 7. Osteoporosis: no end-range rounding or forced twists. Pregnancy
after the first trimester: replace the moves on the back (7, 8). These are notes for the
easier options, not screens.

**Timing.** One screen per movement with a large countdown, "3 of 8", the side for one-sided
moves, the cues and the picture.
- A one-sided move switches sides halfway, with a "switch sides" sound and vibration; the
  switch comes out of the second side's time.
- The last 5 s show "Next: ..." over the end of the movement; there is no separate transition
  time. The last 3 s count in with three short sounds.
- At zero a "next movement" sound and vibration play and the next movement starts by itself.
- Pause stops the clock; Skip and Back move a whole movement. The screen is kept on where the
  browser allows it.
- The person chooses the sound (chime, beep, wood block, bell or none); vibration plays where
  the device has it. Sounds are synthesised in the browser, so there are no audio files.

**Logging.** The flow is logged as the one set of the `mobility` exercise, in the minutes
actually spent moving (paused and skipped time left out), with the set's `started_at` and
`done_at` as ADR-0061 records them.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A fixed, researched eight-move flow, timed with auto-advance (chosen) | Clear what to do; learnable; works hands-free on the floor | One flow for everyone; a change is a plan edit |
| A different flow each time from the stretch catalogue | Variety | Nothing to learn; mixes static holds into a recovery flow |
| Long static holds (30-60 s each) | Simple | Less suited to a flow; static holds of 60 s+ blunt strength for a while |
| Keep the single 10-minute item | No work | Not clear what to do, which is the problem |
| Tap Next between movements | No surprises | Hands off the floor every minute; breaks the flow |

## Consequences

- The guided session shows a flow player for the mobility item; the bot
  still shows the summary.
- The sound is a per-person setting (`settings.sound`, chime to start), chosen in Settings,
  where tapping one plays it.
- The player shows each movement's mannequin moving from its start to its end, keyed by slug
  (ADR-0063).
- Changing the flow is a plan edit with a review, like any other plan change.
- Sources: Behm et al. 2016; Opplert and Babault 2018 (PubMed 29063454); ACSM (Garber et al.
  2011); Gonzalez-de-la-Flor et al. 2024 (BMC Musculoskeletal Disorders); Winters et al. 2004;
  Nunez de Arenas-Arroyo et al. 2025 and Bertacchini et al. 2025 (neurodynamics);
  Swain et al. 2020 (PubMed 31451200); ACOG Committee Opinion 804.
