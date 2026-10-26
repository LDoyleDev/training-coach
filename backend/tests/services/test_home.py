"""The home screen (B1): all-time totals, the last 7 days, ladder progress and today."""

from datetime import UTC, date, datetime, timedelta
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


def test_on_a_monday_the_card_counts_the_last_seven_days(plan: Session) -> None:
    """Owner, 26 Oct 2026: on a Monday the card said ~0 while the list under it showed the
    weekend's cardio; and moderate cardio was in the list but never added (ADR-0077)."""
    on = SUNDAY + timedelta(days=1)  # a Monday
    saturday = on - timedelta(days=2)
    _log(plan, "zone2", [50], saturday, template=_template(plan, "zone2"))
    torso = _template(plan, "torso")
    _log(plan, "pull-up", [5, 5, 5], on - timedelta(days=9), template=torso)  # the bar
    _log(plan, "pull-up", [8, 8, 8], saturday, template=torso)  # a best
    _log(plan, "moderate-cardio", [25], on - timedelta(days=6))  # the oldest of the 7 days
    _log(plan, "zone2", [40], on - timedelta(days=7))  # a week ago: outside
    _log(plan, "zone2", [30], on - timedelta(days=8))
    found = home(plan, on, TZ)
    week = found.week
    assert week.start == on - timedelta(days=6)
    assert (week.done, week.planned, week.extras) == (2, 7, 1)
    assert (week.zone2_minutes, week.moderate_minutes) == (50, 25)
    assert set(found.progress.bests) == {"Pull-up", "Zone 2 (conversational pace)"}
    assert [r.day for r in found.recent] == [saturday, saturday, on - timedelta(days=6)]


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
    assert home(plan, SUNDAY, TZ).today_minutes is None  # a test day has no estimate


def _timed(session: Session, template: int, on: date, minutes: int) -> None:
    """A done workout of ``template`` whose one set took ``minutes`` (ADR-0061)."""
    exercise = session.scalars(select(Exercise).where(Exercise.slug == "pull-up")).one()
    state = users.exercise_state(session, exercise.id)
    assert state is not None
    start = datetime(on.year, on.month, on.day, 16, 0, tzinfo=UTC)
    session.add(
        Workout(
            local_date=on,
            template_id=template,
            status=WorkoutStatus.DONE,
            sets=[
                SetLog(
                    exercise_id=exercise.id,
                    ladder_step_id=state.ladder_step_id,
                    set_no=1,
                    side=Side.BOTH,
                    value=5,
                    started_at=start,
                    done_at=start + timedelta(minutes=minutes),
                )
            ],
        )
    )
    session.flush()


def test_today_says_how_long_from_the_plan_until_it_is_timed(plan: Session) -> None:
    found = home(plan, SUNDAY, TZ)
    assert found.today_minutes is not None
    assert found.today_minutes > 0
    assert found.today_usual_minutes is None


def test_today_says_how_long_it_usually_takes(plan: Session) -> None:
    today = home(plan, SUNDAY, TZ).today
    template = plan.scalars(select(SessionTemplate.id).where(SessionTemplate.name == today)).one()
    for weeks, minutes in [(3, 40), (2, 30), (1, 35)]:
        _timed(plan, template, SUNDAY - timedelta(weeks=weeks), minutes)
    found = home(plan, SUNDAY, TZ)
    assert found.today == today  # earlier weeks don't move today's session
    assert found.today_usual_minutes == 35  # the median of the timed ones
