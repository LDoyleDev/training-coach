# ADR-0068: Today shows what a day logged, with earlier days a tap away and their habits

- Status: Accepted
- Date: 2026-10-23
- Deciders: Liam

## Context

Today showed what to do next, but not what was already saved, so a finished day looked empty:
"Nothing left today". There was no way to look back at an earlier day's log without the
weekly review or Telegram. Habits could only be ticked for today on the web. The bot allows
today and the two days before (`LATE_DAYS`), so a forgotten tick from last week was lost.

## Decision

- **A day card on Today** (`GET /api/day?on=`, `services/day_view.py`). It lists everything
  saved on the day in saving order:
  - each workout's session, or "Extra: walk" for an unplanned one, and rest or skipped days;
  - each exercise with the ladder step it was done at, and its sets, left/right on one line
    for one-sided exercises, with units for timed sets;
  - the band's minutes and heart rate when the workout logs a run the band recorded;
  - what was typed with a cardio log (ADR-0067): effort, distance, pace worked out from the
    minutes and distance, and heart rate, each only when given.
- **Day navigation in the card.** ‹ and › step a day back or forward, and the arrow keys do
  the same. The date returns to today. The server sends its today and the account's first
  day, which bound the arrows. A later day, or one before the first, is refused with 422.
  Earlier days are read-only in the card: saving a missed session stays with Log another
  day (ADR-0060) and the unsaved-session prompt (ADR-0033).
- **The account's first day** is the earliest of the user row's creation and the first
  workout or habit tick. The owner's row was made by a migration after the first workouts,
  so its creation date alone would hide them.
- **Habits follow the card's day.** `GET /api/habits?day=` and `PUT /api/habits/{habit}?day=`
  take any day from the first day to today (`habits.backfill`, `domain.habits.can_backfill`).
  The view's week counts are that day's week up to that day. The bot and AI proposals keep
  the two-day `can_change` window: they answer a recent message, not a deliberate look back.
  Today's habits still show when the card can't load.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A day card with its own ‹ › (chosen) | Today's session controls stay as they are; one place for a day's log | The arrows sit in a card, not the page header |
| The whole Today page switches day | One "day" concept for the page | Every control (guided session, Rest, Swap, Undo) would need hiding or a past-day meaning |
| Widen `LATE_DAYS` for everyone | One rule | An old Telegram button or an AI proposal could change a week-old tick without a deliberate look |

## Consequences

- A finished day now shows what was done. Earlier days are one tap each.
- Weekly review numbers are computed from the ticks each time, so a filled-in tick shows
  there straight away.
- Editing an earlier day's workout from the card is not built. The card links nowhere: Log
  another day and Undo stay the ways to change a log.
