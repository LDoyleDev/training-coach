# Session log: 28 Oct 2026 (1.7.0): home and gym versions, change level in a session, figures for every set-up

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-27-session-end-bell-kit-tops.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.6.0 (live on the Pi 28 Oct 09:46) | the end-of-session bell and "At the top" (see the previous log) |
| 1.7.0 (released with this log) | Builder step 9: #398 places (where you train, `workouts.place`, `template_items.place`), #402 gym versions of Legs, Torso + neck, Cardio + core and Arms + legs, #406 the day's place in the API (`PUT /api/session/place`, kept progress remembers its place), #407 the Home \| Gym switch on Today, asking before it drops kept sets; #413 "Change level" on the set screen, for today or from now on (ADR-0080); gym figures #397 barbell, #400 dumbbells, #403 machines, #405 cables, #408 front views of the raise and flies; step figures #409 goblet split squat, single-leg and Nordic curls, #410 pistols, jump squats, calves, tibialis, one-arm swings, #414 Copenhagen ankle on a chair, deeper reverse Nordics, #415 push-up variants, pike and wall handstand; #418 a flaky Account test made deterministic; this log |

## Decisions and where they live

- **Gym versions** (Liam, 28 Oct: "land as proposed"): `docs/specs/program-builder.md` section
  L, now marked accepted. A session with no gym version (Recovery, Zone 2) is done and saved as
  at home on a gym day, so the kit locks apply (ADR-0071).
- **Gym figures** (Liam, 28 Oct: merge now, follow up the weak ones): ADR-0063.
- **A figure for every set-up:** ADR-0063's addendum table (164 steps audited, 29 drawn, 17 the
  same figure with a reason); a test fails when a step that needs a variant has none.
- **Change level in a session:** ADR-0080 (for today keeps the person's level; from now on is
  ADR-0075's by-hand change; sets already done keep their step).
- **Migrations, in order:** `b4f9e2a7c1d6` places, `d5a2c7e4b8f1` session levels,
  `7b38a427bb7c` `session_progress.place` (server default home; tests for the constraint and the
  backfill).

## State at the wrap

- **Pi.** v1.6.0 live since 09:46 on 28 Oct; 1.7.0 deploys about 15 minutes after its release.
- **Landing.** Stacked squash PRs now land with the scratchpad `land4.sh`: it stops when a PR
  isn't mergeable instead of moving the next one onto main.

## Open items and next steps

1. **In progress:** the follow-up pass on figures that don't read well yet (#417 front views,
   the machine pec deck and the Pallof cable; #419 props in dark mode; #420 the Nordic's sofa
   and bigger reverse Nordics; the archer push-up to come), for 1.7.1.
2. **Waiting on Liam:** approve reader 0.0.7 in the `android-release` environment; carried over:
   the backup key in the password manager, Cloudflare "Always Use HTTPS", the desktop's `User`
   account, BitLocker status.
3. **Next builder work:** the rest of step 8 (weights in the AI's `propose_log` and the
   summaries, each person's own increments, the next weight owned at home), then step 5 (plans
   per person, the point of no return, after home and gym have settled), 6, 7 and 10.
4. **Follow-ups:** a second flaky frontend test ("a rest counts its last 3 seconds" in
   `SessionPage.test.tsx`); a row created first inside `begin_nested` on SQLite is committed when
   the savepoint closes (reported while fixing #413, unchecked; worked around in `change()`
   only); the reader closing when the screen turns off; Gradle dependency verification;
   `/healthz` shows the version publicly; a Dependabot ignore rule for Node majors; the unclosed
   SQLite connections Python 3.14 warns about; ADR-0025 line 29 still quotes the old ladder-end
   message.
