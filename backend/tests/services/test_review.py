"""The weekly review (#73): what was done, hard sets per muscle, bests and what's ready."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, SessionTemplate, SetLog, Workout
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.records import NewBests
from training_coach.services import users
from training_coach.services.review import week_start, weekly
from training_coach.services.seed import apply_seed, load_plan

MONDAY = date(2026, 10, 5)
SUNDAY = MONDAY + timedelta(days=6)


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _exercise(session: Session, slug: str) -> Exercise:
    return session.scalars(select(Exercise).where(Exercise.slug == slug)).one()


def _torso(session: Session) -> int:
    return session.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == "torso")).one()


def _log(
    session: Session,
    slug: str,
    values: list[int],
    on: date,
    *,
    template: int | None = None,
    sides: tuple[Side, ...] = (Side.BOTH,),
) -> None:
    exercise = _exercise(session, slug)
    state = users.exercise_state(session, exercise.id)
    assert state is not None
    workout = Workout(local_date=on, template_id=template, status=WorkoutStatus.DONE)
    workout.sets = [
        SetLog(
            exercise_id=exercise.id,
            ladder_step_id=state.ladder_step_id,
            set_no=n,
            side=side,
            value=v,
        )
        for n, v in enumerate(values, start=1)
        for side in sides
    ]
    session.add(workout)
    session.flush()


def test_week_starts_on_monday() -> None:
    assert week_start(SUNDAY) == MONDAY
    assert week_start(MONDAY) == MONDAY


def test_an_empty_week(plan: Session) -> None:
    review = weekly(plan, SUNDAY)
    assert (review.start, review.planned, review.done, review.rested, review.extras) == (
        MONDAY,
        7,
        0,
        0,
        0,
    )
    assert (review.volume, review.bests, review.ready) == ([], [], [])


def test_sessions_done_rested_and_extra_this_week_only(plan: Session) -> None:
    torso = _torso(plan)
    _log(plan, "pull-up", [8, 8, 8, 8], MONDAY, template=torso)
    _log(plan, "dip", [10, 10, 10], MONDAY + timedelta(days=2))  # an extra
    plan.add(Workout(local_date=MONDAY + timedelta(days=1), template_id=torso, status="rest"))
    _log(plan, "pull-up", [5, 5, 5, 5], MONDAY - timedelta(days=1), template=torso)  # last week
    plan.flush()
    review = weekly(plan, SUNDAY)
    assert (review.done, review.rested, review.extras) == (1, 1, 1)


def test_hard_sets_count_once_per_muscle_group(plan: Session) -> None:
    """A set done on both sides is one set; each set counts for each of its muscle groups."""
    _log(plan, "pull-up", [8, 8, 8, 8], MONDAY)
    _log(plan, "bulgarian-split-squat", [10, 10], MONDAY, sides=(Side.LEFT, Side.RIGHT))
    volume = dict(weekly(plan, SUNDAY).volume)
    for group in _exercise(plan, "pull-up").muscle_groups:
        if group in volume:
            assert volume[group] >= 4
    split = [g for g in _exercise(plan, "bulgarian-split-squat").muscle_groups if g in volume]
    assert split
    assert all(volume[g] >= 2 for g in split)
    pull_only = set(_exercise(plan, "pull-up").muscle_groups) - set(
        _exercise(plan, "bulgarian-split-squat").muscle_groups
    )
    assert all(volume[g] == 4 for g in pull_only if g in volume)
    assert all(volume[g] == 2 for g in split if g not in _exercise(plan, "pull-up").muscle_groups)


def test_bests_this_week_keep_the_highest(plan: Session) -> None:
    _log(plan, "pull-up", [8, 8, 8, 8], MONDAY - timedelta(days=3))  # last week: the bar
    _log(plan, "pull-up", [9, 8, 8, 8], MONDAY)  # best set 9, total 33
    _log(plan, "pull-up", [10, 9, 8, 7], MONDAY + timedelta(days=3))  # best set 10, total 34
    (best,) = weekly(plan, SUNDAY).bests
    assert (best.exercise, best.step, best.bests) == (
        "Pull-up",
        "Strict pull-up",
        NewBests(best_set=10, total=34),
    )


def test_ready_to_move_up(plan: Session) -> None:
    _log(plan, "pull-up", [12, 12, 12, 12], MONDAY - timedelta(days=4))
    _log(plan, "pull-up", [12, 12, 12, 12], MONDAY)
    assert weekly(plan, SUNDAY).ready == ["Pull-up"]


def test_a_repeated_session_is_an_extra(plan: Session) -> None:
    torso = _torso(plan)
    _log(plan, "pull-up", [8, 8, 8, 8], MONDAY, template=torso)
    _log(plan, "pull-up", [8, 8, 8, 8], MONDAY + timedelta(days=4), template=torso)
    review = weekly(plan, SUNDAY)
    assert (review.done, review.extras) == (1, 1)  # never "8 of 7"


def test_only_done_workouts_count_toward_volume(plan: Session) -> None:
    _log(plan, "pull-up", [8, 8, 8, 8], MONDAY)
    skipped = plan.scalars(select(Workout)).one()
    skipped.status = WorkoutStatus.SKIPPED
    plan.flush()
    assert weekly(plan, SUNDAY).volume == []


def test_records_at_two_steps_are_kept_apart(plan: Session) -> None:
    """Moving up mid-week: a record at each step, never one merged from both."""
    pull_up = _exercise(plan, "pull-up")
    _log(plan, "pull-up", [8, 8, 8, 8], MONDAY - timedelta(days=3))
    _log(plan, "pull-up", [12, 12, 12, 12], MONDAY)  # best at Strict pull-up: 12, 48
    state = users.exercise_state(plan, pull_up.id)
    assert state is not None
    harder = next(s for s in pull_up.ladder if s.name == "Pause at top")
    state.ladder_step_id = harder.id
    _log(plan, "pull-up", [5, 5, 5, 5], MONDAY + timedelta(days=1))  # first at the new step
    _log(plan, "pull-up", [6, 6, 5, 5], MONDAY + timedelta(days=4))  # best there: 6, 22
    bests = [(b.step, b.bests) for b in weekly(plan, SUNDAY).bests]
    assert bests == [
        ("Strict pull-up", NewBests(best_set=12, total=48)),
        ("Pause at top", NewBests(best_set=6, total=22)),
    ]
