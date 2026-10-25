# Session log: 25 Oct 2026 (1.1.0): the set screen, a boxing bell, guided stretching and levels

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-25-restore-drill-builder.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.1.0 (released with this log) | #345 the set screen puts the counter and Confirm first, then the explanation, the movement and the muscles; the screen stays on; the rest counts its last 3 s and ends in the timer sound; Check and save shows each set's time, marking slow sets and long rests; #346 figures for pull-up, chin-up, dip, row, pike and diamond; #347 a boxing-ring bell is everyone's timer sound, chosen in Settings; #348 guided stretching: an overview, 15 s to get into each stretch, a countdown and a bell at every change, and Skip past the end counts as stopping early; #350 Move up, Not yet and any level by hand on the Plan page ("Ready to move up" opens it); #353 Torso curls get a second set; #354 stretching falls back to the bell; #357 a flaky test fixed; this log |

## Decisions and where they live

- **Timer sound:** the boxing bell is the default for everyone and every guided timer; chime
  rows moved to it, and the other sounds stay in Settings (ADR-0074).
- **Levels:** the person moves up, says not yet, or picks any level by hand; the app only
  suggests (ADR-0075).
- **Stretching timing:** 15 s into position, 30 s holds, 5 s to let go, the routine fitted to
  the minutes chosen; a run that reaches the end logs itself, a stop asks (ADR-0032, addendum).
- **Set order:** pairs start so no exercise or main muscle comes twice running (ADR-0031,
  addendum; shipped in 1.0.0 as #344).
- **Plan:** Torso pair 5 is 3 lateral raises and 2 curls; biceps 11 sets a week. It joins the
  plan version "Rear delts + carries" from 26 Oct (`training-plan.md`).
- **Body measurements** go out in 1.2.0, not this release (Liam, 25 Oct): the protocol, the
  tape estimate and the re-measure warning (ADR-0076, PRs #349 and #351, which Liam merges).

## State at the wrap

- **Pi.** v1.0.0 has been live since 18:17 on 25 Oct; 1.1.0 deploys within about 15 minutes of
  its release PR merging (ADR-0030).
- **Backups.** Nightly on the Pi and off-site in R2; the first scheduled off-site run is 04:30
  on 26 Oct.
- **Band data.** None since 2026-10-19; reader 0.0.3's sync is due on 26 Oct.

## Open items and next steps

1. **26 Oct:** check the 04:30 off-site run, its Healthchecks ping and the bucket (the first
   upload's 501 from R2 is a watch item); Liam's band sync on reader 0.0.3 decides between the
   Health Connect reader and Gadgetbridge (ADR-0070).
2. **1.2.0:** body measurements, #349 then #351 (Liam merges both).
3. **Building now:** builder step 4, kit on the backend (ADR-0071), with a proposal of concrete
   kettlebell and vest steps for Liam to approve before the ladders change; leg figures, batch
   2 (ADR-0063). Then "My equipment" on Account, then load (step 8, ADR-0072).
4. **Liam to check** (carried over): the backup key in the password manager; Cloudflare
   "Always Use HTTPS"; the desktop's `User` account; BitLocker status.
5. **Follow-ups:** the reader closing when the screen turns off (debug over adb); Gradle
   dependency verification; `/healthz` shows the version publicly; a Dependabot ignore rule for
   Node majors.
