"""The home screen (B1): all-time totals, this week, ladder progress, recent days and today."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, Exercise, SessionTemplate, SetLog, Workout
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.services import retests, users
from training_coach.services.home import MOVED_UP, home
from training_coach.services.seed import apply_seed, load_plan

TZ = ZoneInfo("Europe/Berlin")
SUNDAY = date(2026, 10, 11)
MONDAY = SUNDAY - timedelta(days=6)


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _template(session: Session, slug: str) -> int:
    return session.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == slug)).one()


def _log(
    session: Session,
    slug: str,
    values: list[int],
    on: date,
    *,
    template: int | None = None,
    sides: tuple[Side, ...] = (Side.BOTH,),
    status: WorkoutStatus = WorkoutStatus.DONE,
) -> None:
    exercise = session.scalars(select(Exercise).where(Exercise.slug == slug)).one()
    state = users.exercise_state(session, exercise.id)
    assert state is not None
    workout = Workout(local_date=on, template_id=template, status=status)
    if status == WorkoutStatus.DONE:
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


def test_nothing_done_yet(plan: Session) -> None:
    found = home(plan, SUNDAY, TZ)
    totals = found.totals
    assert (totals.sessions, totals.sets, totals.reps, totals.cardio_minutes) == (0, 0, 0, 0)
    assert (totals.first_day, totals.days) == (None, 0)
    assert (found.week.start, found.week.done, found.week.planned) == (MONDAY, 0, 7)
    assert found.week.zone2_target == (180, 200)
    assert (found.progress.steps_climbed, found.progress.bests) == (0, [])
    assert found.recent == []
    assert found.today is not None  # the session at the queue's pointer


def test_totals_count_done_work_only(plan: Session) -> None:
    first = date(2026, 9, 1)
    _log(plan, "pull-up", [8, 8, 8], first, template=_template(plan, "torso"))
    # A one-sided set is one set; its reps on both sides are added.
    _log(plan, "bulgarian-split-squat", [10, 9], MONDAY, sides=(Side.LEFT, Side.RIGHT))
    _log(plan, "zone2", [45], MONDAY + timedelta(days=1))
    _log(plan, "pull-up", [], SUNDAY, template=_template(plan, "torso"), status=WorkoutStatus.REST)
    found = home(plan, SUNDAY, TZ)
    totals = found.totals
    assert totals.sessions == 3
    assert totals.sets == 3 + 2 + 1
    assert totals.reps == 24 + 2 * 19  # minutes of zone 2 are not reps
    assert totals.cardio_minutes == 45
    assert (totals.first_day, totals.days) == (first, (SUNDAY - first).days)


def test_week_recent_and_progress(plan: Session) -> None:
    torso = _template(plan, "torso")
    _log(plan, "pull-up", [5, 5, 5], MONDAY - timedelta(days=3), template=torso)  # last week
    _log(plan, "pull-up", [8, 8, 8], MONDAY, template=torso)  # a best at this step
    _log(plan, "zone2", [60], MONDAY + timedelta(days=2), template=_template(plan, "zone2"))
    plan.add(Event(kind=MOVED_UP, payload={}))
    plan.add(Event(kind="progress.not_yet", payload={}))
    plan.flush()
    found = home(plan, SUNDAY, TZ)
    assert (found.week.done, found.week.extras, found.week.zone2_minutes) == (2, 0, 60)
    assert found.progress.steps_climbed == 1
    assert found.progress.bests == ["Pull-up"]
    assert [(r.day, r.session) for r in found.recent] == [
        (MONDAY + timedelta(days=2), "Long zone 2"),
        (MONDAY, "Torso + neck"),
    ]  # last week's Friday is more than seven days ago


def test_an_extra_is_named_as_such(plan: Session) -> None:
    _log(plan, "dip", [10], SUNDAY)
    assert [r.session for r in home(plan, SUNDAY, TZ).recent] == ["Extra"]


def test_no_session_left_once_today_is_rested(plan: Session) -> None:
    today = home(plan, SUNDAY, TZ).today
    assert today is not None
    template = plan.scalars(select(SessionTemplate).where(SessionTemplate.name == today)).one()
    _log(plan, "pull-up", [], SUNDAY, template=template.id, status=WorkoutStatus.REST)
    assert home(plan, SUNDAY, TZ).today is None


def test_a_test_day_due_is_today(plan: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    due = retests.TestDayDue(day=1, name="Retest, day 1", tests=("Max pull-ups",))
    monkeypatch.setattr(retests, "due", lambda *_: due)
    assert home(plan, SUNDAY, TZ).today == "Retest, day 1"
