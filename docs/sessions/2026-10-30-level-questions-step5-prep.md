# Session log: 30 Oct 2026 (1.10.0): level questions, a 5-minute warm-up, step 5 prepared

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-30-vest-load-progress-weights.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.10.0 (released with this log's PR open) | #489 a "Can you do ...?" question on every later ladder step (`[exercises.questions]` in `plan.toml`), shown on Plan's ladder panel as "Ready for this if yes"; #485 the warm-up is 5 minutes (`WARM_UP_MINUTES`); #480 the chart's side labels fit ("120 min" showed as "20 min"); #486 the two-person canary over the plan, with six strict xfails that flip when step 5 lands; #487 `docs/specs/plans-per-person.md`: everything that reads the plan, and a draft 5b migration; #476 and #488 Gradle dependency verification for the band reader (a dispatch-only workflow writes `verification-metadata.xml`; two runs matched; `android.yml` fails on a wrong checksum); the 1.9.0 log. No migrations. |

## Decisions and where they live

- **Liam's plan of 30 Oct:** before step 5, build the level questions, draft the 3- and 4-day
  starters, prepare step 5, fit the chart's labels; warm-up 5 minutes (program-builder.md J.4,
  ADR-0065 addendum); a third item in a pair waits for step 6 (J.2); Gradle verification
  through CI (android/CLAUDE.md has the regenerate steps).
- **Level questions:** ADR-0075 addendum: a question sits on the step a "yes" opens and uses the
  bottom of that step's range, in one set with good form. For Liam to confirm.
- **Step 5:** `docs/specs/plans-per-person.md` (inventory, draft 5b migration, open points).

## State at the wrap

- **Pi.** 1.9.0 live since 15:13 on 30 Oct; 1.10.0 deploys about 15 minutes after its release.
- **Starters:** proposed in program-builder.md section M (#484, open, waiting for Liam).

## Open items and next steps

1. **Waiting on Liam:** read and accept or change the starters (#484); whether test days keep
   a 10-minute warm-up (the bot's warm-up line now says 5 on test days too); confirm the level
   questions' two choices (ADR-0075 addendum); plug the phone in for the reader's adb plan.
2. **Step 5, from about 4 Nov on Liam's go:** answer the open points in
   `plans-per-person.md` first (ship the `plan.toml` import with step 5 or keep an owner-only
   seed until step 6; refuse the migration when members exist, or copy plans for them; starters
   only in `plan.toml`); then the restore drill on the Pi (needs Liam's OK), a plan-critic
   review, the migration with a backup and a dry run on a copy, released on its own.
3. **Found while preparing:** a 3-day starter needs rest days the queue passes (ADR-0006 offers
   the next session every day); the catalogue has no stand-ins for less kit (band or inverted
   row, curl); `version_on` and `day_clash._date` skip the per-person scoping; `GET /api/plan`
   and `/api/plan/coverage` read `plan.toml`, not the database; erasing one person reruns the
   whole seed.
