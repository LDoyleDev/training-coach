# Session log: 27 Oct 2026 (1.6.0): an end-of-session bell, the top for your kit everywhere

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-27-cardio-by-zone.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.6.0 (released with this log) | #411 a louder, celebratory bell at the end of every session (the guided session's save, HIIT, the mobility flow, stretching, any cardio save), in the person's timer sound; #399 "At the top" on Home and the weekly review, naming the kit that opens the next level; #396 the bot says the top of a ladder in plain words; #395 a flaky timing test made deterministic; this log |
| Reader `android-v0.0.7` | #401 Health Connect's own data is named "Health Connect itself", not "_platform" |

## Decisions and where they live

- **End-of-session bell** (Liam, 27 Oct: "really positive and loud"): ADR-0074's added line;
  a timer's own end sound stays as it was. On a run-then-block cardio day it rings once per
  save.
- **At the top:** ADR-0078; on Home for 7 days after the save that first noted it, in the
  review for that week.

## State at the wrap

- **Pi.** v1.5.0 live since 09:36 on 27 Oct; Monday's walk reads 66 min after the data fix.
- **Worktrees** cleaned on 27 Oct; work not on main saved in `~/training-coach-archive/2026-10-27/`.

## Open items and next steps

1. **Waiting on Liam:** step 9's gym versions of the sessions (#398 -> #402 -> #406 -> #407, the
   table in `docs/specs/program-builder.md` section L), and whether the 23 gym figures (#397,
   #400, #403, #405, #408) merge now with a follow-up pass for the weak ones (front views small,
   side views of flies, the Pallof column, the reverse pec deck, dim props in dark mode).
2. **In progress:** a figure for every ladder step whose set-up differs (goblet-hold split squat,
   single-leg hamstring curl first; an audit of all steps; a test so new steps can't ship without
   one); "Change level" on the set screen, for today or from now on (ADR-0080).
3. **Liam to check** (carried over): the backup key in the password manager; Cloudflare
   "Always Use HTTPS"; the desktop's `User` account; BitLocker status.
4. **Follow-ups:** the reader closing when the screen turns off (debug over adb); Gradle
   dependency verification; `/healthz` shows the version publicly; a Dependabot ignore rule for
   Node majors; the unclosed SQLite connections Python 3.14 warns about; ADR-0025 line 29 still
   quotes the old ladder-end message.
