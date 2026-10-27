# Session log: 26-27 Oct 2026 (1.4.0): load, the reader's sleep and workouts, figures

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them. The previous
log is `2026-10-26-band-reader-rep-tops.md`.

## Shipped

| Release | PRs |
| --- | --- |
| 1.4.0 (released with this log) | Load, builder step 8: #379 sets record their weight; #380 typed and spoken logs take a weight ("rows 10 10 9 at 16"); #381 double progression suggests the next weight; #382 the set screen's weight counter with − and +; #383 a chart period per weight with a kg strip; #385 23 gym exercises. The reader's coach side: #374 sleep, exercise and deletions; #375 background sync; #376 Account and the bot name the reader, runbook rewritten. Figures: #377 Copenhagen plank front and side, calf-raise close-up; #378 figures by ladder step (vest, dip bars, suitcase, hammer curl); #389 plank front in perspective, dips with feet off the floor. Repo: #384 the backend pinned to Python 3.12; #388 the backend tests in parallel (CI's backend job ~30 min to under 3); #387 a flaky test fixed; this log |
| Reader `android-v0.0.5`, `android-v0.0.6` | #374, #375 |

## Decisions and where they live

- **Load:** ADR-0072's Built section: load belongs to a step; a session's weight is its heaviest
  set; the next weight is suggested only when every set of the last session was at that weight
  and at the top of the range (no suggestion after a pyramid); only a tap on Use takes it; a
  right side weighed differently from its left is a problem, never dropped.
- **Band reader:** ADR-0070 accepted (Liam, 26 Oct, after 0.0.4's first clean sync of 3
  reads, without waiting for the 3-day trial). Reading limits and the expired-token risk:
  `docs/specs/android-reader.md`.
- **Figures by step:** ADR-0063's addendum.
- **Tests in parallel:** `backend/CLAUDE.md`, Tests.

## State at the wrap

- **Pi.** v1.3.0 live since 17:39 on 26 Oct; 1.4.0 deploys within about 15 minutes of its
  release PR merging (ADR-0030).
- **Band data.** Reader 0.0.6 on Liam's phone with sleep, exercise and background reading
  allowed (Android 12's Health Connect supports it). The coach has its first night of sleep
  with stages and its first band workout (a 66-min walk), all from Mi Fitness. Liam turned
  off Google Fit's write access in Health Connect, which had been writing copies.
- **Desktop.** uv upgraded to 0.13.5 (it is pip-installed: `python -m pip install --user
  --upgrade uv`).

## Open items and next steps

1. **Cardio by zone (#390, #391, in review):** total cardio split by zone, targets from the
   plan's sessions plus a per-person "extra cardio a week", a counted band workout counting
   its full minutes, and a one-off data fix for Monday's walk (35 -> 66, Liam's OK, 27 Oct);
   ADR-0079. The 180-200 zone 2 target (Huberman, Nov 2022) becomes the long-term idea, not the
   default.
2. **Next builds:** builder step 9 (home and gym versions, the Today switch), which puts the gym
   exercises and the set screen's weight counter in front of Liam; figures for the 23 gym
   exercises before step 9 offers them.
3. **Small follow-ups:** Home and the weekly review list only "ready" exercises, not "top for
   your kit"; the bot's ladder-end text still says to edit `plan.toml`; a timing test in
   `test_pi_read.py` failed once under parallel load; the "_platform" exercise source in
   Health Connect isn't known.
4. **Liam to check** (carried over): the backup key in the password manager; Cloudflare
   "Always Use HTTPS"; the desktop's `User` account; BitLocker status.
5. **Follow-ups:** the reader closing when the screen turns off (debug over adb); Gradle
   dependency verification; `/healthz` shows the version publicly; a Dependabot ignore rule for
   Node majors; the unclosed SQLite connections Python 3.14 warns about.
