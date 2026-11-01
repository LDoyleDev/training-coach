# Session log: 30 Oct 2026 (1.9.0): the vest takes load, weights on Progress and Plan

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-29-weights-everywhere-map-place.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.9.0 (released with this log's PR open) | #459 a vest or backpack takes load (`backpack` in `[exercises.loads]`, "Vest or backpack" weight step on Account, migration `a4d8f2c6e9b1`), dips gain "Dip bars, vest or backpack"; #465 pull-up and chin-up end in one "Vest or backpack" step (migration `b7e1c3d5f9a2` deletes their unused 10 and 15 kg steps, refusing if anything uses them); #458 Progress and `/progress` name the weights of the last session and the best; #463 Plan's ladder cards too; #455 Plan's exercise lists follow the Home \| Gym view; #467 the weight strip's labels fit; #461 the migration engine and the tests close their SQLite connections (Python 3.14 warned); #454 Dependabot's Node and Python major rules match `library/` images; #451 the threat model's equipment row; #449 ADR-0081 accepted, ADR-0072's built choices confirmed |

## Decisions and where they live

- **Liam's answers of 29 Oct:** ADR-0081 accepted as built; ADR-0072's built choices confirmed
  (weight steps on Account only; at home − and + step through the weights owned), with one
  change: the vest and backpack count as weight owned at home. ADR-0072 "Confirmed (29 Oct
  2026)" and "Built (vest and backpack, 29 Oct 2026)".
- **Pull-up and chin-up:** one loaded step from 5 kg (Liam's choice over keeping 5/10/15 kg);
  dips keep their chair steps and gain a loaded step after dip bars. The data change was Liam's
  option 1, a one-off migration; a read-only check on the Pi (29 Oct) found nothing at the four
  steps (no sets, levels, sessions in progress or events), and a dry run on a copy of the live
  database deleted exactly those 4 rows with no foreign-key problems. No 5 kg sets needed a
  weight filled in.
- **Which weight a Progress best names:** the session's heaviest set's, of the first session to
  reach it, as the weekly review does: ADR-0072 "Built (Progress shows weights)".

## State at the wrap

- **Pi.** 1.9.0 deploys with two migrations (`a4d8f2c6e9b1`, `b7e1c3d5f9a2`) after the deploy's
  own backup.
- **Now visible:** the dips' loaded step is the first in a home version, so the weights owned
  at home show on the set screen for it.
- **Cloudflare:** plain http already gets a 301 to https from Cloudflare, with HSTS on the
  https reply (checked 29 Oct); the "Always Use HTTPS is off" item was wrong. "Remove visitor
  IP headers" is off: the public `/healthz` gives only its status, which needs
  `CF-Connecting-IP`.
- **Backup key:** saved in Liam's password manager (29 Oct).

## Open items and next steps

1. **Waiting on Liam:** plug the phone in for the reader's adb plan
   (`docs/runbooks/band-import.md`). The desktop's `User` account and BitLocker stay deferred.
2. **Next builder work:** step 5, plans per person, after a week of home/gym use (ADR-0073);
   then 6, 7 and 10.
3. **Follow-ups:** Gradle dependency verification for the reader (no JDK on the desktop; a
   one-off CI job could write `verification-metadata.xml`, if Liam agrees); the chart's own
   side labels ("60 min") are about as wide as their gap, `chart.fitSize` could cover them;
   `gh issue create` was refused once by the permission system for a helper (#455 has no
   issue).
