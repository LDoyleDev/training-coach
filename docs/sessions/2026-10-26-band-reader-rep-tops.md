# Session log: 26 Oct 2026 (1.3.0): band data flowing, rep ranges top at 18

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-26-body-kit-seven-days.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.3.0 (released with this log) | #369 the off-site backup skips rclone's check that R2 answers with 501; #372 rep ranges top out at 18, and the saved screen and /progress say what kit opens the next level; this log |
| Reader `android-v0.0.4` | #370 an empty page token ends a read (0.0.3 looped to 202 reads), at most 20 reads a sync, a long catch-up goes on at the next sync |

## Decisions and where they live

- **Rep ranges top at 18:** five ranges went from 20 to 18; calf raise, tibialis raise,
  kettlebell swing and band face pull keep theirs as high-rep work (Liam, 26 Oct; ADR-0078).
  Plan version "Rep tops at 18" from 27 Oct. Past sessions are judged against the new top, so
  Move up can show at once.
- **Reader reads:** why 0.0.3 hit the quota and the 20-read limit (`docs/specs/android-reader.md`,
  "Reads less"). 0.0.3's quota error wasn't the minimal pattern ADR-0070's trial asks about.
- **Off-site backup:** why the upload skips rclone's HEAD (`docs/runbooks/backup-restore.md`).

## State at the wrap

- **Pi.** v1.2.0 live since 13:43 on 26 Oct; 1.3.0 deploys within about 15 minutes of its
  release PR merging (ADR-0030).
- **Backups.** The 04:33 off-site run on 26 Oct uploaded and kept 35 days (its journal, read
  over `vybe-pi`); the 501 was rclone's check after the upload, now skipped.
- **Band data.** Reader 0.0.4's first sync (15:56, 26 Oct) stored 2 days of steps and 4,967
  heart-rate samples: the first band data since 19 Oct and the first heart rate ever. Day 1 of
  ADR-0070's 3-day trial.

## Open items and next steps

1. **Band trial:** days 2 and 3 (open Mi Fitness, then Sync now). Both clean: ADR-0070 is
   accepted.
2. **Next builds:** figures for the new kit set-ups (vest or backpack, dip bars, hammer curl,
   suitcase split squat); the Copenhagen plank front view needs a decision; the calf-raise
   figure reads weakly. Then builder steps 8 (load, ADR-0072) and 9 (home or gym; until then a
   gym day shows home-kit locks).
3. **Small follow-ups:** Home and the weekly review list only "ready" exercises, not "top for
   your kit"; the bot's ladder-end text still says to edit `plan.toml`; Dependabot #365-#367.
4. **Liam to check** (carried over): the backup key in the password manager; Cloudflare
   "Always Use HTTPS"; the desktop's `User` account; BitLocker status.
5. **Follow-ups:** the reader closing when the screen turns off (debug over adb); Gradle
   dependency verification; `/healthz` shows the version publicly; a Dependabot ignore rule for
   Node majors.
