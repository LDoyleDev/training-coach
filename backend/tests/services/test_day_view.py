"""What Today's day view lists for a day (ADR-0068)."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import update
from sqlalchemy.orm import Session

from tests import factories
from training_coach.db.models import (
    Exercise,
    HabitCheck,
    ImportedWorkout,
    LadderStep,
    SetLog,
    User,
    Workout,
)
from training_coach.domain.day_view import LoggedSet
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus
from training_coach.services import day_view
from training_coach.services.day_view import BandRun, CardioDetails

BERLIN = ZoneInfo("Europe/Berlin")
DAY = date(2026, 10, 23)


def _workout(session: Session, on: date = DAY, **fields: object) -> Workout:
    fields.setdefault("status", WorkoutStatus.DONE)
    row = Workout(local_date=on, **fields)
    session.add(row)
    session.flush()
    return row


def test_a_session_lists_its_exercises_steps_and_sets(session: Session) -> None:
    pull = factories.exercise(session)
    plan = factories.template(session, pull)
    workout = _workout(session, template_id=plan.id)
    step = pull.ladder[1]
    workout.sets = [
        SetLog(exercise_id=pull.id, ladder_step_id=step.id, set_no=n, side=Side.BOTH, value=v)
        for n, v in ((1, 8), (2, 7))
    ]
    session.flush()
    (found,) = day_view.logged(session, DAY)
    assert (found.name, found.status, found.planned, found.band) == ("Upper", "done", True, None)
    (exercise,) = found.exercises
    assert (exercise.name, exercise.unit, exercise.step) == ("Pull-up", "reps", "Strict")
    assert exercise.sets == (LoggedSet(1, 8), LoggedSet(2, 7))


def test_an_extra_and_a_counted_band_run_show_too(session: Session) -> None:
    extra = _workout(session, activity="walk")
    start = datetime(2026, 10, 23, 14, 26, tzinfo=UTC)
    session.add(
        ImportedWorkout(
            source="com.mi.health",
            start_at=start,
            end_at=start + timedelta(minutes=43),
            local_date=DAY,
            exercise_type=56,
            activity="run",
            minutes=43,
            avg_hr=139,
            max_hr=160,
            status="counted",
            workout_id=extra.id,
        )
    )
    rest = _workout(session, status=WorkoutStatus.REST)
    session.flush()
    walk, rested = day_view.logged(session, DAY)
    assert (walk.name, walk.planned, walk.activity) == ("Extra", False, "walk")
    assert walk.band == BandRun(43, 139, 160)
    assert (rested.workout_id, rested.status, rested.exercises) == (rest.id, "rest", ())


def test_a_day_with_nothing_logged_is_empty(session: Session) -> None:
    _workout(session)
    assert day_view.logged(session, DAY - timedelta(days=1)) == ()


def test_the_first_day_is_the_earliest_of_the_account_and_its_records(session: Session) -> None:
    made = datetime(2026, 10, 12, 22, 30, tzinfo=UTC)  # already the 13th in Berlin
    session.execute(update(User).values(created_at=made))
    assert day_view.first_day(session, BERLIN) == date(2026, 10, 13)
    session.add(HabitCheck(local_date=date(2026, 10, 9), habit="protein"))
    session.flush()
    assert day_view.first_day(session, BERLIN) == date(2026, 10, 9)
    _workout(session, on=date(2026, 10, 1))
    assert day_view.first_day(session, BERLIN) == date(2026, 10, 1)


def test_a_cardio_log_shows_what_was_typed_with_it(session: Session) -> None:
    run = Exercise(slug="moderate-cardio", name="Moderate cardio", kind=ExerciseKind.DURATION_MIN)
    run.ladder = [LadderStep(position=0, name="Run")]
    session.add(run)
    session.flush()
    workout = _workout(session, effort=6, distance_m=7290, avg_hr=139, max_hr=160)
    workout.sets = [
        SetLog(
            exercise_id=run.id, ladder_step_id=run.ladder[0].id, set_no=1, side=Side.BOTH, value=43
        )
    ]
    plain = _workout(session, activity="walk")
    session.flush()
    typed, walk = day_view.logged(session, DAY)
    # 43 min over 7.29 km: 5:54/km, 10.2 km/h
    assert typed.cardio == CardioDetails(6, 7290, 354, 139, 160, 10.2)
    assert typed.exercises[0].unit == "minutes"
    assert walk.workout_id == plain.id
    assert walk.cardio is None
