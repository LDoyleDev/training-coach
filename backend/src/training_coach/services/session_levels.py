"""Changing an exercise's level during the guided session (ADR-0080).

On the set screen the person picks a step of the exercise's ladder, then says whether it is
**for today** (this session's sets of it are saved at that step and their level stays) or
**from now on** (the by-hand level change of the Plan tab, ADR-0075, through the same service
and event). Either way the rest of today's sets are at the chosen step, with that step's own
targets, and sets already confirmed keep the step they were done at.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import Exercise, LadderStep, SetLog
from training_coach.domain import kit as kit_rules
from training_coach.services import equipment, guided, progress, users
from training_coach.services.progress import Rung

NOT_IN_SESSION = "that exercise isn't in today's session"
NOT_ON_LADDER = "that step isn't on this exercise's ladder"


class Scope(StrEnum):
    TODAY = "today"  # this session only; the person's level stays
    FROM_NOW_ON = "from_now_on"  # the person's level, as on the Plan tab


@dataclass(frozen=True)
class Changed:
    revision: int  # the kept progress's, for the browser's next keep
    warning: str | None  # the chosen step needs kit that isn't listed: chosen anyway


def ladders(session: Session, slugs: Iterable[str]) -> dict[str, tuple[Rung, ...]]:
    """Each exercise's ladder, easiest first, with the kit each step lacks (ADR-0071), for the
    exercises that have more than one step: the others have no level to change."""
    kit = equipment.kit(session)
    found = session.scalars(
        select(Exercise).where(Exercise.slug.in_(set(slugs))).options(selectinload(Exercise.ladder))
    )
    return {
        exercise.slug: tuple(
            Rung(r.id, r.name, r.cue, tuple(kit_rules.missing(kit, needs)))
            for r, needs in zip(exercise.ladder, equipment.ladder_needs(exercise), strict=True)
        )
        for exercise in found
        if len(exercise.ladder) > 1
    }


def change(
    session: Session, plan: guided.Guided, revision: int, slug: str, step_id: int, scope: Scope
) -> Changed | str:
    """Put ``slug`` at ``step_id`` for the rest of ``plan``, for today or from now on. A problem
    in words, or ``guided.STALE`` when another device moved the session on since ``revision``;
    nothing changes then."""
    indexes = [i for i, item in enumerate(plan.items) if item.slug == slug]
    if not indexes:
        return NOT_IN_SESSION
    exercise = session.scalars(select(Exercise).where(Exercise.slug == slug)).one()
    step = session.get(LadderStep, step_id)
    if step is None or step.exercise_id != exercise.id:
        return NOT_ON_LADDER
    kept = guided.kept(session, plan.day)
    if kept is None or kept.template_id != plan.template_id or kept.after_run != plan.after_run:
        # Nothing kept for this session yet: start its progress, as the first confirmed set
        # would, so the choice has somewhere to live and a reload keeps it.
        started = guided.keep(session, plan, revision, 0, [], [])
        if isinstance(started, str):
            return started
        revision = started
    row = guided.progress_row(session, plan.day)
    assert row is not None  # noqa: S101 - kept or started above
    if row.saved_workout_id is not None:
        return "this session is saved already"
    if row.revision != revision:
        return guided.STALE
    # Sets already confirmed were done at the step shown for them: they keep it.
    shown = {i: plan.items[i].step_id for i in indexes}
    row.sets = [
        {**s, "step_id": shown[s["item"]]} if s["item"] in shown and not s.get("step_id") else s
        for s in row.sets
    ]
    if scope is Scope.TODAY:
        warning = progress.kit_warning(session, slug, step.name)
    else:
        moved = progress.set_level(session, exercise.id, step.id)
        warning = moved.warning if moved is not None else None
    # Today is at the step picked, either way: in a strength block a strength session would
    # otherwise train a step above the new level (ADR-0028).
    row.steps = {**row.steps, slug: step.id}
    row.revision += 1
    session.flush()
    return Changed(row.revision, warning)


def today_only(session: Session, steps: dict[str, int]) -> set[str]:
    """The exercises whose step today was chosen for today only: not the person's level."""
    if not steps:
        return set()
    query = select(Exercise.slug, Exercise.id).where(Exercise.slug.in_(steps))
    ids = dict(session.execute(query).all())
    found = set()
    for slug, step_id in steps.items():
        state = users.exercise_state(session, ids[slug]) if slug in ids else None
        if state is not None and state.ladder_step_id != step_id:
            found.add(slug)
    return found


def done_at(session: Session, day: date, workout_id: int) -> list[tuple[str, tuple[str, ...]]]:
    """For the saved screen: each exercise whose level changed in ``day``'s session, with the
    steps its sets in the workout were done at, in the order done."""
    row = guided.progress_row(session, day)
    if row is None or not row.steps:
        return []
    found: dict[str, list[str]] = {}
    rows = session.execute(
        select(Exercise.name, LadderStep.name)
        .select_from(SetLog)
        .join(Exercise, SetLog.exercise_id == Exercise.id)
        .join(LadderStep, SetLog.ladder_step_id == LadderStep.id)
        .where(SetLog.workout_id == workout_id, Exercise.slug.in_(row.steps))
        .order_by(SetLog.id)
    )
    for exercise, step in rows:
        steps = found.setdefault(exercise, [])
        if step not in steps:
            steps.append(step)
    return [(exercise, tuple(steps)) for exercise, steps in found.items()]
