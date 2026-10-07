"""Bests and progression after a save, and the Move up / Not yet answers (#13, ADR-0025)."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    LadderStep,
    SessionTemplate,
    SetLog,
    Workout,
)
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.progression import Progress
from training_coach.domain.records import NewBests
from training_coach.services.progress import MoveOutcome, feedback, move_up, not_yet
from training_coach.services.seed import apply_seed, load_plan

DAY = date(2026, 10, 1)


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _exercise(session: Session, slug: str) -> Exercise:
    exercise = session.scalar(select(Exercise).where(Exercise.slug == slug))
    assert exercise is not None
    return exercise


def _step(session: Session, slug: str) -> LadderStep:
    state = session.get(ExerciseState, _exercise(session, slug).id)
    assert state is not None
    step = session.get(LadderStep, state.ladder_step_id)
    assert step is not None
    return step


def _template(session: Session, slug: str) -> int:
    template_id = session.scalar(select(SessionTemplate.id).where(SessionTemplate.slug == slug))
    assert template_id is not None
    return template_id


def _log(
    session: Session,
    slug: str,
    values: list[int],
    days: int,
    *,
    template: str | None = "torso",
    sides: tuple[Side, ...] = (Side.BOTH,),
    step: LadderStep | None = None,
) -> int:
    exercise = _exercise(session, slug)
    at = step or _step(session, slug)
    workout = Workout(
        local_date=DAY + timedelta(days=days),
        template_id=_template(session, template) if template else None,
        status=WorkoutStatus.DONE,
    )
    workout.sets = [
        SetLog(exercise_id=exercise.id, ladder_step_id=at.id, set_no=n, side=side, value=v)
        for n, v in enumerate(values, start=1)
        for side in sides
    ]
    session.add(workout)
    session.flush()
    return workout.id


TOP = [12, 12, 12, 12]  # pull-up in Torso: 4 sets of 5-12


def test_the_first_session_at_a_step_is_not_a_best_and_holds(plan: Session) -> None:
    (item,) = feedback(plan, _log(plan, "pull-up", [8, 7, 6, 6], 0))
    assert item.exercise == "Pull-up"
    assert item.bests == NewBests()
    assert item.status is Progress.HOLD
    assert item.next_step is None


def test_beating_earlier_sessions_is_a_best(plan: Session) -> None:
    _log(plan, "pull-up", [8, 7, 6, 6], 0)
    (item,) = feedback(plan, _log(plan, "pull-up", [9, 7, 6, 6], 2))
    assert item.bests == NewBests(best_set=9, total=28)


def test_two_sessions_at_the_top_are_ready(plan: Session) -> None:
    _log(plan, "pull-up", TOP, 0)
    (item,) = feedback(plan, _log(plan, "pull-up", TOP, 2))
    assert item.status is Progress.READY
    assert item.next_step == "Pause at top"


def test_an_extra_session_is_judged_by_the_plan(plan: Session) -> None:
    _log(plan, "pull-up", TOP, 0, template=None)
    (item,) = feedback(plan, _log(plan, "pull-up", TOP, 2, template=None))
    assert item.status is Progress.READY


def test_one_side_short_holds_unilateral_work(plan: Session) -> None:
    """kb-row is per side: the weaker side counts (ADR-0016)."""
    both = (Side.LEFT, Side.RIGHT)
    _log(plan, "kb-row", [20, 20, 20], 0, sides=both)
    workout = _log(plan, "kb-row", [20, 20, 20], 2, sides=both)
    row = plan.scalar(select(SetLog).where(SetLog.workout_id == workout, SetLog.side == Side.LEFT))
    assert row is not None
    row.value = 19
    plan.flush()
    (item,) = feedback(plan, workout)
    assert item.status is Progress.HOLD


def test_a_log_at_an_older_step_counts_for_bests_only(plan: Session) -> None:
    old = _step(plan, "pull-up")
    _log(plan, "pull-up", TOP, 0, step=old)
    state = plan.get(ExerciseState, old.exercise_id)
    assert state is not None
    state.ladder_step_id = plan.scalars(
        select(LadderStep.id).where(
            LadderStep.exercise_id == old.exercise_id, LadderStep.position == old.position + 1
        )
    ).one()
    (item,) = feedback(plan, _log(plan, "pull-up", TOP, 2, step=old))
    assert item.status is Progress.HOLD


def test_the_top_of_the_ladder_is_said_once(plan: Session) -> None:
    exercise = _exercise(plan, "pull-up")
    last = max(exercise.ladder, key=lambda s: s.position)
    state = plan.get(ExerciseState, exercise.id)
    assert state is not None
    state.ladder_step_id = last.id
    _log(plan, "pull-up", TOP, 0)
    (first,) = feedback(plan, _log(plan, "pull-up", TOP, 2))
    (again,) = feedback(plan, _log(plan, "pull-up", TOP, 4))
    assert first.status is again.status is Progress.TOP_OF_LADDER
    assert (first.note_top, again.note_top) == (True, False)


def test_feedback_lists_each_exercise_once_in_logged_order(plan: Session) -> None:
    workout = _log(plan, "dip", [10, 10, 10], 0)
    _log(plan, "pull-up", [5], 0)
    pull = plan.scalars(select(SetLog).join(Workout).where(Workout.id != workout)).all()
    for row in pull:
        row.workout_id = workout
    plan.flush()
    plan.expire_all()
    assert [i.exercise for i in feedback(plan, workout)] == ["Dip (chairs)", "Pull-up"]


def test_feedback_for_a_missing_workout_is_empty(plan: Session) -> None:
    assert feedback(plan, 999) == []


def test_move_up_when_ready(plan: Session) -> None:
    step = _step(plan, "pull-up")
    _log(plan, "pull-up", TOP, 0)
    _log(plan, "pull-up", TOP, 2)
    move = move_up(plan, step.exercise_id, step.id)
    assert move is not None
    assert (move.outcome, move.exercise, move.step) == (
        MoveOutcome.MOVED,
        "Pull-up",
        "Pause at top",
    )
    assert _step(plan, "pull-up").name == "Pause at top"
    kinds = plan.scalars(select(Event.kind)).all()
    assert "progress.moved_up" in kinds


def test_a_second_press_does_not_move_twice(plan: Session) -> None:
    step = _step(plan, "pull-up")
    _log(plan, "pull-up", TOP, 0)
    _log(plan, "pull-up", TOP, 2)
    move_up(plan, step.exercise_id, step.id)
    again = move_up(plan, step.exercise_id, step.id)
    assert again is not None
    assert again.outcome is MoveOutcome.ALREADY_MOVED
    assert _step(plan, "pull-up").name == "Pause at top"


def test_move_up_rechecks_the_rule(plan: Session) -> None:
    step = _step(plan, "pull-up")
    _log(plan, "pull-up", TOP, 0)
    _log(plan, "pull-up", [12, 12, 12, 11], 2)
    move = move_up(plan, step.exercise_id, step.id)
    assert move is not None
    assert move.outcome is MoveOutcome.NOT_READY
    assert _step(plan, "pull-up").id == step.id


def test_move_up_at_the_last_step(plan: Session) -> None:
    exercise = _exercise(plan, "pull-up")
    last = max(exercise.ladder, key=lambda s: s.position)
    state = plan.get(ExerciseState, exercise.id)
    assert state is not None
    state.ladder_step_id = last.id
    move = move_up(plan, exercise.id, last.id)
    assert move is not None
    assert move.outcome is MoveOutcome.NO_NEXT_STEP


def test_move_up_for_an_unknown_exercise(plan: Session) -> None:
    assert move_up(plan, 999, 1) is None


def test_not_yet_records_the_choice(plan: Session) -> None:
    step = _step(plan, "pull-up")
    assert not_yet(plan, step.exercise_id, step.id) == "Pull-up (Strict pull-up)"
    assert plan.scalars(select(Event.kind).where(Event.kind == "progress.not_yet")).one()
    dip = _step(plan, "dip")
    assert not_yet(plan, step.exercise_id, dip.id) is None  # a step of another exercise
    assert not_yet(plan, 999, step.id) is None


def test_a_backdated_log_is_compared_with_earlier_sessions_only(plan: Session) -> None:
    """ADR-0025: a record beats every *earlier* session; a later, better one doesn't count."""
    _log(plan, "pull-up", [10, 10, 10, 10], 0)
    _log(plan, "pull-up", [12, 12, 12, 12], 4)
    (item,) = feedback(plan, _log(plan, "pull-up", [11, 10, 10, 10], 2))
    assert item.bests == NewBests(best_set=11, total=41)
