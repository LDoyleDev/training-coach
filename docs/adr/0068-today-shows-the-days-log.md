# ADR-0068: Today shows what a day logged, with earlier days a tap away

- Status: Accepted
- Date: 2026-10-23
- Deciders: Liam

## Context

Today showed what to do next, but not what was already saved, so a finished day looked empty:
"Nothing left today". There was no way to look back at an earlier day's log without the
weekly review or Telegram.

## Decision

- **A day card on Today** (`GET /api/day?on=`, `services/day_view.py`). It lists everything
  saved on the day in saving order:
  - each workout's session, or "Extra: walk" for an unplanned one, and rest or skipped days;
  - each exercise with the ladder step it was done at, and its sets, left/right on one line
    for one-sided exercises, with units for timed sets;
  - the band's minutes and heart rate when the workout logs a run the band recorded.
- **Day navigation in the card.** ‹ and › step a day back or forward, and the arrow keys do
  the same. The date returns to today. The server sends its today and the account's first
  day, which bound the arrows. A later day, or one before the first, is refused with 422.
  Earlier days are read-only in the card: saving a missed session stays with Log another
  day (ADR-0060) and the unsaved-session prompt (ADR-0033).
- **The account's first day** is the earliest of the user row's creation and the first
  workout or habit tick. The owner's row was made by a migration after the first workouts,
  so its creation date alone would hide them.
- **Today's habits sit under the card** when it shows today.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A day card with its own ‹ › (chosen) | Today's session controls stay as they are; one place for a day's log | The arrows sit in a card, not the page header |
| The whole Today page switches day | One "day" concept for the page | Every control (guided session, Rest, Swap, Undo) would need hiding or a past-day meaning |

## Consequences

- A finished day now shows what was done. Earlier days are one tap each.
- Editing an earlier day's workout from the card is not built. The card links nowhere: Log
  another day and Undo stay the ways to change a log.
- The new cardio details (ADR-0067) can be added to the card's workout line once they land.
