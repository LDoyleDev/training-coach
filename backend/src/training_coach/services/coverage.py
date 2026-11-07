"""The body map's numbers for one person: their plan's week, counted per muscle at the
ladder step each exercise is trained at (program-builder.md F, step 3). Read-only.

The step matters for the spine warning only: a squat or lunge loads the spine once its step
holds a weight (``muscles.step_stress``). An exercise nobody has started is counted at the
plan's starting step.

A session's home or gym version is counted (ADR-0071): the map shows one place at a time, and a
session with no gym version counts its one version at both.
"""

from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, ExerciseState, LadderStep
from training_coach.domain import coverage as domain
from training_coach.domain.enums import Place, Places
from training_coach.domain.muscles import step_stress
from training_coach.domain.places import day_place
from training_coach.services import guided, user_settings
from training_coach.services.plan_edit import places_for
from training_coach.services.plan_rows import PlannedItem, planned_sessions, with_draft
from training_coach.services.seed import ExerciseSeed, bundled_plan
from training_coach.services.today import ItemPlan


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


ADDS = 4  # exercises named under a muscle on the map


def would_add(found: domain.Coverage, place: Place) -> dict[str, list[str]]:
    """Per muscle, exercises that would add to it (program-builder.md F): ones that can be done at
    ``place`` and train it most, not already counted for it this week; a lengthened-position pick
    first (Decided 5), then by name."""
    catalogue = [e for e in bundled_plan().exercises if not e.retired and place in places_for(e)]
    out: dict[str, list[str]] = {}
    for m in found.muscles:
        counted = {s.exercise for s in m.sources}
        picks = [e for e in catalogue if e.muscles.get(m.muscle) == 1 and e.name not in counted]
        picks.sort(key=lambda e: (not e.lengthened, e.name))
        out[m.muscle] = [e.name for e in picks[:ADDS]]
    return out


def _minutes(items: Sequence[PlannedItem], exercises: Mapping[str, ExerciseSeed], kind: str) -> int:
    """About how long as planned, at the bottom of each range: where a new step starts."""
    plans = tuple(
        ItemPlan(
            exercise=exercises[i.exercise].name,
            kind=exercises[i.exercise].kind,
            step="",
            cue=None,
            per_side=i.per_side,
            targets=(i.rep_min,) * i.sets,
            pair=i.pair,
            slug=i.exercise,
        )
        for i in items
    )
    return guided.planned_minutes(plans, warm_up=kind == "strength")


def plan_coverage(
    session: Session,
    place: Place = Place.HOME,
    draft: Mapping[tuple[str, Place], Sequence[PlannedItem]] | None = None,
) -> domain.Coverage:
    """The week with each session's version at ``place``, and with ``draft``'s versions in place
    of the saved ones, for the map as a plan is edited (program-builder.md F). Nothing is saved."""
    exercises = {e.slug: e for e in bundled_plan().exercises}
    steps = trained_steps(session)
    week = []
    for planned in with_draft(planned_sessions(session), draft or {}):
        at = Place.GYM if place is Place.GYM and planned.gym else Place.HOME
        items = []
        version = planned.gym if at is Place.GYM else planned.items
        for item in version:
            ex = exercises[item.exercise]
            step = steps.get(ex.slug, ex.ladder[min(ex.start, len(ex.ladder) - 1)])
            items.append(
                domain.Item(
                    exercise=ex.name,
                    sets=item.sets,
                    muscles=dict(ex.muscles),
                    parts=frozenset(ex.parts),
                    stress=frozenset(step_stress(ex.stress, ex.pattern, ex.needs.get(step, []))),
                    pattern=ex.pattern,
                )
            )
        minutes = _minutes(version, exercises, planned.kind)
        week.append(domain.Day(planned.name, items, slug=planned.slug, place=at, minutes=minutes))
    return domain.coverage(week)
