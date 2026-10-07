# Phase 2: the overview (draft)

Status: **draft, not agreed.** Scope comes from the product spec; the steps and acceptance
criteria below are a proposal to react to. Settle the open decisions with Liam, then turn each
step into an issue in milestone **Phase 2 - Overview** and remove "draft" from this file.
Target version: 1.0.0 (phase 2 complete and in daily use, ADR-0005).

Goal: Liam can see whether the training is working (baselines, retests, measurements, weekly
volume and bests) on his phone, and share a read-only view with others. Phase 1 must be done
and one real week logged first.

## Open decisions (before any issue is opened)

D2, D4 and D6 are decided, with a bigger progressive overload step: `phase-2-decisions.md`.
The web app, multi-user and wearable data direction: `platform-and-health-data-proposal.md`
(ADR-0026).

| # | Decision | Why it matters |
| --- | --- | --- |
| D1 | Dashboard visual design and screen list (`dashboard-design.md` says it is agreed first) | Every web step depends on it |
| D2 | ~~Monthly strength/hypertrophy blocks (#26)~~ Decided: optional 4-week blocks | `phase-2-decisions.md` |
| D3 | Where progress photos are stored, and whether they are encrypted at rest | Most sensitive data in the app; SD card and backups |
| D4 | ~~Retest cadence~~ Decided: start of each block, else every 4 weeks | `phase-2-decisions.md` |
| D5 | Which habits to track (product spec: morning light, sleep, protein) and how (one tap each, or a daily check-in) | Data model and message design |
| D6 | ~~Weekly review day and time~~ Decided: Sunday 19:00, adjustable | `phase-2-decisions.md` |

## Proposed steps (draft)

Order: data first, then Telegram features, then the dashboard that shows them.

Issues open so far (milestone "Phase 2 - Overview"): 2-0 #72, 2-A #74, 2-C #73, 2-E #26. The
others wait on D1, D3 and D5.

### 2-0 Multi-user-ready schema (#72)
- ADR-0026: a `users` table with Liam as the only row, `user_id` on every per-person table,
  every query scoped by it and a test that enforces it. Behaviour unchanged (still one user).

### 2-A Baseline tests and retests (#74)
- Model for test definitions (from the product spec list) and results with date and conditions.
- `/baseline` walks through day 1 and day 2 tests in Telegram, one test at a time, with the
  same confirm-before-save rule as workout logs (ADR-0007).
- Retests at the start of each block, or every 4 weeks without blocks (D4); results comparable
  test by test.

### 2-B Body measurements and progress photos
- Measurements (bodyweight, waist, chest, upper arm, thigh, resting heart rate) logged by text.
- Photos stored per D3; never in logs, never in share views (ADR-0012), excluded from any
  public endpoint (ADR-0019).

### 2-C Weekly review message (#73)
- `/review` (built): the week so far. Next: sent on its own every Sunday at 19:00, adjustable
  in `/settings` (D6).
- Contents: sessions done vs planned, hard sets per muscle group vs Galpin's 10-20,
  personal bests, exercises ready to progress.

### 2-D Habit check-offs
- Per D5. One message or buttons; streaks shown in the weekly review.

### 2-E Strength and hypertrophy blocks (#26)
- Optional 4-week blocks per ADR-0028. Morning message names the current block and prompts the
  warm-up.

### 2-F Dashboard login and share links
- Owner sign-in and read-only share links exactly as ADR-0012 (Telegram HMAC, hashed expiring
  tokens, `/share` and `/unshare`). Every route declares owner-only or share-visible; tests
  enforce it. Cloudflare WAF and rate limit on `/api/auth/*`.

### 2-G Dashboard screens
- Built to the agreed design (D1): Today, Plan with live position and ladder progress,
  Progress charts, Baseline vs retests, Measurements, Share view. Works as a Telegram Mini App.

### 2-H Guided session mode
- One exercise at a time with a rest timer, in Telegram or the Mini App.

## Definition of done (phase)
- All steps merged; release 1.0.0; in daily use for at least two weeks.
- Restore drill repeated with photos and measurements in the backup.
