from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, ExerciseState, PlanState, SetLog, Workout
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.today import today, week

PLAN = """
[[exercises]]
slug = "pull-up"
name = "Pull-up"
kind = "reps"
start = 1
ladder = ["Negatives", "Strict", "Weighted"]

[[exercises]]
slug = "split-squat"
name = "Split squat"
kind = "reps"
start = 0
ladder = ["Bodyweight"]

[[exercises]]
slug = "run"
name = "Zone 2 run"
kind = "duration_min"
start = 0
ladder = ["Easy"]

[[sessions]]
slug = "upper"
name = "Upper"
focus = "Strength"
items = [
  { exercise = "pull-up", sets = 3, rep_min = 5, rep_max = 12 },
  { exercise = "split-squat", sets = 2, rep_min = 8, rep_max = 15, per_side = true },
]

[[sessions]]
slug = "zone2"
name = "Zone 2"
focus = "Easy aerobic"
items = [{ exercise = "run", sets = 1, rep_min = 45, rep_max = 75 }]

[[sessions]]
slug = "rest"
name = "Rest"
focus = "Recovery"
is_rest_optional = true
items = [{ exercise = "run", sets = 1, rep_min = 20, rep_max = 30 }]
"""

DAY = date(2026, 10, 6)


@pytest.fixture
def seeded(session: Session) -> Session:
    apply_seed(session, load_plan(PLAN))
    session.flush()
    return session


def _exercise(session: Session, slug: str) -> Exercise:
    return session.scalars(select(Exercise).where(Exercise.slug == slug)).one()


def _log(
    session: Session,
    slug: str,
    values: list[tuple[int, Side, int]],
    on: date = date(2026, 10, 1),
    template_id: int | None = None,
) -> None:
    exercise = _exercise(session, slug)
    step = session.get(ExerciseState, exercise.id)
    assert step is not None
    workout = Workout(local_date=on, template_id=template_id, status=WorkoutStatus.DONE)
    workout.sets = [
        SetLog(
            exercise_id=exercise.id, ladder_step_id=step.ladder_step_id, set_no=n, side=s, value=v
        )
        for n, s, v in values
    ]
    session.add(workout)
    session.flush()


def test_no_plan_means_none(session: Session) -> None:
    assert today(session, DAY) is None
    assert week(session, DAY) is None


def test_pointer_to_missing_session_means_none(seeded: Session) -> None:
    state = seeded.get(PlanState, 1)
    assert state is not None
    state.next_template_id = None
    seeded.flush()
    assert today(seeded, DAY) is None
    assert week(seeded, DAY) is None


def test_first_session_without_history_aims_for_the_bottom(seeded: Session) -> None:
    plan = today(seeded, DAY)
    assert plan is not None
    assert (plan.session.name, plan.session.focus, plan.session.optional) == (
        "Upper",
        "Strength",
        False,
    )
    pull_up, split_squat = plan.session.items
    assert (pull_up.exercise, pull_up.step, pull_up.kind) == (
        "Pull-up",
        "Strict",
        ExerciseKind.REPS,
    )
    assert pull_up.targets == (5, 5, 5)
    assert split_squat.per_side
    assert split_squat.targets == (8, 8)
    assert plan.logged_today == ()


def test_targets_step_up_from_the_last_session_at_the_same_step(seeded: Session) -> None:
    """ADR-0027: each set aims last value + about 10% of the range top (5-12: +1, 8-15: +2)."""
    _log(seeded, "pull-up", [(1, Side.BOTH, 8), (2, Side.BOTH, 7), (3, Side.BOTH, 6)])
    _log(
        seeded,
        "split-squat",
        [(1, Side.LEFT, 10), (1, Side.RIGHT, 9), (2, Side.LEFT, 9), (2, Side.RIGHT, 9)],
    )
    plan = today(seeded, DAY)
    assert plan is not None
    pull_up, split_squat = plan.session.items
    assert pull_up.targets == (9, 8, 7)
    assert split_squat.targets == (11, 11)  # weaker side counts: 9/9 -> +2 each


def test_latest_session_wins(seeded: Session) -> None:
    _log(
        seeded,
        "pull-up",
        [(1, Side.BOTH, 5), (2, Side.BOTH, 5), (3, Side.BOTH, 5)],
        on=date(2026, 9, 28),
    )
    _log(
        seeded,
        "pull-up",
        [(1, Side.BOTH, 9), (2, Side.BOTH, 9), (3, Side.BOTH, 9)],
        on=date(2026, 10, 2),
    )
    plan = today(seeded, DAY)
    assert plan is not None
    assert plan.session.items[0].targets == (10, 10, 10)


def test_logged_today_lists_each_workout(seeded: Session) -> None:
    upper = seeded.get(PlanState, 1)
    assert upper is not None
    seeded.add(
        Workout(local_date=DAY, template_id=upper.next_template_id, status=WorkoutStatus.SKIPPED)
    )
    _log(seeded, "run", [(1, Side.BOTH, 30)], on=DAY)
    plan = today(seeded, DAY)
    assert plan is not None
    assert plan.logged_today == ("Upper (skipped)", "Extra (done)")


def test_week_starts_today_and_wraps(seeded: Session) -> None:
    days = week(seeded, DAY, days=4)
    assert days is not None
    assert [(d.date.day, d.session) for d in days] == [
        (6, "Upper"),
        (7, "Zone 2"),
        (8, "Rest"),
        (9, "Upper"),
    ]


@pytest.mark.parametrize(
    ("status", "starts"),
    [(WorkoutStatus.REST, 7), (WorkoutStatus.DONE, 7), (WorkoutStatus.SKIPPED, 6)],
)
def test_week_starts_tomorrow_once_today_is_done(
    seeded: Session, status: WorkoutStatus, starts: int
) -> None:
    state = seeded.get(PlanState, 1)
    assert state is not None
    seeded.add(Workout(local_date=DAY, template_id=state.next_template_id, status=status))
    seeded.flush()
    days = week(seeded, DAY, days=1)
    assert days is not None
    assert days[0].date.day == starts


def test_missing_exercise_state_falls_back_to_the_first_rung(seeded: Session) -> None:
    seeded.delete(seeded.get(ExerciseState, _exercise(seeded, "pull-up").id))
    seeded.flush()
    plan = today(seeded, DAY)
    assert plan is not None
    assert plan.session.items[0].step == "Negatives"


def test_queued_sessions_missing_from_the_plan_are_ignored(seeded: Session) -> None:
    """A swap queued before a template was removed must not break /week or the queue."""
    state = seeded.get(PlanState, 1)
    assert state is not None
    state.queued = [999]
    seeded.flush()
    days = week(seeded, DAY, days=2)
    assert days is not None
    assert [d.session for d in days] == ["Upper", "Zone 2"]


def test_a_missed_target_is_held_across_logged_sessions(seeded: Session) -> None:
    """ADR-0027 through the database: history is replayed oldest first."""
    _log(
        seeded,
        "pull-up",
        [(1, Side.BOTH, 8), (2, Side.BOTH, 7), (3, Side.BOTH, 6)],
        on=date(2026, 9, 28),
    )  # next: 9 / 8 / 7
    _log(
        seeded,
        "pull-up",
        [(1, Side.BOTH, 9), (2, Side.BOTH, 7), (3, Side.BOTH, 7)],
        on=date(2026, 10, 2),
    )  # set 2 missed its 8
    plan = today(seeded, DAY)
    assert plan is not None
    assert plan.session.items[0].targets == (10, 8, 8)
