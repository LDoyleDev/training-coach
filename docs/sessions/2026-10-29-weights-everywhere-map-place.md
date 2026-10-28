# Session log: 29 Oct 2026 (1.8.0): weights everywhere, own weight steps, the map's place

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-28-figure-fixes.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.8.0 (released with this log) | #434 an AI's `propose_log` takes a weight per set on loaded steps, checked as a typed weight; #439 Today's day card, the AI's read tools and "Copy for my AI" show each set's weight; #446 new bests and the weekly review name the weight; #436 each person's own weight steps ("Weight steps" on Account; migration `e2c6a9f1b3d7`, three nullable columns on `settings`); #445 at home the next weight is the next dumbbell owned; #433 the body map's Home \| Gym view on Plan; #437 the reverse pec deck's levers pass beside the head, the Nordic curl drawn as big as the reverse Nordic; #443 a savepoint on SQLite opens its transaction first (ADR-0081, Proposed); #447 `/healthz` gives only its status through Cloudflare; #441 the rest-count test's race (test only); #431 the reader's adb plan (docs); this log |

## Decisions and where they live

- **Builder steps 8 and 9 are done** (Liam, 28 Oct: "keep on working until all of those pieces
  of work are complete"): `docs/specs/program-builder.md` steps 8 and 9; ADR-0072 Built
  (proposals, summaries, own increments, owned weights); ADR-0071 Built (the body map's place);
  ADR-0069 addendum. The choices ADR-0072 didn't settle (steps on Account only, 0.25-20 kg in
  quarters, only dumbbells count as owned weights, − and + step through them at home) are in its
  Built sections, for Liam to confirm or change.
- **SQLite savepoints:** ADR-0081, **Proposed**, for Liam to accept or swap for the full
  SQLAlchemy recipe or `BEGIN IMMEDIATE`.
- **`/healthz`:** `docs/runbooks/deploy.md` and the threat model's new row.
- **Reader closing at screen-off:** nothing in the reader closes it; the adb plan is in
  `docs/runbooks/band-import.md`.

## State at the wrap

- **Pi.** v1.7.1 live since 14:13 on 28 Oct; 1.8.0 deploys about 15 minutes after its release,
  with one migration (`e2c6a9f1b3d7`).
- **Reader** 0.0.7 approved by Liam on 28 Oct.
- **Not visible yet:** the next weight owned at home applies only to loaded steps in a home
  version, and the plan has none (kettlebells are ladder steps, locked by kit already). It
  shows once plan editing (step 6) can put one there.

## Open items and next steps

1. **Waiting on Liam:** accept ADR-0081 (or pick an alternative); confirm ADR-0072's new
   choices; plug the phone in for the reader's adb plan; the backup key in the password
   manager; Cloudflare "Always Use HTTPS" (still off on 28 Oct: plain http serves the app). The
   desktop's `User` account and BitLocker (the TPM check failed on 28 Oct: Secure Boot is off
   and the boot path through GRUB changes) are deferred by Liam.
2. **Next builder work:** step 5, plans per person, after a week of home/gym use (ADR-0073);
   then 6, 7 and 10.
3. **Follow-ups:** Plan's exercise lists still show the home versions in the gym view; the
   "last session" and "best" on Progress and `/progress` don't show weights; the threat model
   has no row for `equipment` (ADR-0071, the security reviewer on #445); whether Cloudflare's
   "Remove visitor IP headers" is off (it would show `/healthz`'s version again and break the
   per-address limits; from memory, unchecked); Gradle dependency verification; a Dependabot
   ignore rule for Node majors; the unclosed SQLite connections Python 3.14 warns about.
