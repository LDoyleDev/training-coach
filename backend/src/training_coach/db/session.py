"""Engine and session factory. SQLite is tuned for an SD card: WAL, fewer fsyncs (ADR-0010).

A session can be bound to a user (ADR-0026, ADR-0029): every query it runs on an ``Owned``
(per-person) table is filtered to that user, and every new row it writes is stamped with them.
Services never filter by user themselves, so they can't forget to.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker, with_loader_criteria
from sqlalchemy.orm.attributes import get_history
from sqlalchemy.sql import visitors
from sqlalchemy.sql.expression import ClauseElement, TableClause

from training_coach.db.base import Base
from training_coach.db.models import Owned, SetLog, Workout

USER = "user_id"  # key in Session.info
# Execution option for shared checks that must see everyone's rows from any session (the
# seed's "is this ladder step in use" guard). Never for per-person reads.
ALL_USERS = "all_users"


def make_engine(database_url: str) -> Engine:
    # hide_parameters: an error message never carries values (measurements, token hashes) into
    # the logs (security review, 2026-10-10).
    engine = create_engine(database_url, future=True, hide_parameters=True)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine: Engine, user_id: int | None = None) -> sessionmaker[Session]:
    """Sessions for one user's data, or (``user_id`` None) unbound sessions for shared work
    such as seeding the plan and linking the owner's account."""
    return sessionmaker(bind=engine, expire_on_commit=False, info={USER: user_id})


def owned_models() -> list[type[Owned]]:
    """Every mapped per-person model, however deep below ``Owned`` it inherits."""
    return [m.class_ for m in Base.registry.mappers if issubclass(m.class_, Owned)]


def bound_user(session: Session) -> int | None:
    user = session.info.get(USER)
    return user if isinstance(user, int) else None


def _targets_owned(state: ORMExecuteState) -> bool:
    mapper = state.bind_mapper
    return mapper is not None and issubclass(mapper.class_, Owned)


def _touches_owned(state: ORMExecuteState) -> bool:
    """Whether the statement selects from or joins any per-person table."""
    if any(issubclass(mapper.class_, Owned) for mapper in state.all_mappers):
        return True
    owned = {model.__tablename__ for model in owned_models()}  # type: ignore[attr-defined]  # mapped models
    statement = state.statement
    if not isinstance(statement, ClauseElement):  # pragma: no cover - ORM statements always are
        return False
    return any(
        isinstance(element, TableClause) and element.name in owned
        for element in visitors.iterate(statement)
    )


@event.listens_for(Session, "do_orm_execute")
def _only_this_users_rows(state: ORMExecuteState) -> None:
    user = bound_user(state.session)
    if state.execution_options.get(ALL_USERS):
        return
    if user is None:
        # An unbound session is for shared work (the plan, linking the owner). Reading or
        # changing per-person rows there would see everyone, so it must say so explicitly.
        # Loads of an already-loaded row's columns or relationships follow that row's query.
        if _touches_owned(state) and not (state.is_column_load or state.is_relationship_load):
            raise PermissionError(
                "per-person rows need a session bound to their user, or all_users=True for "
                "a shared check"
            )
        return
    if (state.is_insert or state.is_update) and _targets_owned(state):
        # These skip the flush, so nothing would stamp or check the owner: per-person rows are
        # added and changed through the unit of work only.
        raise PermissionError("bulk inserts and updates of per-person rows are not allowed")
    if state.is_column_load or state.is_relationship_load:
        return  # the criteria of the parent query already apply
    if state.is_select or state.is_delete:
        state.statement = state.statement.options(
            *(
                with_loader_criteria(model, lambda cls: cls.user_id == user, include_aliases=True)
                for model in owned_models()
            )
        )


@event.listens_for(Session, "before_flush")
def _stamp_owner(session: Session, _context: object, _instances: object) -> None:
    user = bound_user(session)
    if user is None:
        return
    for row in session.new:
        if isinstance(row, Owned):
            if row.user_id is None:
                row.user_id = user
            elif row.user_id != user:
                raise PermissionError("a session bound to one user wrote another user's row")
    with session.no_autoflush:
        for row in session.new:
            # A set belongs to its workout's owner: one of this user's own workouts.
            if isinstance(row, SetLog):
                workout = row.workout
                if workout is None and row.workout_id is not None:
                    workout = session.get(Workout, row.workout_id)
                if workout is None or workout.user_id != user:
                    raise PermissionError("a set can only be added to the user's own workout")
    for row in session.dirty:
        if isinstance(row, Owned) and get_history(row, "user_id").has_changes():
            raise PermissionError("a row can't be handed to another user")


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
