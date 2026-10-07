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

from training_coach.db.models import Owned

USER = "user_id"  # key in Session.info


def make_engine(database_url: str) -> Engine:
    engine = create_engine(database_url, future=True)
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


def bound_user(session: Session) -> int | None:
    user = session.info.get(USER)
    return user if isinstance(user, int) else None


@event.listens_for(Session, "do_orm_execute")
def _only_this_users_rows(state: ORMExecuteState) -> None:
    user = bound_user(state.session)
    if user is None or state.is_column_load or state.is_relationship_load:
        return
    if state.is_select or state.is_update or state.is_delete:
        state.statement = state.statement.options(
            *(
                with_loader_criteria(model, lambda cls: cls.user_id == user, include_aliases=True)
                for model in Owned.__subclasses__()
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
