# ADR-0053: A daily check before training: sleep, soreness, energy

- Status: Accepted
- Date: 2026-10-11
- Deciders: Liam

## Context

The product spec's phase-3 item "Readiness check (sleep, soreness) that eases the session" asks
how the day looks before training. It is a different thing from the readiness questions
(ADR-0046): those are a health screen asked about every 6 months; this is asked every day and
changes only today's advice. It has to be quick (one tap per question) on both surfaces, the web
app as it opens and the morning message on Telegram, and never stand in the way of training.

## Decision

- **Three questions, three answers each, best first:** sleep (good, OK, poorly), soreness (not
  sore, a bit sore, very sore), energy (high, normal, low). Wording, the rule and the advice
  texts live in `domain/daily_check.py`, so the web and the bot say the same thing.
- **The rule** (pure logic, `advise`):
  - two or more worst answers (poor sleep, very sore, low energy): **Take a rest day**;
  - one worst answer, or two or more middle ones: **Go lighter today**;
  - otherwise: **Go as planned**.
- **It advises; it never changes the plan by itself.** On "Take a rest day" a one-tap
  Rest today is offered, using the existing rest (ADR-0022, ADR-0052); on "Go lighter" the
  person continues and eases off themselves.
- **Stored per person per day** (`daily_checks`): the local day in `settings.tz`, the three
  answers (check constraints on each), `answered_at` (UTC); unique per person and day, so
  answering again that day replaces the answers (`PUT /api/daily-check` is idempotent).
- **Health data:** never logged, never on the `/share` picture (ADR-0050), in the export
  (`daily_checks` in `data.json`) and erased with everything else (the `user_id` cascade,
  ADR-0044).
- **Kept for a year:** rows older than 365 days are deleted whenever a new answer is saved,
  long enough to see a pattern, short enough not to keep a health diary forever.
- **When it's asked:** on the web, when the app opens and today isn't answered, after the
  6-monthly readiness questions if those are due; "Not now" skips it for that load; signed out,
  an error or no answer within 4 seconds lets the page through. In Telegram, the morning
  message carries the three questions as rows of buttons until answered (`bot/daily_check.py`:
  each button carries the answers so far and the day, so nothing is kept between taps and an
  old message can't answer today); the third tap saves and replies with the advice, with
  Rest today when it says rest. Today shows the day's answers and advice as one line.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Three one-tap questions, a fixed counting rule (chosen) | Fast; the same answer on web and Telegram; easy to test and explain | Coarse: doesn't scale the session itself |
| A 1-10 score per question and a weighted score | Finer | Slower to answer; weights are guesswork |
| Ease the session automatically (fewer sets, lower step) | No thinking needed | Changes the plan without asking; the plan is edited deliberately (product spec) |
| Read sleep from a wearable | No questions | Needs health-data imports that don't exist yet (platform proposal) |

## Consequences

- The privacy notice lists daily checks as health data under consent (draft in `docs/legal/`).
- A later "go lighter" that adjusts targets, or sleep read from a band, would change this ADR.
- Tests: `tests/domain/test_daily_check.py` (all 27 answers), `tests/api/test_daily_check.py`,
  `frontend/src/readiness/DailyCheckGate.test.tsx`, `tests/bot/test_daily_check.py`.
