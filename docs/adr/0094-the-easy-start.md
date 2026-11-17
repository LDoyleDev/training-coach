# ADR-0094: The easy start: a light start, then one set lower

- Status: Accepted
- Date: 2026-11-17
- Deciders: Liam (16 Nov 2026 the proposal; 17 Nov 2026 "I agree with the new positions": the
  17 decisions below, as revised after an evidence review)
- Changes: ADR-0082, ADR-0084 and ADR-0092 (an addendum in each)

## Context

ADR-0084 accepted an easy start "for a person at level 3 or below, or who says they're new to
training": a light start, then program-builder's Decided 7 (one set lower per exercise for four
weeks; a single set stays one). ADR-0092 (Decided 12) left it out of the walk-through, to be
offered there as a switch. None of it was built.

An evidence review (17 Nov 2026) of the first proposal changed most of its answers:

- **ICFSR 2021 doesn't prescribe "three or four exercises of one or two sets" for two weeks**, as
  ADR-0084 read it. It says resistance programmes start "with 1-2 sets and progressing to 2-3
  sets"; that 6-10 exercises "may be further broken down into sets of 3-4 exercises for novice
  trainees" (grouping, not cutting); and that endurance work starts at 5-10 minutes in the first
  weeks, progressing to 15-30 (Izquierdo et al., J Nutr Health Aging 25:824, full text read). No
  duration is given; the four weeks one set lower have no study of their own.
- **The soreness protection fades from the last bout, not the first.** One light bout protects for
  about two weeks, gone by three (Chen, Nosaka and Chen 2012); four light bouts protect as much as
  one hard one (Chen et al. 2010), and training renews it. So the light start is counted in
  sessions as well as days, and a long gap during it can start it again.
- **Cutting each session to four exercises left about half of it, balance included, undone**
  until a week where the sets doubled. Balance has the strongest falls evidence for people over
  65 (Sherrington et al. 2019, Cochrane: falls rate 0.76, high certainty) and costs almost no
  soreness. So the light start keeps every exercise at one set.
- **It cut volume, not effort**: each step is placed where the person says they can do it, so the
  light start also caps the target at the bottom of the range, and Move up waits.
- On the product side: a lock after the first workout took the choice away when it mattered
  most; skipped answers gave the least protective default; the bigger step (into one set lower)
  had no notice.

The review's sources were mostly read as abstracts; ICFSR was read in full. Figures it couldn't
verify are not relied on here.

## Decision

The easy start is a per-person setting. While it runs, it changes the plan for the day before the
person's own exercises per session and minutes trim it (ADR-0082). Two phases:

- **The light start:** every exercise at one set (its first), each set's target the bottom of its
  range, and a timed item (cardio) at most 10 minutes. Move up isn't offered. It ends at the later
  of 4 sessions and 14 days from the start.
- **One set lower:** every exercise one set fewer than planned (a single set stays one), timed
  items and targets as usual, Move up as usual. It ends at the later of 8 more sessions and 28
  days from the end of the light start.
- **The start** is the first logged workout of one of the person's own sessions after the switch
  was turned on (or the easy start restarted). A session counts when its workout is logged.
  Recovery sessions don't count and aren't changed (the trim leaves them as planned).

The overview names it every time, as a line: "Easy start: light, session 2 of 4 (until at least
3 Dec). Then a 5-10 minute walk, if you can walk safely on your own." In one set lower: "Easy
start: one set fewer of each, session 3 of 8 (until at least 31 Dec)."

## Decided (17 Nov 2026)

1. **Two phases:** the light start, then one set lower, as ADR-0084 accepted. The sources are
   corrected above.
