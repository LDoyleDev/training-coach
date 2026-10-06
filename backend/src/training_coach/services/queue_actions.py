"""What the morning buttons do to the queue (ADR-0006, ADR-0014, ADR-0016, ADR-0022).

Every action names the session it was offered for. If the queue has moved on since (a button
on an old message), nothing changes and the action returns ``None`` so the bot can say so.
The caller owns the transaction.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, PlanState, SessionTemplate, Workout
from training_coach.domain.enums import WorkoutStatus
from training_coach.domain.queue import Position, complete, swap_with_next
from training_coach.services.today import SessionPlan, session_plan


@dataclass(frozen=True)
class RestOutcome:
    session: str
    advanced: bool  # True for a planned (optional) rest; False when the session waits a day


def _state_at(session: Session, template_id: int) -> PlanState | None:
    state = session.get(PlanState, 1)
    if state is None or state.next_template_id != template_id:
        return None
    return state


def _order(session: Session) -> list[int]:
    return list(session.scalars(select(SessionTemplate.id).order_by(SessionTemplate.position)))


def _save(state: PlanState, position: Position) -> None:
    state.next_template_id = position.pointer
    state.queued = list(position.queued)


def rest_today(session: Session, template_id: int, on: date) -> RestOutcome | None:
    """Rest instead of the offered session.

    The optional rest session counts as done and the queue moves on (ADR-0006). Any other
    session is held for tomorrow: a ``skipped`` workout, which also silences the nudge.
    """
    state = _state_at(session, template_id)
    template = session.get(SessionTemplate, template_id)
    if state is None or template is None:
        return None
    status = WorkoutStatus.REST if template.is_rest_optional else WorkoutStatus.SKIPPED
    session.add(Workout(local_date=on, template_id=template_id, status=status))
    position = Position(template_id, tuple(state.queued))
    _save(state, complete(_order(session), position, template_id, status))
    session.add(Event(kind="queue.rest", payload={"template_id": template_id, "status": status}))
    return RestOutcome(session=template.name, advanced=template.is_rest_optional)


def push_to_tomorrow(session: Session, template_id: int, on: date) -> str | None:
    """Hold the offered session for tomorrow; everything after it shifts a day (ADR-0006)."""
    state = _state_at(session, template_id)
    template = session.get(SessionTemplate, template_id)
    if state is None or template is None:
        return None
    session.add(Workout(local_date=on, template_id=template_id, status=WorkoutStatus.SKIPPED))
    session.add(Event(kind="queue.pushed", payload={"template_id": template_id}))
    return template.name


def swap_next(session: Session, template_id: int) -> SessionPlan | None:
    """Do the next session today and the offered one tomorrow (ADR-0022)."""
    state = _state_at(session, template_id)
    order = _order(session)
    if state is None or len(order) < 2:
        return None
    swapped = swap_with_next(order, Position(template_id, tuple(state.queued)))
    _save(state, swapped)
    session.add(Event(kind="queue.swapped", payload={"from": template_id, "to": swapped.pointer}))
    return session_plan(session, swapped.pointer)


def pick(session: Session, template_id: int, picked_id: int) -> SessionPlan | None:
    """Show another session for today. The queue stays put: doing it is an out-of-order
    session (ADR-0016), so the offered one is still next tomorrow."""
    if _state_at(session, template_id) is None or picked_id == template_id:
        return None
    plan = session_plan(session, picked_id)
    if plan is not None:
        session.add(
            Event(kind="queue.picked", payload={"offered": template_id, "picked": picked_id})
        )
    return plan


def choices(session: Session) -> list[tuple[int, str]]:
    """Every session in plan order, for the pick menu."""
    rows = session.execute(
        select(SessionTemplate.id, SessionTemplate.name).order_by(SessionTemplate.position)
    )
    return [(template_id, name) for template_id, name in rows]
