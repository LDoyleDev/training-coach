"""What locks ladder steps for the person (ADR-0071, ADR-0083): their home kit and the marks
they've chosen to avoid, read for the rules in ``domain.locks``. Every lock goes through here:
Move up, the levels on Plan and Progress, the set screen's picker and a level chosen by hand.
"""

from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, LadderStep
from training_coach.domain import locks
from training_coach.domain.locks import Asks, Limits, Lock
from training_coach.domain.step_levels import Mark
from training_coach.services import equipment, user_settings


def limits(session: Session, *, at_gym: bool = False, away: bool = False) -> Limits:
    """This person's limits. A gym has every kit (ADR-0071), away none (ADR-0086); what they
    avoid goes with them."""
    kit = None if at_gym else [] if away else equipment.kit(session)
    return Limits(kit, user_settings.load(session).avoid)


def _marks(step: LadderStep) -> tuple[Mark, ...]:
    return tuple(Mark(m) for m in step.marks)


def ladder(exercise: Exercise) -> list[Asks]:
    """What each of the exercise's ladder steps asks for, easiest first."""
    needs = equipment.ladder_needs(exercise)
    return [Asks(n, _marks(r)) for r, n in zip(exercise.ladder, needs, strict=True)]


def step_lock(session: Session, step: LadderStep, *, away: bool = False) -> Lock:
    """Why one step is locked for this person, at home (or away, with no kit: ADR-0086); open
    when nothing locks it."""
    needs = equipment.step_needs(step.exercise.slug).get(step.name, [])
    return locks.lock(Asks(needs, _marks(step)), limits(session, away=away))


def warning(session: Session, step: LadderStep, *, away: bool = False) -> str | None:
    """A locked step chosen by hand, in words; None when it is open."""
    return locks.warning(step.name, step_lock(session, step, away=away))