2. **The light start's size:** every exercise at one set, not four exercises of two.
3. **Which exercises stay:** all of them (so the trim's drop key doesn't apply to the light start;
   the person's own exercises per session and minutes still trim on top, as on any day).
4. **Who is offered it:** everyone in the walk-through, as a switch on screen 13 ("Easy start:
   lighter first weeks, less soreness"). It is on, with the word "Suggested", at a suggested level
   of 3 or below, or when more than half of screens 4-6's questions were skipped. At level 4 it is
   off, labelled "New to strength work? Turn this on."
5. **On and off at any time** on Account until the easy start is over. Turning it off and on
   doesn't move the start: the phases still count from the first workout.
6. **Counted from the first logged workout** of one of the person's own sessions, not a walk logged
   through the bot or the plan's start day.
7. **Sessions with days as a floor:** the light start runs the later of 4 sessions and 14 days;
   one set lower the later of 8 sessions and 28 days.
8. **Both steps up are told:** a plan notice (ADR-0087) when one set lower begins ("Your light
   start is done: from today, one set fewer than planned of each exercise") and when the easy start
   ends ("Your easy start is done: full sessions from today"). Each has "One more easy week" on
   Today while it is new. The first session of a new phase says so on its overview, before the
   first set; in the last days of a phase the line says what comes next.
9. **A gap:** sessions count, so a gap pauses it. After 14 days or more without a workout while
   the easy start runs, Today offers "Start the easy start again" with a tap; it takes Ease back
   in's place for that return, so there is one prompt (ADR-0084).
10. **Move up waits** in the light start and is offered as usual in one set lower.
11. **The map and Plan show the plan as it is,** with one line naming the date: "Lighter until at
    least 31 Dec (easy start); this is the plan from then." Before the first workout: "for the first
    6 weeks or more". The walk-through's preview shows the same line.
12. **The walk is a line, not tracked,** worded "if you can walk safely on your own", on the
    overview in both phases. The end notice adds: "Build your walks up to 15-30 minutes."
13. **The owner is never offered it;** `/start`'s try-out shows the switch as a member sees it.
14. **The bot:** the morning message carries the overview's line; each notice goes on Telegram
    once (ADR-0087's path). No other messages.
15. **The re-check** (B6) is later work. The end notice links to Account's minutes, exercises per
    session and days.
16. **The light start's effort cap:** each set's target is the bottom of its range (decision 10's
    hold included). A weight is as the person sets it.
17. **"One more easy week" at most twice** in an easy start: it adds 7 days to the phase that just
    ended. A restart (9) begins again with none used.

## Stored

`settings` gains, all nullable or defaulted, so no row needs filling:

- `easy_start` (boolean, false): the switch.
- `easy_start_from` (date): the day it was turned on the first time or restarted; workouts before
  it don't count. Turning it off and on keeps it.
- `easy_start_weeks_light`, `easy_start_weeks_lower` (integers, 0): "One more easy week" taps per
  phase, at most 2 together.
- `easy_start_told` (`light`, `lower`, `done`): the last phase a notice was written for, so each is
  written once.

One migration, so its release changes live data. These are ordinary settings: in the export, kept
on a walkthrough consent withdrawal like minutes and kit (ADR-0092 Decided 2).

The default comes from the walk-through's answers (65 and over is capped at level 3), so a stored
`true` sits close to "65 or over, or low function". The person sees it and decides before Save, as
with the levels saved there; the DPIA gets a row for it.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A cap before the trim, phases worked out from the workouts and the setting (chosen) | One pure rule (`domain/easy_start.py`) at 100% coverage; every day view gets it; the plan isn't rewritten | Plan shows more than the person does for six weeks or more (the line explains) |
| Four exercises of two sets for two calendar weeks (the first proposal) | Shorter sessions | Half of each session, balance included, first done in a week where the sets double; days alone don't follow the protection |
| Write a light plan version, then restore | Plan and the map show what's done | Plan versions the person didn't make; a restore that can clash with their own edits (ADR-0093) |
| No easy start, Step down only | Nothing to build | Against ADR-0084; Step down lowers a step after two missed sessions, not the sets at the start |

## Consequences

- `domain/easy_start.py` (pure): the phase, the session count, the dates and the offers from the
  setting, the workout days and today. `domain/trim.py`'s caller applies the phase to the plan's
  set counts, durations and targets before the trim.
- Progression holds Move up in the light start; targets cap at the bottom of the range there.
- A migration for the five columns; Account and the walk-through's Save gain the switch; Today
  gains the restart offer and "One more easy week"; plan notices are written once per phase.
- The bot's morning message and the export carry it. Nothing changes for the owner.
- `any-level-any-time.md` B6 points here.
