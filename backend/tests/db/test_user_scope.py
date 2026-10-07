"""Sessions bound to a user see and write only that user's rows (ADR-0026, #72)."""

from datetime import date

import pytest
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from training_coach.db.models import Event, PlanState, User, UserSettings, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import users

DAY = date(2026, 10, 7)


@pytest.fixture
def two(engine: Engine) -> tuple[sessionmaker[Session], sessionmaker[Session]]:
    """The owner (user 1, from the migration) and a second person, each with a workout."""
    with session_scope(make_session_factory(engine)) as session:
        session.add(User(id=2))
    one, other = make_session_factory(engine, user_id=1), make_session_factory(engine, user_id=2)
    for sessions, status in ((one, WorkoutStatus.DONE), (other, WorkoutStatus.REST)):
        with session_scope(sessions) as session:
            session.add(Workout(local_date=DAY, status=status))
            session.add(UserSettings())
            session.add(Event(kind="settings.changed", payload={}))
    return one, other


def _statuses(sessions: sessionmaker[Session]) -> list[str]:
    with sessions() as session:
        return list(session.scalars(select(Workout.status)))


def test_each_user_sees_only_their_rows(
    two: tuple[sessionmaker[Session], sessionmaker[Session]],
) -> None:
    one, other = two
    assert _statuses(one) == ["done"]
    assert _statuses(other) == ["rest"]
    with other() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 1
        assert users.settings_row(session) is not None
        assert session.scalars(select(UserSettings.user_id)).all() == [2]


def test_new_rows_are_stamped_with_the_user(
    two: tuple[sessionmaker[Session], sessionmaker[Session]], engine: Engine
) -> None:
    with make_session_factory(engine)() as session:  # unbound: sees everyone
        owners = session.execute(select(Workout.user_id, Workout.status)).all()
    assert sorted(tuple(row) for row in owners) == [(1, "done"), (2, "rest")]


def test_a_bound_session_cannot_write_another_users_row(
    two: tuple[sessionmaker[Session], sessionmaker[Session]],
) -> None:
    _, other = two
    with pytest.raises(PermissionError), session_scope(other) as session:
        session.add(Workout(user_id=1, local_date=DAY, status=WorkoutStatus.DONE))


def test_bulk_deletes_are_scoped_too(
    two: tuple[sessionmaker[Session], sessionmaker[Session]],
) -> None:
    one, other = two
    with session_scope(other) as session:
        session.execute(delete(Workout))
    assert _statuses(other) == []
    assert _statuses(one) == ["done"]


def test_get_by_id_does_not_reach_another_users_row(
    two: tuple[sessionmaker[Session], sessionmaker[Session]], engine: Engine
) -> None:
    one, other = two
    with one() as session:
        own = session.scalars(select(Workout.id)).one()
    with other() as session:
        assert session.get(Workout, own) is None
        assert session.get(PlanState, 1) is None


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


def test_link_owner_recreates_a_missing_owner(engine: Engine) -> None:
    sessions = make_session_factory(engine)
    with session_scope(sessions) as session:
        session.delete(session.get_one(User, users.OWNER))
    with session_scope(sessions) as session:
        assert users.link_owner(session, 7) == users.OWNER
    with sessions() as session:
        assert session.get_one(User, users.OWNER).telegram_user_id == 7
