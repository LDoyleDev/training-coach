"""Stretching after a resistance session (#98, ADR-0032): the session's muscles from the plan,
the stretches from the bundled plan file, the choice from ``domain.stretching``, and the
minutes logged on the workout as the plan's mobility exercise."""

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import Exercise, SessionTemplate, SetLog, TemplateItem, Workout
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.stretching import CHOICES, Step, routine
from training_coach.services import users
from training_coach.services.seed import bundled_plan


def worked(session: Session, template_id: int) -> Counter[str] | None:
    """Planned sets per muscle group in a session, or None if there's no such session."""
    template = session.scalar(
        select(SessionTemplate)
        .where(SessionTemplate.id == template_id)
        .options(selectinload(SessionTemplate.items).selectinload(TemplateItem.exercise))
    )
    if template is None:
        return None
    sets: Counter[str] = Counter()
    for item in template.items:
        for group in item.exercise.muscle_groups:
            sets[group] += item.sets
    return sets


def for_session(session: Session, template_id: int, minutes: int) -> list[Step] | None:
    """The routine after ``template_id`` in ``minutes``, or None if there's no such session."""
    muscles = worked(session, template_id)
    if muscles is None:
        return None
    return routine([s.stretch() for s in bundled_plan().stretches], muscles, minutes)


MOBILITY = "mobility"  # the plan's stretching exercise, counted in minutes


@dataclass(frozen=True)
class Routine:
    session: str  # the session it follows, e.g. "Legs"
    minutes: int
    steps: list[Step]


def _strength_workout(session: Session, workout_id: int) -> tuple[Workout, SessionTemplate] | None:
    """A saved resistance workout of the bound user and its session, or None."""
    workout = session.scalar(select(Workout).where(Workout.id == workout_id))
    if workout is None or workout.status != WorkoutStatus.DONE or workout.template_id is None:
        return None
    template = session.get(SessionTemplate, workout.template_id)
    if template is None or template.kind != "strength":
        return None
    return workout, template


def offered(session: Session, workout_id: int) -> bool:
    """Whether stretching is offered after this workout: a saved resistance session."""
    return _strength_workout(session, workout_id) is not None


def for_workout(session: Session, workout_id: int, minutes: int) -> Routine | None:
    """The routine after a saved resistance workout, or None if there's no such workout,
    ``minutes`` isn't one of the choices, or no stretch was chosen (never an empty routine
    with a Done button that would log time nobody was given)."""
    found = _strength_workout(session, workout_id)
    if found is None or minutes not in CHOICES:
        return None
    _, template = found
    steps = for_session(session, template.id, minutes)
    return Routine(template.name, minutes, steps) if steps else None


def log(session: Session, workout_id: int, minutes: int) -> bool | None:
    """Add ``minutes`` of stretching to the workout: True when logged, False when it already
    has stretching (one per workout, so a second tap can't double it), None when there's no
    such workout, the time isn't a choice or the plan has no stretching exercise."""
    found = _strength_workout(session, workout_id)
    mobility = session.scalar(select(Exercise).where(Exercise.slug == MOBILITY))
    if found is None or mobility is None or not mobility.ladder or minutes not in CHOICES:
        return None
    workout, _ = found
    if any(s.exercise_id == mobility.id for s in workout.sets):
        return False
    state = users.exercise_state(session, mobility.id)
    step = state.ladder_step_id if state is not None else mobility.ladder[0].id
    workout.sets.append(
        SetLog(
            exercise_id=mobility.id, ladder_step_id=step, set_no=1, side=Side.BOTH, value=minutes
        )
    )
    session.flush()
    return True
