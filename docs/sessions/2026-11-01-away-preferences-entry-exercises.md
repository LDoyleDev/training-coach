# Session log: 1 Nov 2026 (1.12.0): away days, preferences, entry exercises, step down, the last set

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-31-short-on-time-levels-stop-signs.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.12.0 (released with this log's PR open) | #518, #519, #520, #523 seventeen entry exercises for people starting low, with figures, and the way-in rule's test; #529 minutes per session on Account, the default length (ADR-0082); #531 the four preferences lock the steps they mark, strength blocks included (ADR-0083); #541 a fifth, "Easy on my knees"; #538, #539 Away, no equipment, a third place on Today with written away versions of the seven sessions and door-frame pulls (ADR-0086); #536 an optional last set of as many good reps as you can, locked for the first 8 weeks (ADR-0084); #530, #532, #533 a step-down suggestion next to Move up and "Ease back in" after 21 days away (ADR-0084); #527 pytest-asyncio's loop scope. Migrations add columns or widen a check only (`e5a1c7d3f9b4`, `e5a7c9d1f3b4`, `a7c2e9f4b1d3`, `f1b3d5a7c9e2`, `1e0c139151a7`); no data changes. |

## Decisions and where they live

- **Liam's answers of 1 Nov:** EU and EEA only, 30 days of travel, the bot's check as a first
  handler, the band import exempt (ADR-0085, "Owner's decisions, 1 Nov 2026"); "Easy on my
  knees" added and a seated neck hold (ADR-0083 addenda); #534 released on its own after a
  dry run; #514 and #515 merge after his Cloudflare check.
- **Away, no equipment** (Liam, 1 Nov: "We need a no-equipment option for any given day also. So
  that when I'm in a hotel room I can still do a session."): ADR-0086, which amends ADR-0071's
  Decided 10. The away versions are in `program-builder.md` section M and #539's body.
- **Built choices** are in the addenda of ADR-0083 (preferences, entry exercises, knees) and
  ADR-0084 (the step-down rule read per set, the last set as its target met).

## State at the wrap

- **Pi.** 1.11.0 live since 31 Oct 21:35; 1.12.0 deploys about 15 minutes after its release.
- **#534** (fifteen ladders down, the Squat back) is next, released alone as 1.13.0. The Pi
  check and the dry run on a fresh backup copy passed on 1 Nov (58 steps kept their ids, every
  reference unchanged, 36 new steps unused, downgrade round trip clean); copies deleted; the
  backup `training_coach-manual-20261101T062611Z.db` stays on the Pi for 35 days.
- **Open PRs:** #514, #515 (wait for the Cloudflare check), #534 (next), #484 (starters).

## Open items and next steps

1. **Waiting on Liam:** IP Geolocation on in Cloudflare and the WAF rule from
   `docs/runbooks/deploy.md`, then #514 and #515; review the away versions (#539's tables:
   fewer hamstring and lat sets away; set your glute bridge and plank levels on Plan); the
   knees marks (the leg press unmarked); a clinician and a lawyer before anyone else uses the
   app; the earlier items (starters #484, test-day warm-up, level questions, phone adb check,
   step 5 from about 4 Nov, the restore drill).
2. **Follow-ups:** figures for #534's new steps and the two door-frame exercises; renaming
   exercises whose names no longer fit their bottom steps (seed only); knees marks on #534's
   new deep steps; Dependabot #470 (Gradle) fails.
3. **After step 5:** setup with placement and the on-device safety questions (ADR-0085, which
   drops `readiness_answers` with Liam's OK), the starting starters, the easy start.
