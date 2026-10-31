"""How long guided sessions take, read from their set times (ADR-0061)."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from tests import factories
from training_coach.db.models import Exercise, SessionTemplate, SetLog, Workout
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.services import session_times

START = datetime(2026, 10, 12, 16, 0, tzinfo=UTC)


def _workout(
    session: Session,
    template: SessionTemplate | None,
    exercise: Exercise,
    on: date,
    sets: list[tuple[int, int]],  # (minutes after START, seconds) per set; empty: untimed
    *,
    sides: bool = False,
) -> Workout:
    workout = Workout(
        local_date=on,
        template_id=template.id if template is not None else None,
        status=WorkoutStatus.DONE,
    )
    step = exercise.ladder[0].id
    for n, (after, seconds) in enumerate(sets or [(0, 0)], start=1):
        started = START + timedelta(minutes=after) if sets else None
        done = started + timedelta(seconds=seconds) if started is not None else None
        for side in (Side.LEFT, Side.RIGHT) if sides else (Side.BOTH,):
            workout.sets.append(
                SetLog(
                    exercise_id=exercise.id,
                    ladder_step_id=step,
                    set_no=n,
                    side=side,
                    value=8,
                    started_at=started,
                    done_at=done,
                )
            )
    session.add(workout)
    session.flush()
    return workout


def _sets(n: int) -> list[tuple[int, int]]:
    """``n`` one-minute sets, every three minutes: ``3n - 2`` minutes in all."""
    return [(3 * k, 60) for k in range(n)]


def test_a_workouts_time_counts_each_one_sided_set_once(session: Session) -> None:
    pull = factories.exercise(session)
    upper = factories.template(session, pull)
    workout = _workout(session, upper, pull, date(2026, 10, 12), [(0, 60), (2, 60)], sides=True)
    found = session_times.of_workout(session, workout.id)
    assert found is not None
    assert (found.total, found.on_sets, found.resting) == (
        timedelta(minutes=3),
        timedelta(minutes=2),
        timedelta(minutes=1),
    )


def test_an_untimed_workout_has_no_time(session: Session) -> None:
    pull = factories.exercise(session)
    workout = _workout(session, factories.template(session, pull), pull, date(2026, 10, 12), [])
    assert session_times.of_workout(session, workout.id) is None


def test_the_usual_time_is_from_this_sessions_timed_workouts(session: Session) -> None:
    pull = factories.exercise(session)
    upper = factories.template(session, pull)
    other = factories.template(session, pull, position=1)
    assert session_times.usual_minutes(session, upper.id) is None
    for day, n in ((10, 11), (11, 15), (12, 13)):  # 31, 43 and 37 minutes
        _workout(session, upper, pull, date(2026, 10, day), _sets(n))
    _workout(session, upper, pull, date(2026, 10, 13), [])  # a typed log: not timed
    _workout(session, other, pull, date(2026, 10, 13), _sets(20))
    assert session_times.usual_minutes(session, upper.id) == 37


def test_each_timed_session_in_plan_order(session: Session) -> None:
    pull = factories.exercise(session)
    upper = factories.template(session, pull, position=2)
    legs = factories.template(session, pull, position=1)
    legs.name = "Legs"
    factories.template(session, pull, position=0)  # never timed: not listed
    _workout(session, upper, pull, date(2026, 10, 12), _sets(16))  # 46, the latest
    _workout(session, upper, pull, date(2026, 10, 10), _sets(14))  # 40
    _workout(session, legs, pull, date(2026, 10, 11), _sets(11))  # 31
    _workout(session, None, pull, date(2026, 10, 12), _sets(3))  # an extra: no session
    found = session_times.by_session(session)
    assert [(t.session, t.usual, t.last, t.fastest, t.timed) for t in found] == [
        ("Legs", 31, 31, 31, 1),
        ("Upper", 43, 46, 40, 2),
    ]


def test_a_shorter_day_has_its_time_but_does_not_count_toward_usual(session: Session) -> None:
    """ADR-0082: a day run at 20 minutes says nothing about the session as planned."""
    pull = factories.exercise(session)
    upper = factories.template(session, pull)
    _workout(session, upper, pull, date(2026, 10, 12), _sets(5))  # 13 minutes
    short = _workout(session, upper, pull, date(2026, 10, 14), _sets(2))  # 4 minutes
    short.minutes = 20
    session.flush()
    assert session_times.usual_minutes(session, upper.id) == 13
    (times,) = session_times.by_session(session)
    assert (times.usual, times.last, times.fastest, times.timed) == (13, 13, 13, 1)
    found = session_times.of_workout(session, short.id)
    assert found is not None
    assert found.total == timedelta(minutes=4)
