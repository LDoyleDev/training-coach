# Product spec: Training Coach

Status: living document. Source of truth for *what* the app does; phase specs say *how and when*.

## Goal

Help one person (Liam) follow a Huberman/Galpin-style weekly training plan at home, get
stronger and bigger, and see progress clearly, with the least friction possible from a phone.
Built for Liam first; the direction is an app others can use too, from Telegram, the web and
later a phone app (ADR-0026, `platform-and-health-data-proposal.md`).

Equipment: 8 kg kettlebell, pull-up bar, dips (chairs), floor. Bodyweight progress comes from
harder variations (ladders), not added weight. The plan follows Huberman's Foundational Fitness
Protocol: legs; recovery + posture; torso + neck; moderate cardio; high intensity; arms,
calves + neck; long zone 2. Rationale, volume per muscle and sources: `docs/specs/training-plan.md`
(ADR-0017). Data: `backend/src/training_coach/seed/plan.toml`.

## Daily flow

1. **Morning message** at a configurable time (default 07:30 Europe/Berlin) with the next
   session in the queue (ADR-0006) and a target per exercise based on the last performance,
   e.g. "Pull-ups 4 sets. Last: 8/7/6/5, aim 9/8/7/6" (ADR-0027; until its code lands the bot
   still aims 8/8/7/6 per ADR-0016). Buttons: Start, Rest today, Swap.
2. **Workout** (optional guided mode in phase 2: one exercise at a time, rest timer).
3. **Log** by one voice note or text: "pull-ups 8 8 7 6, dips 12 11 10".
4. **Confirm**: the bot shows what it understood; nothing is saved without "Save".
5. **Feedback**: personal bests; "ready to progress" when the advance rule is met.
6. **Evening nudge** (default 20:00) only if the day's session is not logged.
7. **Weekly review** (Sunday, phase 2): done vs planned, volume per muscle group, bests,
   what to progress next.

Missed session: the order is kept; everything shifts back one day (ADR-0006).

## Features by phase

| Feature | Phase |
| --- | --- |
| Plan, ladders, session queue, settings (morning time, nudges) | 1 |
| Morning message with targets, evening nudge | 1 |
| Text and voice logging with confirm step | 1 |
| Previous numbers, personal bests, ready-to-progress flags | 1 |
| `/today`, `/week`, `/progress`, `/settings`, `/rest`, `/help` | 1 |
| Nightly backup | 1 |
| Baseline tests and retests every 4-6 weeks | 2 |
| Weekly review message | 2 |
| Habit check-offs: morning light, sleep, protein | 2 |
| Body measurements and progress photos | 2 |
| Dashboard (web + Telegram Mini App), share links | 2 |
| Guided session mode with rest timers | 2 |
| MCP endpoint for Claude (read, log, propose plan changes) | 3 |
| Readiness check (sleep, soreness) that eases the session | 3 |

Deliberately out of scope: exercise video library (link per exercise instead), social feed,
AI-generated daily workouts (the plan is fixed and edited deliberately).

## Progression rule (default)

Each exercise has a ladder of variations and a rep range. When every working set reaches the
top of the range in two consecutive sessions, the exercise is flagged "ready to progress";
the user confirms moving to the next ladder step, and the target resets to the bottom of the
range. Timed exercises use seconds instead of reps.

## Baseline tests (phase 2)

Day 1: bodyweight, waist, chest, upper arm, thigh, photos, resting heart rate, max pull-ups,
max push-ups, max dips, dead hang. Day 2: Bulgarian split squat L/R, goblet squat 8 kg, single-
leg calf raise L/R, 12-minute run, deep squat hold, toe touch. Retest every 4-6 weeks under the
same conditions.

## Non-functional

- Phone-first; everything doable from Telegram.
- Private by default; dashboard shareable read-only (ADR-0012).
- Zero running cost (Groq free tier, self-hosted).
- Runs on a Raspberry Pi 5 from an SD card; max one day of data loss (ADR-0010).
