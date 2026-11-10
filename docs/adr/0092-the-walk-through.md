# ADR-0092: The walk-through: a new person's plan from their answers, saved in one tap

- Status: Accepted
- Date: 2026-11-09
- Deciders: Liam (7 Nov 2026, the order and what's asked: `any-level-any-time.md` B5, "The
  owner's answers"; 8 Nov, the starters: S1 Decided; 9 Nov 2026, "accept all" on the build
  plan's 23 decisions, below under Decided)
- Changes: ADR-0082, ADR-0090 and ADR-0091 (an addendum in each)

## Context

Everyone but the owner starts on the `new_people` starter, the 3-day, with every exercise at the
bottom step of its ladder (ADR-0073, S1). Liam's answers on 7 Nov say the walk-through then moves
each exercise up to where the person wants to start: safety questions first, on the device; then
age and how they exercise now; then "can you do...?" per movement, walking up or down; then days,
minutes, exercises per session and kit. The plan comes from the starters he approved, fitted to
the answers, and the answers are kept with consent. The aim is a start that is positively doable
and never too hard.

The specs leave some things open: the order of kit and "can you do", the rule that suggests a
level, how a ladder is walked, how tapped days meet the starters' fixed rest places (ADR-0091),
what the `walkthrough` category holds, and where the rules run. A build plan (8 Nov) gave 23
decisions with a recommendation each, and Liam accepted all of them on 9 Nov. This ADR records
the result. The product rule holds throughout: the app suggests, the person decides. Nothing is
saved until the last screen's **Save**, and every value the app works out (a level, a
preference, the start day, leaving an exercise out) is a suggestion the person can change first.

## Decision

### Who sees it

- **A member on a starter.** `/join` ends with "Set up your plan", and Home shows a "Set up your
  plan (about 10 minutes)" card with "Later" until it's done (`settings.set_up_on`). It can be
  run again until the person's first workout is logged.
- **The owner** is never asked: his plan is the 7-day cycle, and nothing here touches it. He can
  open `/start` as a **try-out**: every screen, the result and the map, with Save replaced by
  "This is a try-out: nothing was saved".

### The screens, in order

One question per screen, Back on every one, and a progress line ("4 of 12"). Everything is held
in the browser's memory only, not in device storage, so a reload starts again; consent,
residence and the safety date are already on the server, so those screens are then skipped.

| # | Screen | Kept where |
| --- | --- | --- |
| 0 | **Welcome:** what it does, about 10 minutes, everything skippable, a private test | nothing |
| 1 | **Keep your answers?** The consent card for `walkthrough` (ADR-0090). "Not now" carries on: the plan is still made, the answers aren't kept | `consents` |
| 2 | **Where you live,** only if `users.country` is empty (ADR-0085 layer 3) | `users.country` |
| 3 | **Safety questions:** the ten on-device questions and their note (ADR-0085). Skipped with "You answered these on <date>" while current | `readiness_checks` (version and date only) |
| 4 | **Your age:** 18-34, 35-49, 50-64, 65-74, 75+ | answers, with consent |
| 5 | **How you exercise now:** how often (not at the moment, under once a week, 1-2, 3 or more times a week), how hard (easy, can talk in sentences; sometimes out of breath), how long (under 10, 10-30, over 30 minutes). One screen each | answers, with consent |
| 6 | **Everyday questions:** stand up from a chair without your hands? climb a flight of stairs without stopping? walk 10 minutes without stopping? get down to the floor and up again? (B5.2) | answers, with consent |
| 7 | **What you'd rather avoid:** the five switches (ADR-0083), off until tapped; "Keep me off the floor" marked "suggested" after a no to the floor question | `settings.avoid_*`, at Save |
| 8 | **Where you train** (home, gym, both) and **what's at home** (My equipment's list; skipped for gym only) | `settings.places`, `equipment`, at Save |
| 9 | **"Can you do...?"**: 13 ladders, the starters' 12 exercises and the tibialis raise. Each question shows the step's figure and cue: Yes, No, Not sure, Skip this one | levels in `exercise_state` at Save; the answers, with consent |
| 10 | **Days:** tap the weekdays | `plan_state.starts_on`; the tapped days only in the answers, with consent |
| 11 | **Minutes per session:** 20, 30, 40, or as long as it takes | `settings.session_minutes` |
| 12 | **Exercises per session:** 4, 6, 8, or as planned | `settings.session_exercises` |
| 13 | **Your plan:** the starter's sessions with each exercise at its step, trimmed to the minutes and count with what's dropped named, the week with dates and rest days, the body map at that length (home, and gym at both), and the notes. Any step can be changed (open steps only), and the days, minutes and count; a left-out exercise can be put back. **Save** | everything above, in one request |
| 14 | **Done:** "Your first session is on <day>", with links to Today and the stop signs | nothing |

