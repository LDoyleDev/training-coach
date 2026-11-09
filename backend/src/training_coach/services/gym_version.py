"""A person's gym version of their starter (any-level-any-time.md S1, Decided 5): each exercise
they are placed high enough on is done as its gym exercise (``plan.toml``'s ``[[gym_swaps]]``).

The walk-through's save (``walkthrough.apply``, ADR-0092) writes it when it makes their plan, on
the person's own tap, from the steps they were placed on. It changes only sessions that are
a starter's, so the owner's cycle and its written gym versions are never touched."""

from dataclasses import replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, ExerciseState, LadderStep
from training_coach.domain.enums import Place
from training_coach.domain.gym_swaps import Swap, swap_for
from training_coach.services import plan_edit
from training_coach.services.plan_edit import ItemEdit, Saved, VersionEdit
from training_coach.services.seed import PlanSeed

NOTE = "Gym version, from where you were placed"


def swaps(plan: PlanSeed) -> tuple[Swap, ...]:
    ladders = {e.slug: e.ladder for e in plan.exercises}
    return tuple(
        Swap(
            s.exercise,
            ladders[s.exercise].index(s.from_step),
            s.gym,
            s.rep_min,
            s.rep_max,
            frozenset(s.sessions),
        )
        for s in plan.gym_swaps
    )


def _placed(session: Session) -> dict[str, int]:
    """Exercise slug -> the ladder position this person is on."""
    return dict(
        session.execute(
            select(Exercise.slug, LadderStep.position)
            .join(ExerciseState, ExerciseState.exercise_id == Exercise.id)
            .join(LadderStep, LadderStep.id == ExerciseState.ladder_step_id)
        ).all()
    )


def _gym(item: ItemEdit, swap: Swap | None) -> ItemEdit:
    if swap is None:
        return item
    return replace(
        item, exercise=swap.gym, rep_min=swap.rep_min, rep_max=swap.rep_max, per_side=False
    )


def edits(session: Session, plan: PlanSeed) -> list[VersionEdit]:
    """The gym version of each of this person's starter sessions, from their home version and
    where they are placed now: empty, done the same way at the gym, when nothing is swapped."""
    starter = {s.slug for st in plan.starters for s in st.sessions}
    found, placed = swaps(plan), _placed(session)
    out = []
    for mine in plan_edit.editable(session):
        if mine.slug not in starter:
            continue
        gym = tuple(
            _gym(i, swap_for(found, mine.slug, i.exercise, placed.get(i.exercise, 0)))
            for i in mine.home
        )
        out.append(VersionEdit(mine.slug, Place.GYM, () if gym == mine.home else gym))
    return out


def write(session: Session, plan: PlanSeed, today: date) -> Saved | str:
    """Save ``edits`` as one plan version, as an edit of their own is (``plan_edit.save``):
    nothing changes when every gym version is already so, or for someone on no starter. It
    replaces a gym version they edited themselves, so anything but setup's first run shows what
    would change and saves on their yes."""
    return plan_edit.save(
        session, edits(session, plan), NOTE, plan_edit.revision(session), plan, today
    )
