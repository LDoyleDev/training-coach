"""The body map's numbers for one person: the bundled plan's week, counted per muscle at the
ladder step each exercise is trained at (program-builder.md F, step 3). Read-only.

The step matters for the spine warning only: a squat or lunge loads the spine once its step
holds a weight (``muscles.step_stress``). An exercise nobody has started is counted at the
plan's starting step.

A session's home or gym version is counted (ADR-0071): the map shows one place at a time, and a
session with no gym version counts its one version at both.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, ExerciseState, LadderStep
from training_coach.domain import coverage as domain
from training_coach.domain.enums import Place, Places
from training_coach.domain.muscles import step_stress
from training_coach.domain.places import day_place
from training_coach.services import user_settings
from training_coach.services.seed import bundled_plan


def trained_steps(session: Session) -> dict[str, str]:
    """Exercise slug -> the name of the step this person is on, for exercises they've started."""
    return dict(
        session.execute(
            select(Exercise.slug, LadderStep.name)
            .join(ExerciseState, ExerciseState.exercise_id == Exercise.id)
            .join(LadderStep, LadderStep.id == ExerciseState.ladder_step_id)
        ).all()
    )


def map_place(session: Session) -> tuple[Places, Place]:
    """Where the person trains, and the place the map starts at: the day's place, so someone at
    both sees the one last chosen on Today's switch."""
    prefs = user_settings.load(session)
    return prefs.places, day_place(prefs.places, prefs.place)


def plan_coverage(session: Session, place: Place = Place.HOME) -> domain.Coverage:
    """The week with each session's version at ``place``."""
    plan = bundled_plan()
    exercises = {e.slug: e for e in plan.exercises}
    steps = trained_steps(session)
    week = []
    for planned in plan.sessions:
        at = Place.GYM if place is Place.GYM and planned.gym else Place.HOME
        items = []
        for item in planned.gym if at is Place.GYM else planned.items:
            ex = exercises[item.exercise]
            step = steps.get(ex.slug, ex.ladder[min(ex.start, len(ex.ladder) - 1)])
            items.append(
                domain.Item(
                    exercise=ex.name,
                    sets=item.sets,
                    muscles=dict(ex.muscles),
                    parts=frozenset(ex.parts),
                    stress=frozenset(step_stress(ex.stress, ex.pattern, ex.needs.get(step, []))),
                )
            )
        week.append(domain.Day(planned.name, items, slug=planned.slug, place=at))
    return domain.coverage(week)