The avoid switches and place and kit come before "Can you do" (Liam's list had kit last),
because they decide which steps can be asked: a step locked by a preference or missing kit is
never asked, as `domain.locks` already rules.

### How the plan is made

1. **The suggested level**, worked out from screens 4-6, first match wins: can't stand from a
   chair without hands, or can't walk 10 minutes: **1**. Can't climb a flight of stairs, or
   exercises under once a week (or not at the moment): **2**. Exercises 1-2 times a week, or
   only at talking effort, or for under 10 minutes: **3**. Otherwise **4**, never higher, since
   the questions walk up. Then 65-74 caps it at 3 and 75+ at 2. A skipped question matches no
   line, so it lowers nothing; the walk still places only on a Yes. The level only picks where
   each ladder's questions start (S1 Decided 4); it is never stored.
2. **Walking a ladder:** the first question is the first open step at the suggested level, or the
   nearest open step below it when the ladder has none there (the split squat starts at 2). Yes
   walks up, asking each next open step, until a No or the top; No walks down until a Yes or the
   bottom, which has no question and is the default. Not sure counts as No; Skip leaves the
   bottom. The placement is the highest Yes, with no cap going up. "Any push-ups, and how many?"
   is answered by the seed's fixed "Can you do 10...?" questions (ADR-0075): no number entry.
3. **The starter by days:** 1 or 2 days the 2-day, 3 the 3-day, 4 or more the 4-day (S1 Decided
   6: no 1- or 5-day starter). 1 day gets S1's note (the queue waits, so A one week and B the
   next happens by itself); 5-7 days get the cardio note (150 minutes a week; walking counts).
   No days tapped: the 3-day, starting tomorrow.
4. **Left out for now:** a suggested level of 1 leaves the split squat out (S1 Decided 3), shown
   on screen 13 with "Put it back". It is removed from the person's sessions in the saved plan
   (a template item has at least one set), so Plan and the map show it honestly.
5. **The trim** isn't written into the plan: minutes per session and exercises per session are
   settings the trim applies every day, in S1's trim order (ADR-0082 and its addendum). Screen
   13 previews it.
6. **Kit and preferences:** placements are only ever on open steps, so nothing needs moving.
7. **The gym version:** with places gym or both, Save writes the person's gym version from the
   placements (`gym_version.write`, S1 Decided 5). Later progress doesn't swap again.
8. **The week and the start:** the starter's rest places (ADR-0091) stay as approved. The start
   day is the next tapped day, today included, from which the pattern lands the most sessions on
   tapped days; screen 13 shows the week ("Mon A, Wed B, Fri C") and which tapped days it misses.
   The start is kept as `plan_state.starts_on` (ADR-0091 addendum).

### What's kept, and where

- **Training data, on the contract, kept after a withdrawal** (like the plan): the levels
  (`exercise_state`), the plan and its version, `session_minutes`, `session_exercises`,
  `places`, `equipment`, the five `avoid_*`, `plan_state.starts_on` and `settings.set_up_on`
  (the day it was done; it holds no answer).
- **The walk-through's answers, only with `walkthrough` consent:** a `walkthrough_answers`
  table, one row per person (`Owned`), replaced by a re-run: the wording version, when answered,
  the age band, the three exercise answers, the four everyday answers, the tapped weekdays and
  the placement answers (per exercise, the steps asked in order, each Yes, No, Not sure or Skip).
  Any answer can be empty: everything is skippable.
- **Not kept anywhere:** the safety answers (ADR-0085) and the suggested level, which can be
  worked out again from the row. Minutes, kit and places are not copied into the answers: their
  home is settings (ADR-0090 addendum).
