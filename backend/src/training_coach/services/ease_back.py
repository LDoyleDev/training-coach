"""Ease back in after three weeks or more away (ADR-0084).

When an exercise in today's guided session hasn't been done for ``RETURN_DAYS`` or more, the
session overview offers one prompt for the whole return, "Ease back in: one step down today",
however many exercises it covers. Taken, each of them is done one step down for today only
(ADR-0080's "For today", through ``session_levels.change``): the person's levels stay. Either
answer is recorded with each exercise's last day, so the prompt is shown once per return, and a
later return (a new break) asks again. Nothing changes without a tap.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, Exercise, LadderStep, SetLog, Workout
from training_coach.domain.enums import WorkoutStatus
from training_coach.domain.progression import returning
from training_coach.services import blocks, equipment, guided, progress, users
from training_coach.services.session_levels import Changed, Scope, change

ANSWERED = "progress.ease_back"
NOTHING = "nothing to ease back into today"


@dataclass(frozen=True)
class Returning:
    """An exercise of today's session back after a break, and the step below its level."""

    exercise_id: int
    slug: str
    exercise: str
    last_done: date
    step_id: int  # one step down, offered for today
    step: str


def _last_done(session: Session, exercise_id: int) -> date | None:
    query = (
        select(func.max(Workout.local_date))
        .join(SetLog, SetLog.workout_id == Workout.id)
        .where(SetLog.exercise_id == exercise_id, Workout.status == WorkoutStatus.DONE)
    )
    return session.scalar(query)


def _answered(session: Session) -> set[tuple[int, str]]:
    """(exercise id, last day before the return) pairs already asked about."""
    found: set[tuple[int, str]] = set()
    for payload in session.scalars(select(Event.payload).where(Event.kind == ANSWERED)):
        if isinstance(payload, dict):
            found |= {(e, d) for e, d in payload.get("exercises", []) if isinstance(e, int)}
    return found


def offered(session: Session, plan: guided.Guided, kept: guided.Kept | None) -> list[Returning]:
    """The exercises of ``plan`` to ease back into: back after ``RETURN_DAYS`` or more, with an
    open step below their level, not on a loaded step (the weight is what to lower, ADR-0072)
    and not asked about for this return. Only before the session starts, and never for the block
    after a run. Empty when there is nothing to offer."""
    mine = (plan.template_id, plan.after_run, plan.place)
    if kept is not None and (kept.template_id, kept.after_run, kept.place) != mine:
        kept = None  # kept for a session that isn't today's
    if plan.after_run or (kept is not None and (kept.sets or kept.saved)):
        return []
    chosen = dict(kept.steps) if kept is not None else {}
    answered = _answered(session)
    kit = equipment.kit(session)
    found: dict[str, Returning] = {}
    for item in plan.items:
        if item.slug in found or item.slug in chosen:
            continue
        exercise = session.scalars(select(Exercise).where(Exercise.slug == item.slug)).one()
        state = users.exercise_state(session, exercise.id)
        step = session.get(LadderStep, state.ladder_step_id) if state is not None else None
        if step is None or blocks.load_kit(exercise.slug, step.name) is not None:
            continue
        below = progress.step_below(step, kit)
        last = _last_done(session, exercise.id)
        if below is None or last is None or not returning(last, plan.day):
            continue
        if (exercise.id, last.isoformat()) in answered:
            continue
        found[item.slug] = Returning(
            exercise.id, exercise.slug, exercise.name, last, below.id, below.name
        )
    return list(found.values())


def answer(
    session: Session, plan: guided.Guided, kept: guided.Kept | None, revision: int, ease: bool
) -> int | str:
    """One step down today for every exercise ``offered`` (``ease``), or not; either way
    recorded, so it isn't asked again for this return. The kept revision after it, or a problem
    in words (``guided.STALE`` when another device moved the session on); nothing is recorded
    then."""
    found = offered(session, plan, kept)
    if not found:
        return NOTHING
    if ease:
        for returned in found:
            result = change(session, plan, revision, returned.slug, returned.step_id, Scope.TODAY)
            if not isinstance(result, Changed):
                return result
            revision = result.revision
    exercises = [[r.exercise_id, r.last_done.isoformat()] for r in found]
    session.add(Event(kind=ANSWERED, payload={"exercises": exercises, "eased": ease}))
    return revision
