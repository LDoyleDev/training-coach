"""The session queue (ADR-0006, ADR-0014, ADR-0016, ADR-0022). Pure logic, no I/O.

The plan is a cycle of sessions in a fixed order. A pointer names the next session. It moves
only when that session is completed as ``done`` or ``rest``. Nothing logged, a ``skipped``
workout, an extra (unplanned) workout or a session done out of order leaves it in place, so
the order is kept and everything later shifts back by a day.

A swap queues sessions ahead of the cycle: when the pointer moves it takes the first queued
session, and the cycle resumes once the queue is empty.
"""

from collections.abc import Sequence
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Position:
    """Where the queue stands: the next session, and sessions queued before the cycle resumes."""

    pointer: int
    queued: tuple[int, ...] = ()


def advance(order: Sequence[int], position: Position) -> Position:
    """The position after the session at the pointer is completed."""
    if position.queued:
        return Position(position.queued[0], position.queued[1:])
    return Position(next_in_cycle(order, position.pointer))


def complete(
    order: Sequence[int],
    position: Position,
    template_id: int | None,
    status: WorkoutStatus,
) -> Position:
    """The position after logging one workout.

    Advances by exactly one when the workout completes the session at the pointer with an
    advancing status. Calling it again with the new position and the same workout does not
    advance again, so the caller must apply each workout once (the service guards that).
    """
    if template_id is None or status not in ADVANCING or template_id != position.pointer:
        return position
    return advance(order, position)


def swap_with_next(order: Sequence[int], position: Position) -> Position:
    """Do the next session first and the current one after it (ADR-0022).

    With nothing queued, the cycle resumes after the session that was pulled forward, so
    neither session comes round twice: P N A B ... becomes N P A B ...
    """
    if len(order) < 2:
        raise ValueError("a swap needs at least two sessions in the plan")
    upcoming_session = advance(order, position)
    after = upcoming_session.queued or (next_in_cycle(order, upcoming_session.pointer),)
    return Position(upcoming_session.pointer, (position.pointer, *after))


def upcoming(order: Sequence[int], position: Position, days: int) -> list[int]:
    """The sessions for the next ``days`` days if every one is completed on its day."""
    if days < 0:
        raise ValueError("days must be >= 0")
    sessions: list[int] = []
    for _ in range(days):
        sessions.append(position.pointer)
        position = advance(order, position)
    return sessions


def local_date(moment: datetime, tz: ZoneInfo) -> date:
    """The calendar date of an aware UTC moment in the user's timezone."""
    if moment.tzinfo is None:
        raise ValueError("naive datetime; pass an aware UTC datetime")
    return moment.astimezone(tz).date()