- **Withdrawing** `walkthrough` deletes the row; the plan made from it stays. The export includes
  it; leaving and erasing delete it. No one else sees the answers: not Telegram, MCP, the AI
  summary or comment, the share card, logs, or the owner's People view.

### What runs in the browser

Answers sent to the server are health data even if not kept (ADR-0085). So the level rule and
the ladder walk run in the browser, as the safety note does, with table tests in Vitest
(`walkthrough/level.ts`, `walkthrough/walk.ts`). Without consent the answers never reach the
server: Save sends only the outcomes (the starter, a step per exercise, the leave-outs, the
settings and kit, the start day). With consent, Save sends the answers too, and the server
refuses them (403 `consent_needed`) if the category isn't open. The server sends each step's
needs and marks, and the browser applies the same lock rule during the walk (one TS copy of
`domain.locks`' matching, tested against shared cases), so screen 8 needs no round trip. Save
checks every lock again on the server.

### One save

`services/walkthrough.apply`, in one transaction, only while no workout is logged and no session
is in progress: swaps the starter, sets every level (one event each, with no answers in its
payload), removes the leave-outs, writes the settings, kit and gym version, sets `starts_on` and
`set_up_on`, makes one plan version "Set up with the walk-through" (dated today, so it replaces
"Starting plan" if they joined today), and keeps the answers when consent is open.

### API

- `GET /api/walkthrough`: who it's for (a member, the owner's try-out, done, or closed since a
  workout was logged), the 13 ladders with each step's id, name, level, question, cue, figure,
  needs and marks, the three starters (days, sessions with items and rest places), and the
  readiness and residence state.
- `POST /api/walkthrough/preview`: the outcomes, as Save sends them; answers the fitted sessions
  trimmed to the minutes and count, the week with dates, and the coverage (home, and gym at
  both). Saves nothing. Built on `plan_coverage`'s draft path, taking a whole starter and a trim
  (which also gives T2's "map at that length").
- `POST /api/walkthrough`: the same, plus the answers (with consent only) and the plan's
  revision. 409 once a workout is logged or a session is in progress; the owner gets 403.
- Unchanged: `/api/consents/walkthrough`, `/api/readiness`, `/api/account/residence`,
  `/api/equipment` (screen 8 uses its list; Save writes the kit).

## Decided (9 Nov 2026)

Liam's answer to the build plan's 23 decisions was "accept all", so each is decided as its
recommendation says:

1. **Avoid and place and kit come before "Can you do"**, as they decide which steps can be asked.
2. **The `walkthrough` category holds** the age band, how they exercise, the everyday answers,
   the tapped days and the can-you-do answers. Minutes, kit and places are ordinary settings and
   stay on withdrawal; the consent wording changes and goes to version 2 (ADR-0090 addendum).
3. **Age as five bands**, not a birth year. `settings.birth_year` (heart-rate zones, under `band`)
   isn't filled; Heart-rate zones can offer "use the age from your walk-through" later.
4. **The suggested level rule**, as above.
5. **Walking a ladder**, as above: Not sure is No, Skip is the bottom, no number entry.
6. **Tapped days and the rest places:** the approved patterns stay; the start day lands the most
   sessions on tapped days, and the days that don't fit are named. Setting `rest_after` from the
   gaps between tapped days was turned down: it changes the approved spacing.
7. **1 day and 5-7 days:** the 2-day with S1's note, and the 4-day with the cardio note. No days
   tapped: the 3-day, starting tomorrow.
8. **The rules run in the browser**, and the server sees outcomes only, plus the answers with
   consent. The cost: these rules live in TS, outside `domain/`'s 100% gate.
9. **Exercises per session is a setting**, `settings.session_exercises` (4, 6, 8 or empty), on
   Account too, applied by the trim before the minutes with ADR-0082's drop key (ADR-0082
   addendum). Short on time today trims on top.
10. **The start date** is a nullable `plan_state.starts_on` (ADR-0091 addendum).
11. **No goal (B5.6) and no quick checks (B5.3).** Nothing would use a goal; each question's
    "Not sure? Try one now, holding a counter" hint stands in for the checks.
