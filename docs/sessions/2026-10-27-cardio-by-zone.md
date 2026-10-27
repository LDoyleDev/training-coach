# Session log: 27 Oct 2026 (1.5.0): cardio by zone, targets from the plan

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-27-load-reader-figures.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.5.0 (released with this log) | #390 all cardio counted over the last 7 days and split by zone (easy, zones 1-5; a log without heart rate in the zone the person picked), targets from the plan's sessions plus a per-person extra, a counted band workout counting its full minutes, and a one-off data fix for walks counted the old way; #391 the Cardio page's total, zone rows and what's left, Home's short form, and "Extra cardio a week" on the Plan page; this log |

## Decisions and where they live

- **Cardio by zone and targets** (Liam, 26-27 Oct; ADR-0079): targets default to what the
  cycle's sessions plan (today zone 2 45-75, all cardio 75-115) plus "extra cardio a week"
  (none, 30, 60, 120 or a number), which adds to both; over target is never a warning. The
  180-200 zone 2 figure (Huberman, Nov 2022) is now the long-term idea reached with extra time
  (`docs/specs/training-plan.md`). A typed log is split by heart rate only over its own timed
  sets; otherwise it counts in the zone picked.
- **Stored data changes in this release** (Liam's OK, 27 Oct): migration `c3e8a1f5d9b2` sets a
  counted band workout's cardio set to the import's full minutes where it still holds the old
  zone 2 figure. On the Pi that is Monday's walk, 35 -> 66. The auto-deploy backs up first.

## State at the wrap

- **Pi.** v1.4.0 live since 09:05 on 27 Oct (the load migration ran; the gym catalogue seeded).
  1.5.0 deploys within about 15 minutes of its release PR merging.
- **Backups.** The 04:34 off-site run on 27 Oct uploaded and kept 35 days with no 501 retry:
  the `--s3-no-head` fix (1.3.0) works.

## Open items and next steps

1. **Check after deploy:** Monday's walk reads 66 min; the Cardio page shows 109 of 75-115,
   zone 2 35 of 45-75.
2. **Next builds:** builder step 9 (home and gym versions, the Today switch); figures for the 23
   gym exercises before step 9 offers them.
3. **Small follow-ups:** as in the previous log (Home and the review's "top for your kit", the
   bot's ladder-end text, the `test_pi_read.py` timing test under parallel load, the
   "_platform" exercise source).
4. **Liam to check** (carried over): the backup key in the password manager; Cloudflare
   "Always Use HTTPS"; the desktop's `User` account; BitLocker status.
