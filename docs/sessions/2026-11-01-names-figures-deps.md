# Session log: 1 Nov 2026 (1.14.0): names that fit, figures for the new steps, dependencies

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-11-01-ladders-down.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.14.0 | #546 knees marks on the new deep steps (split squat holding a chair at full range, back foot on a low step; the Squat's full depth) and names that fit the lower ladders ("Split squat", "Calf raise", "One-arm row", "Curl", "Lateral raise", "Neck flexion/extension/side bend"; slugs kept, old names are aliases); #548 figures for the 17 new steps (`UNDRAWN` is empty); #549 figures for the door-frame row and curl; dependencies #522 (Python minor/patch), #544 (Python image), #468 (Node image), #471 (claude-code-action); #547 the 1.13.0 log. No migrations. |

## Decisions and where they live

- **"Heavier kettlebell" stays named so** until a migration renames it: migration
  `5ebed72122f7` checks that ladder by name on downgrade (ADR-0083 addendum); its cue says
  16 kg.
- **Figures that don't read well yet** are listed in #548 and #549 (scapular pulls, the pull-up
  with feet on a chair, the counter and chair-seat push-ups, the chair in front of the split
  squat, the flat calf raise, the door-frame row's lean, the door-frame curl's arm).

## Open items and next steps

1. **Dependabot #470 (Gradle):** asked to rebase onto main so `gradle-verification.yml` can run
   on it (the branch predates the workflow); then the checksum steps in `android/CLAUDE.md`.
2. **Waiting on Liam:** the Cloudflare check for #514 and #515; glute bridge and plank levels on
   Plan; the away versions (#539) and knees marks (#541, #546) to look over; a clinician and a
   lawyer before anyone else uses the app.
3. **After builder step 5:** setup with placement and the on-device safety questions, the
   starting starters, the easy start.
