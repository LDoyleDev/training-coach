# Session log: 25 Oct 2026 (1.0.0): the restore drill, phase 2 done, and the builder's next steps

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-25-reader-diagnostics.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.0.0 (released with this log) | #338 the off-site job pings its own monitor and reports any failure; #340 plan version "Rear delts + carries" from 26 Oct (band face pulls, suitcase carries, one dead-hang set fewer); #341 the trend chart shows each ladder step as its own labelled period; #336 a flaky test fixed; docs #339 (ADR-0071 to 0073), this log |

## Decisions and where they live

- **Phase 2 is done** and the app is 1.0.0 (`phase-2-overview.md`, ADR-0005).
- **Program builder:** kit per person, a gym has everything, steps lock by kit (ADR-0071); load
  and double progression, where the app suggests the next weight and the person decides
  (ADR-0072); sessions per person, built last (ADR-0073). New order: steps 4, 8, 9, then 5
  (`program-builder.md`, Suggested order).
- **Progress chart:** each weight or ladder step is a labelled period with a broken line; one
  axis only, no dual axis and no converted one-rep-max line for now (ADR-0072).
- **Upper traps and rear delts:** Liam chose face pulls and suitcase carries; builder decision
  K.4 is revisited in `program-builder.md` and the numbers are in `training-plan.md`.

## The restore drill (25 Oct)

Run on the Pi beside the live app, which was never touched (`backup-restore.md`, Rehearsal):
the restore, the migration, every count and a test photo's bytes matched, and the off-site copy
decrypted with the backup key. It also found that the off-site job had **never run**: the
timer, the Telegram alert unit and the `coach-data` group weren't installed and the R2 bucket
was empty. Liam installed them the same day; the first copy uploaded (its first attempt got a
501 from R2 and the retry worked), and a Healthchecks.io check now watches the job. The old
6 Oct database copy was deleted and the data folder locked to its owner and group.

## State at the wrap

- **Pi.** v0.38.1 live; 1.0.0 deploys after its release PR merges, which waits for the first
  nightly off-site run at 04:30 on 26 Oct to succeed on its own.
- **Backups.** Nightly on the Pi and off-site in R2; no desktop copy (not set up, by choice).
- **Band data.** None since 2026-10-19; reader 0.0.3's one fresh-quota sync is due on 26 Oct.

## Open items and next steps

1. **26 Oct:** check the 04:30 off-site run and the bucket, then release 1.0.0; Liam's band sync
   on reader 0.0.3 decides between the Health Connect reader and Gadgetbridge (ADR-0070).
2. **Next build:** body measurements protocol and a tape-based estimate (Liam's brief of 25 Oct,
   plan first, ADR-0074); then builder step 4, equipment on Account (ADR-0071).
3. **Liam to check** (carried over): the backup key in the password manager; Cloudflare
   "Always Use HTTPS"; the desktop's `User` account; BitLocker status.
4. **Follow-ups:** Gradle dependency verification; `/healthz` shows the version publicly; a
   Dependabot ignore rule for Node majors; figures for the new exercises (ADR-0063).
