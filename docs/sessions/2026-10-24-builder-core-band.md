# Session log: 21 to 24 Oct 2026 (v0.34.0 to v0.37.1)

One file per release wrap: what shipped, the decisions and where they live, open items. Facts
stay in their own homes (ADRs, specs, runbooks); this log only points at them.

## Shipped

| Release | PRs |
| --- | --- |
| v0.34.0 (23 Oct) | #283 refused band syncs and HC Webhook record ids (ADR-0055); #284 exercise catalogue with weighted muscles (ADR-0064); #285 read-only body map; #288 rest by transition (ADR-0065); #289 plan update: every main muscle on target; #287 dependency fix; docs #276, #286 |
| v0.35.0 (23 Oct) | #293 core and hips block, Cardio + core day; #294 a cardio day's block stays open after its run (ADR-0066); #292 read-only Pi helper; docs #290 |
| v0.36.0 (23 Oct) | #295 cardio effort, distance, heart rate, start (ADR-0067); #298 Today shows each day's log, with ‹ › to earlier days (ADR-0068); #299, #300 nav order, Tests inside Body, a body map per session on Plan (ADR-0069); #301 habits on earlier days; docs #296 |
| v0.37.0 (24 Oct, released with this log) | #305 your own AI turns a run screenshot into a cardio proposal with distance, heart rate and start; you pick the effort on the card (ADR-0067, `docs/specs/cardio-photo-prefill.md` option A); #304 virtualenv 21.14.13 (GHSA-cx6f-vjhg-g3cc) and #306 filelock 4.2.4 (CVE-2026-112940), both dev tools only; docs #302, this log |
| v0.37.1 (24 Oct) | #308: the Pi's image build survives a slow download (longer timeout, retries, a wheel cache). v0.37.0 never deployed: its build timed out fetching one package over Wi-Fi, so the Pi rolled back to v0.36.0 (`docs/runbooks/deploy.md`) |

## Decisions and where they live

- **Program builder.**
  - The plan and its stages: `docs/specs/program-builder.md`.
  - The evidence: `docs/specs/program-builder-research.md`. It covers:
    - set weights of 1 / 0.5 / 0.25 / 0;
    - the colour bands and the two-days rule;
    - overload warnings;
    - only loaded squats count as spine-loading;
    - time efficiency;
    - the core and hips bands, which rest on low evidence.
- **The plan itself.** `backend/src/training_coach/seed/plan.toml` and `docs/specs/training-plan.md`. The "Coverage + core" version runs from 23 Oct.
- **Rest.** A 15 s switch inside a pair and 60 or 90 s after it, by pattern: ADR-0065.
- **Cardio log fields and session load (minutes × effort).** ADR-0067. Photo or screenshot prefill is planned in `docs/specs/cardio-photo-prefill.md`.
- **Read-only access to the live Pi.** A forced-command SSH key: `docs/runbooks/pi-read-access.md`. Writes still go through `vybe-pi`, with an OK each time.
- **Band import.**
  - Diagnosis and fixes: `docs/runbooks/band-import.md`.
  - Direction: `docs/specs/platform-and-health-data-proposal.md`, section 4, "What we learned".

## State at the wrap

- **Pi.** v0.36.0 has been live since 23 Oct 21:16 UTC and is healthy. v0.37.1 (which includes v0.37.0) has been live since 24 Oct 05:07 UTC and is healthy. To check a deploy, look for "auto-deploy: deployed vX" in `tc-read deploy`. The version that `tc-read status` shows is the Pi's checkout, not the running app. The cardio-details migration `b7e2c4d9a1f3` ran; the plan seed was unchanged.
- **Band data.** None since 2026-10-19 19:00 UTC, and only steps have ever arrived.
  - **Cause:** Health Connect's read quota. HC Webhook 1.9.22 reports "Rate limited request quota has been exceeded" even for Steps alone.
  - **Fix in progress on the phone:**
    1. Leave the app alone for 24 hours.
    2. Sync Now with Past 1 day.
    3. Then two scheduled syncs a day, with Steps on Daily.
  - **Also:** Fit no longer writes to Health Connect, and Mi Fitness comes first in the data priority.
- **23 Oct workout.** Cardio + core is logged as workout 23: a 43 min run plus the core block.
  - A rollback-based "dry run" wrote it for real, because the save commits inside the service.
  - The day's `session_progress` row was left without its `saved_workout_id`. It was linked to workout 23 on 24 Oct, after a dry run on a copy of the backup.
  - Backups: `training_coach-manual-20261023T154959Z.db` (before the log), `training_coach-manual-20261023T223125Z.db` (before the link).
- **Read-only helper.** `~/bin/tc-read` on the Pi now matches `scripts/pi-read.sh` on main (24 Oct). The old copy is `~/bin/tc-read.bak-20261024`. Its SQL allowlist has no `LIKE`; use `instr`.

## Open items and next steps

1. **Phone:** retry the band sync. If it still fails, plan our own Android reader (proposal section 4).
2. **Photo prefill, next step:** option B, reading the text on the phone (`docs/specs/cardio-photo-prefill.md`). This is for when there's no connected AI.
3. **Connect the coach to the Claude.ai exercise chat:** `docs/runbooks/connect-my-ai.md`.
4. **Builder stages left:** equipment and places, editing, the picker, gym weights. Plus tri-sets, Recovery pairs and drop sets (decision J).
5. **Coverage gaps:**
   - upper traps 0;
   - rear delts light green;
   - Legs goes over the spine cap once split squats and pistols are loaded.
6. **Figures:** for the exercises that still have none.
7. **Local worktrees:** twelve merged, clean worktrees under `training-coach-worktrees/` are waiting to be removed. `dayview` holds 26 uncommitted files from before that work was split into #298 and #301. Keep it until it has been checked.
