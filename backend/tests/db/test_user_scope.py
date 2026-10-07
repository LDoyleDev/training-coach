"""Sessions bound to a user see and write only that user's rows (ADR-0026, ADR-0029, #72).

Each test has two people with the same kinds of rows, so a missing filter shows up as the
other person's data, not as an empty result that would pass anyway.
"""

from datetime import date

import pytest
from sqlalchemy import Engine, delete, insert, select, update
from sqlalchemy.orm import Session, sessionmaker

from tests import factories
from training_coach.db.models import (
    Event,
    LadderStep,
    PlanState,
    SetLog,
    User,
    UserSettings,
    Workout,
)
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.services import users

DAY = date(2026, 10, 7)
Sessions = sessionmaker[Session]


@pytest.fixture
def two(engine: Engine) -> tuple[Sessions, Sessions]:
    """The owner (user 1, from the migration) and user 2, each with a workout and a set at
    their own ladder step, settings, a plan row and an event."""
    with session_scope(make_session_factory(engine)) as session:
        session.add(User(id=2))
        exercise = factories.exercise(session)
        steps = [s.id for s in exercise.ladder]
        exercise_id = exercise.id
    one, other = make_session_factory(engine, user_id=1), make_session_factory(engine, user_id=2)
    for sessions, status, step in (
        (one, WorkoutStatus.DONE, steps[0]),
        (other, WorkoutStatus.REST, steps[1]),
    ):
        with session_scope(sessions) as session:
            workout = Workout(local_date=DAY, status=status)
            workout.sets = [
                SetLog(
                    exercise_id=exercise_id, ladder_step_id=step, set_no=1, side=Side.BOTH, value=8
                )
            ]
            session.add_all([workout, UserSettings(), PlanState(), Event(kind="x", payload={})])
    return one, other


def _all(sessions: Sessions, column: object) -> list[object]:
    with sessions() as session:
        return list(session.scalars(select(column)))  # type: ignore[call-overload]  # any column


def test_each_user_sees_only_their_rows(two: tuple[Sessions, Sessions]) -> None:
    one, other = two
    assert _all(one, Workout.status) == ["done"]
    assert _all(other, Workout.status) == ["rest"]
    for model in (Workout, SetLog, UserSettings, PlanState, Event):
        assert _all(one, model.user_id) == [1], model
        assert _all(other, model.user_id) == [2], model
    with other() as session:
        assert users.settings_row(session) is not None
        assert users.plan_state(session) is not None


def test_sets_are_scoped_on_their_own(two: tuple[Sessions, Sessions]) -> None:
    """A set selected without its workout is still filtered (review of #72)."""
    one, other = two
    own = _all(one, SetLog.id)
    with other() as session:
        assert session.get(SetLog, own[0]) is None
        assert session.scalars(select(SetLog.ladder_step_id)).all() != _all(
            one, SetLog.ladder_step_id
        )


def test_get_by_id_does_not_reach_another_users_row(two: tuple[Sessions, Sessions]) -> None:
    one, other = two
    with one() as session:
        own_workout = session.scalars(select(Workout.id)).one()
        own_plan = session.scalars(select(PlanState.id)).one()
    with other() as session:
        assert session.get(Workout, own_workout) is None
        assert session.get(PlanState, own_plan) is None


def test_a_cached_statement_never_serves_another_user(two: tuple[Sessions, Sessions]) -> None:
    one, other = two
    statement = select(Workout.status)
    for sessions, expected in ((one, "done"), (other, "rest"), (one, "done"), (other, "rest")):
        with sessions() as session:
            assert session.scalars(statement).all() == [expected]


def test_new_rows_are_stamped_and_others_refused(two: tuple[Sessions, Sessions]) -> None:
    _, other = two
    with pytest.raises(PermissionError), session_scope(other) as session:
        session.add(Workout(user_id=1, local_date=DAY, status=WorkoutStatus.DONE))


def test_a_set_cannot_be_added_to_another_users_workout(two: tuple[Sessions, Sessions]) -> None:
    one, other = two
    with one() as session:
        theirs = session.scalars(select(Workout.id)).one()
        step = session.scalars(select(LadderStep.id)).first()
        exercise = session.scalars(select(LadderStep.exercise_id)).first()
    with pytest.raises(PermissionError), session_scope(other) as session:
        session.add(
            SetLog(
                workout_id=theirs,
                exercise_id=exercise,
                ladder_step_id=step,
                set_no=2,
                side=Side.BOTH,
                value=1,
            )
        )
    assert len(_all(one, SetLog.id)) == 1


def test_a_row_cannot_be_handed_to_another_user(two: tuple[Sessions, Sessions]) -> None:
    one, other = two
    with pytest.raises(PermissionError), session_scope(other) as session:
        session.scalars(select(Workout)).one().user_id = 1
    assert _all(one, Workout.status) == ["done"]


@pytest.mark.parametrize(
    "statement",
    [
        pytest.param(update(Workout).values(user_id=1), id="bulk-update"),
        pytest.param(
            insert(Event).values(user_id=1, kind="x", payload={}), id="insert-skipping-flush"
        ),
    ],
)
def test_statements_that_skip_the_flush_are_refused(
    two: tuple[Sessions, Sessions], statement: object
) -> None:
    one, other = two
    with pytest.raises(PermissionError), session_scope(other) as session:
        session.execute(statement)  # type: ignore[call-overload]  # an ORM statement
    assert _all(one, Workout.user_id) == [1]
    assert len(_all(one, Event.id)) == 1


def test_bulk_deletes_are_scoped(two: tuple[Sessions, Sessions]) -> None:
    one, other = two
    with session_scope(other) as session:
        session.execute(delete(Event))
    assert _all(other, Event.id) == []
    assert len(_all(one, Event.id)) == 1


def test_all_users_is_an_explicit_opt_out(two: tuple[Sessions, Sessions]) -> None:
    """For shared checks such as the seed's ladder guard, never for per-person reads."""
    _, other = two
    with other() as session:
        everyone = session.scalars(
            select(SetLog.user_id), execution_options={ALL_USERS: True}
        ).all()
    assert sorted(everyone) == [1, 2]


def test_link_owner_links_and_follows_a_changed_account(engine: Engine) -> None:
    sessions = make_session_factory(engine)
    with session_scope(sessions) as session:
        assert users.link_owner(session, 4242) == users.OWNER
    with session_scope(sessions) as session:
        assert session.get_one(User, users.OWNER).telegram_user_id == 4242
        assert users.link_owner(session, 4242) == users.OWNER  # unchanged, nothing to do
    with session_scope(sessions) as session:
        users.link_owner(session, 99)  # the allowed account changed: the owner moves with it
    with sessions() as session:
        assert session.get_one(User, users.OWNER).telegram_user_id == 99
        kinds = session.scalars(select(Event.kind)).all()
    assert kinds == ["users.owner_relinked"]


def test_link_owner_recreates_a_missing_owner(engine: Engine) -> None:
    sessions = make_session_factory(engine)
    with session_scope(sessions) as session:
        session.delete(session.get_one(User, users.OWNER))
    with session_scope(sessions) as session:
        assert users.link_owner(session, 7) == users.OWNER
    with sessions() as session:
        assert session.get_one(User, users.OWNER).telegram_user_id == 7
