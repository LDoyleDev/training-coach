"""The session queue (ADR-0006, ADR-0014, ADR-0016). Pure logic, no I/O.

The plan is a cycle of sessions in a fixed order. A pointer names the next session. It moves
only when that session is completed as ``done`` or ``rest``. Nothing logged, a ``skipped``
workout, an extra (unplanned) workout or a session done out of order leaves it in place, so
the order is kept and everything later shifts back by a day.
"""

from collections.abc import Sequence
from datetime import date, datetime
from zoneinfo import ZoneInfo

from training_coach.domain.enums import WorkoutStatus

ADVANCING = frozenset({WorkoutStatus.DONE, WorkoutStatus.REST})


def next_in_cycle(order: Sequence[int], current: int) -> int:
    """The session after ``current`` in the cycle, wrapping from last to first."""
    if not order:
        raise ValueError("the plan has no sessions")
    try:
        index = order.index(current)
    except ValueError as exc:
        raise ValueError(f"session {current} is not in the plan") from exc
    return order[(index + 1) % len(order)]


def complete(
    order: Sequence[int],
    pointer: int,
    template_id: int | None,
    status: WorkoutStatus,
) -> int:
    """The pointer after logging one workout.

    Advances by exactly one when the workout completes the session at the pointer with an
    advancing status. Calling it again with the new pointer and the same workout does not
    advance again, so the caller must apply each workout once (the service guards that).
    """
    if template_id is None or status not in ADVANCING or template_id != pointer:
        return pointer
    return next_in_cycle(order, pointer)


def upcoming(order: Sequence[int], pointer: int, days: int) -> list[int]:
    """The sessions for the next ``days`` days if every one is completed on its day."""
    if days < 0:
        raise ValueError("days must be >= 0")
    sessions: list[int] = []
    current = pointer
    for _ in range(days):
        sessions.append(current)
        current = next_in_cycle(order, current)
    return sessions


def local_date(moment: datetime, tz: ZoneInfo) -> date:
    """The calendar date of an aware UTC moment in the user's timezone."""
    if moment.tzinfo is None:
        raise ValueError("naive datetime; pass an aware UTC datetime")
    return moment.astimezone(tz).date()
