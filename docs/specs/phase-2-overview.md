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
| D1 | Dashboard visual design and screen list | Decided 2026-10-09 for the guided session; the other screens stand as mocked (`dashboard-design.md`) |
| D2 | ~~Monthly strength/hypertrophy blocks (#26)~~ Decided: optional 4-week blocks | `phase-2-decisions.md` |
| D3 | ~~Where progress photos are stored~~ Decided: on the Pi for now | `phase-2-decisions.md` |
| D4 | ~~Retest cadence~~ Decided: start of each block, else every 4 weeks | `phase-2-decisions.md` |
| D5 | ~~Which habits to track~~ Decided: morning light, protein, wind-down; sleep and steps from the band later | `phase-2-decisions.md` |
| D6 | ~~Weekly review day and time~~ Decided: Sunday 19:00, adjustable | `phase-2-decisions.md` |

## Proposed steps (draft)

Order: data first, then Telegram features, then the dashboard that shows them.

Issues (milestone "Phase 2 - Overview"): 2-0 #72 (done), 2-A #74 (#94-#96, built), 2-B #142
(measurements, built) and #143 (photos, built), 2-C #73 and #124 (done), 2-D #90 and #91 (done),
2-E #26 (done). Web: 2-F sign-in #115 (done; share links still open), 2-H #117 and #118 (done),
summaries #116 (done). Plan changes keep history: #107 (done).

### 2-0 Multi-user-ready schema (#72, done)
- ADR-0026: a `users` table with Liam as the only row, `user_id` on every per-person table,
  every query scoped by it and a test that enforces it. Behaviour unchanged (still one user).

### 2-A Baseline tests and retests (#74; built in #94-#96)
- Test definitions in `plan.toml`, and test days with their conditions and results (ADR-0037).
- The web app walks through day 1 and day 2 tests one test at a time, with the same
  confirm-before-save rule as workout logs (ADR-0007). Not in Telegram (ADR-0035, ADR-0037).
- Retests at the start of each block, or every 4 weeks without blocks (D4); results comparable
  test by test. A due test day stands in front of the queue, which waits (ADR-0038); the
  baseline is started by hand from the tests page.
- Each result is shown against the first baseline and the previous test, with a note when the
  conditions differ (#96).

### 2-B Body measurements and progress photos
- Measurements (bodyweight, waist, chest, upper arm, thigh, resting heart rate) entered in the
  web app at `/body` (#142, web-first per ADR-0035), with the change since the first and the
  last; never logged.
- Photos stored on the Pi (D3); never in logs, never in share views (ADR-0012), excluded from
  any public endpoint (ADR-0019); the nightly backup and the desktop pull include them. Built
  (#143): rows in the database, cleaned of metadata on the server, taken or chosen on `/body`
  (ADR-0039).

### 2-C Weekly review message (#73, done)
- Built: `/review` shows the week so far, and the review is sent every Sunday at 19:00 (local,
  DST-safe, skipped while paused), adjustable in `/settings` (D6).
- Contents: sessions done vs planned, hard sets per muscle group vs Galpin's 10-20,
  zone 2 and moderate cardio minutes vs the 180-200 zone 2 target (#124), personal bests,
  exercises ready to progress, habits.

### 2-D Habit check-offs (#90, #91, done)
- Per D5: three one-tap check-offs in one evening message; the week's tally in the weekly
  review (5 of 7), no streaks to break. The protein target is a setting.
- Built: the buttons sit under the evening nudge when one is due, otherwise they come on
  their own; `/habits` shows them any time; taps count for up to two days; `/settings` turns
  them off. The protein number is still to come as a setting.

### 2-E Strength and hypertrophy blocks (#26, done)
- Optional 4-week blocks per ADR-0028, built: "Train in blocks" in `/settings`, the block
  calendar (paused days don't count), the strength prescription (one step harder, 4-8 reps,
  3-4 sets) with its own history, Move up held for hypertrophy blocks, and the morning message
  naming the block and prompting the warm-up before strength sessions.

### 2-F Dashboard login and share links
- Sign-in, built (#115): passkeys, started and recovered with a one-time Telegram link
  (ADR-0036, superseding ADR-0012's Telegram login). Every route declares public or
  owner-only; a test enforces it. Cloudflare rate limit on `/api/auth/*` (a manual step).
- Still to do: read-only share links as ADR-0012 (hashed expiring tokens, `/share` and
  `/unshare`), never showing measurements or photos.

### 2-G Dashboard screens
- Built so far without the mockup: `/progress` (each exercise's step, last session, best and a
  trend, as the bot's `/progress`), `/tests`, `/body`, and a nav between the signed-in pages.
- Built to the agreed design (D1): Today, Plan with live position and ladder progress,
  Progress charts, Baseline vs retests, Measurements, Share view. Works as a Telegram Mini App.

### 2-H Guided session mode (#117 API, #118 screens; needs 2-F #115)
- One set at a time in work order, with + and − from the target, a rest timer, a pair switch,
  and resume; as decided in `dashboard-design.md` (Guided session).

## Definition of done (phase)
- All steps merged; release 1.0.0; in daily use for at least two weeks.
- Restore drill repeated with photos and measurements in the backup.
