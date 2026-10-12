# ADR-0060: Log any day, any session, and ask before a day gets two

- Status: Accepted; extends ADR-0033 and replaces its "today's date on top is an ordinary log"
  for a line that names a session
- Date: 2026-10-12
- Deciders: Liam

## Context

On the Pi, Legs was logged live on 8 Oct, then backdated to 7 Oct, and then a rest day was
backdated to 8 Oct. Nothing asked: 8 Oct held both a Legs session and a rest day, and Legs
counted twice. Liam asked for three things: log a different session than the queue offers,
log any day (or another date) from the web, and when a log would land on a day that already
has its session, be asked, shown what is there, and choose to overwrite it, move it to another
day or add to that day.

ADR-0033 lets a bot log name a past day with a date line. ADR-0058 refused an AI's proposal for
an earlier day that already had its session (`workout_log.day_saved`). Nothing else checked.

## Decision

**Log any day on the web.** "Log another day" on the session page: pick a day (today back to
14 days, never the future), then what was done: any session in the plan, its exercises as an
extra, cardio (zone 2, moderate or HIIT, with what it was), or a rest day. A session opens its
exercises with that day's targets, to enter what was done. Everything is saved through
`workout_log.save` with ADR-0033's filing rules (that date, that date's block, the current
ladder steps), so it is idempotent by its token and /undo takes it back. Cardio on an earlier
day is an extra, as a band workout from then is (ADR-0055); today it is the same as Log
cardio. A rest day is for earlier days only: resting today is Rest today (ADR-0022).

**A different session today.** Today's log can name a session other than the queue's: on the
web by picking it, in the bot with `today <session>` or the session's name alone on the first
line (as ADR-0033 names one after a date). The queue rule is ADR-0016's, the one "Pick another
session" already uses (ADR-0022): a session done out of turn leaves the pointer where it is, so
the session at the pointer stays next. Naming the session at the pointer moves it on as usual.
No new queue rule.

**The question.** A planned session or a rest day saved for a day that already holds a planned
session (done or rested) or a rest day is a clash: nothing is saved, and the person sees what
is there, each with its name and a short summary ("Legs: 25 sets: Jump squat, ...", "45 min",
"rested"), and chooses:

- **Replace it:** the old workout is deleted and the new one saved.
- **Move the old one to another day:** the old workout keeps its sets, ladder steps and block;
  only its date changes (and the plan version in force then, ADR-0034). The day it moves to must
  be in the same 14 days and free: one that holds a session too is shown, and another day is
  asked for. There is no second question about that day.
- **Add it to that day:** both stay. Two planned sessions on one day (a run and a Tabata on a
  Sunday) is the usual reason.
- **Cancel.**

When the day holds more than one such workout (the 8 Oct data), replace and move act on all of
them. Extras, cardio extras among them, and held sessions (`skipped`) never clash.

**The answer is checked again when saving.** It names the workouts the person was shown. If the
day holds anything else by then (another device, Telegram), the question is asked again rather
than replacing what nobody saw. The move's day is checked again too. Check and save happen in
one transaction.

**The queue after a replace or a move** is ADR-0033's catching-up rule applied to the result
(`domain.queue.resettled`): when the latest planned session done (by date, then by when it was
logged) changed, the queue goes to the session after the new latest one, with any swap dropped;
when no planned session is left at all, the one that was latest is next again; otherwise an
older day changed and the queue stays, swaps and all. After any of these the pointer is what
logging the days in date order would give. Add follows the usual rules.

**One undo.** Each outcome is one `workout.logged` event that /undo takes back (ADR-0048):
undoing a replace removes the new workout and puts the old one back, sets and all; undoing a
move puts it back on its day. A replaced workout is kept in `replaced_workouts` for the undo
window (24 hours), because an event carries ids and dates only. It comes back as a new row:
SQLite may already have given its id to the workout that replaced it.

**API.** A save that clashes answers 409 with `detail` = what is there (`day`, `recorded`,
`moving`); the browser asks and sends the same save again with `resolution` = `replace`, `add`
or `move:YYYY-MM-DD` and `seen` = the ids it showed. The same holds for `/api/log`,
`/api/session/save` (an earlier day's guided session), `/api/cardio` and band offers
(`/api/band/{id}/count`); Telegram asks with buttons under the confirmation. A proposal from a
connected AI asks at Save time instead of being refused (ADR-0058).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Ask before saving, answer sent with the same save (chosen) | Nothing half-saved; one request to retry; works for every surface | Every save path learns one more answer |
| Save, then offer to fix the day | No question in the way | The wrong state exists, even briefly; the queue moves twice |
| One workout per day, enforced in the database | Simple rule | ADR-0014: two sessions a day is real |
| Recompute the whole queue from history after a replace | One rule | Swaps can't be rebuilt from history (ADR-0048); would undo out-of-turn sessions |
| Keep a replaced workout as a hidden status | No new table | Every history query would have to skip it |

## Consequences

- `services/day_clash.py` owns the question, the answers and putting back; `services/day_log.py`
  the web's any-day log; `domain.queue.resettled` the queue rule, with table tests.
- `workout_log.day_saved` goes once proposals ask instead (ADR-0058).
- Tests: `tests/services/test_day_clash.py` (the 8 Oct case end to end, both answers),
  `tests/api/test_log.py`, `tests/domain/test_queue.py`.
