"""The body map's numbers for one person: the bundled plan's week, counted per muscle at the
ladder step each exercise is trained at (program-builder.md F, step 3). Read-only.

The step matters for the spine warning only: a squat or lunge loads the spine once its step
holds a weight (``muscles.step_stress``). An exercise nobody has started is counted at the
plan's starting step.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, ExerciseState, LadderStep
from training_coach.domain import coverage as domain
from training_coach.domain.muscles import step_stress
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


def plan_coverage(session: Session) -> domain.Coverage:
    plan = bundled_plan()
    exercises = {e.slug: e for e in plan.exercises}
    steps = trained_steps(session)
    week = []
    for planned in plan.sessions:
        items = []
        for item in planned.items:
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
        week.append(domain.Day(planned.name, items, slug=planned.slug))
    return domain.coverage(week)