12. **The easy start (B6) isn't in stage 5:** a follow-up the walk-through then offers as a
    switch. For 65-74 and 75+, screen 13 has a line about the balance and sit-to-stand snack,
    with nothing tracked.
13. **Run again until the first workout** (workouts restrict their sessions, so the starter can't
    be swapped after it). Then the card goes and Account keeps the separate settings; a re-check
    every 6-12 weeks (B6) is later work.
14. **The owner** is never prompted; `/start` is a try-out that saves nothing.
15. **Consent "Not now":** the walk-through carries on and keeps nothing; the card is shown at
    the start only.
16. **A reload starts again:** the answers are in memory only, never in device storage.
17. **No one else sees the answers**; they are in the export.
18. **The gym version is written once, at Save.** A later "you've reached standard push-ups: do
    the bench press at the gym? [tap]" suggestion is its own item.
19. **Locks during the walk** are applied in the browser from the steps' needs and marks; Save
    checks again on the server.
20. **The members' Plan page** hero ("Seven sessions ... an 8 kg kettlebell") reads from the
    plan instead, in the walk-through's last web PR.
21. **No weights asked for gym exercises:** the first gym session starts empty and carries over
    (ADR-0072).
22. **Not asked:** the talk test (on Account) and the last-set option (off for a new person's
    first 8 weeks, S1 and F2).
23. **Wording checks:** the everyday and exercise-habit questions join #556's clinician list;
    the answers row joins the DPIA and the privacy draft.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Rules in the browser, outcomes to the server, answers only with consent (chosen) | Without consent no answer is sent, so nothing is processed that wasn't agreed; one Save | The level rule and the walk live in TS, outside the domain gate; a TS copy of the lock rule |
| Rules on the server, in `domain/` | 100% coverage gate; one copy of the lock rule | Every answer reaches the server, consent or not: health data processed without a yes (ADR-0085) |
| Save each screen as it's answered | A reload keeps progress | Writes before the person decides; answers in the database without a final yes |
| A birth year, as heart-rate zones use | One age for everything | Keeps more than any rule needs |

## Consequences

- Build order, one PR each, each safe on `main` while nothing links to `/start`: this ADR; the
  schema (`walkthrough_answers`, `settings.session_exercises` and `set_up_on`,
  `plan_state.starts_on`) with keeping and erasing the answers; exercises per session in the
  trim and on Account, and the start date in the rest days; `walkthrough.apply` and its domain
  helpers (the starter by days, the start day); the API; three web PRs (screens 0-8 with the
  level rule and the try-out; the ladder walk and screens 10-12; screen 13, Save, screen 14,
  `/join`'s last step, Home's card and the Plan page's hero).
- Stops for Liam: after this ADR, and before the release that carries the schema migration (no
  data change, but the live file changes).
- The `walkthrough` consent wording goes to version 2 in `domain/consent.py` and the web's
  `consent/wording.ts`; nobody has given it yet, so nobody is asked again.
- Threat-model row: the answers kept without consent or after withdrawal, or shown anywhere but
  to the person and in their export.
- The everyday and exercise-habit questions need a clinician's check before the public release
  (#556); the DPIA and the privacy draft gain the answers' row.

## Addendum (9 Nov 2026): the save and the API as built

- **The start day and the starter are picked in the browser.** The tapped days are answers
  (ADR-0090 addendum), so without consent they never reach the server; Save and the preview send
  the starter and `starts_on` (today to 6 days on). `domain.walkthrough`'s `starter_days` and
  `start_day` are the rule, and the web's copy follows them.
- **"Starting plan" is dated at `plan.toml`'s newest version**, not the day someone joins, so the
  save's "Set up with the walk-through" usually comes after it rather than replacing it; it
  renames a version dated today when there is one.
- **A workout logged** means a workout of a planned session (done, rested or skipped): it holds
  that session in place, so it closes the walk-through. A walk or an extra names no session and
  leaves it open.
- **No figure field:** a step's figure is the web's own, found by the ladder's slug and the step's
  name, as everywhere else.
- **The lock cases** both copies of the rule are tested on: `frontend/src/walkthrough/lock-cases.json`
  (`backend/tests/domain/test_lock_cases.py` runs `domain.locks` against it).
