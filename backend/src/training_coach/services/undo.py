"""Undo the last change to the plan (ADR-0048): a rest day, a push to tomorrow, a swap or a
saved workout log.

Each of those records, in its event, the queue before and after it and the workout row it
added. Undoing puts the queue back and removes that workout, but only while nothing has moved
since: the queue must still be where the change left it. One step only: after an undo there is
nothing left to undo until the next change. The caller owns the transaction.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, SessionProgress, SessionTemplate, Workout
from training_coach.services import users

UNDOABLE = ("queue.rest", "queue.pushed", "queue.swapped", "workout.logged")
UNDONE = "undo.applied"
WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class Undoable:
    event_id: int
    what: str  # "the rest day for Moderate cardio"


@dataclass(frozen=True)
class Undone:
    what: str
    next_session: str | None


@dataclass(frozen=True)
class Blocked:
    reason: str  # one of NOTHING, TOO_OLD, CHANGED


NOTHING = "nothing"
TOO_OLD = "too_old"
CHANGED = "changed"


def snapshot(session: Session) -> list[Any] | None:
    """The queue as stored: ``[pointer, queued]``, or None when there is no plan."""
    state = users.plan_state(session)
    if state is None:
        return None
    return [state.next_template_id, list(state.queued)]


def record(
    before: list[Any] | None, after: list[Any] | None, workout: Workout | None
) -> dict[str, Any]:
    """What an event carries so it can be undone: ids and queue positions, nothing else."""
    return {"before": before, "after": after, "workout_id": workout.id if workout else None}


def _name(session: Session, template_id: object) -> str:
    template = session.get(SessionTemplate, template_id) if isinstance(template_id, int) else None
    return template.name if template is not None else "a session"


def _describe(session: Session, event: Event) -> str:
    p = event.payload
    if event.kind == "queue.rest":
        return f"the rest day for {_name(session, p.get('template_id'))}"
    if event.kind == "queue.pushed":
        return f"moving {_name(session, p.get('template_id'))} to tomorrow"
    if event.kind == "queue.swapped":
        return f"doing {_name(session, p.get('to'))} before {_name(session, p.get('from'))}"
    workout_id = p.get("undo", {}).get("workout_id")
    workout = session.get(Workout, workout_id) if isinstance(workout_id, int) else None
    day = f"{workout.local_date:%a %d %b}" if workout is not None else "that day"
    session_name = _name(session, p.get("template_id")) if p.get("template_id") else "extra"
    return f"the {session_name} log for {day} ({p.get('sets', 0)} sets)"


def _latest(session: Session) -> Event | None:
    return session.scalar(
        select(Event).where(Event.kind.in_((*UNDOABLE, UNDONE))).order_by(Event.id.desc()).limit(1)
    )


def last(session: Session, now: datetime) -> Undoable | Blocked:
    """The change /undo would take back, or why there is none."""
    event = _latest(session)
    if event is None or event.kind == UNDONE or not isinstance(event.payload.get("undo"), dict):
        return Blocked(NOTHING)
    if now - event.at > WINDOW:
        return Blocked(TOO_OLD)
    undo = event.payload["undo"]
    if undo.get("after") != snapshot(session):
        return Blocked(CHANGED)
    workout_id = undo.get("workout_id")
    if workout_id is not None and session.get(Workout, workout_id) is None:
        return Blocked(CHANGED)
    return Undoable(event.id, _describe(session, event))


def apply(session: Session, event_id: int, now: datetime) -> Undone | Blocked:
    """Take back the change in ``event_id`` if it is still the last one and nothing moved."""
    found = last(session, now)
    if isinstance(found, Blocked):
        return found
    if found.event_id != event_id:  # a button from an older /undo
        return Blocked(CHANGED)
    event = session.get_one(Event, event_id)
    undo = event.payload["undo"]
    state = users.plan_state(session)
    if state is not None and undo.get("before") is not None:
        pointer, queued = undo["before"]
        state.next_template_id = pointer
        state.queued = list(queued)
    workout_id = undo.get("workout_id")
    if workout_id is not None:
        # A guided session that was saved becomes unsaved again: its sets are kept.
        for progress in session.scalars(
            select(SessionProgress).where(SessionProgress.saved_workout_id == workout_id)
        ):
            progress.saved_workout_id = None
        session.delete(session.get_one(Workout, workout_id))
    session.add(Event(kind=UNDONE, payload={"event_id": event_id, "kind": event.kind}))
    session.flush()
    pointer = state.next_template_id if state is not None else None
    return Undone(found.what, _name(session, pointer) if pointer is not None else None)
