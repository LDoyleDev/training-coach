from pathlib import Path

import pytest
from sqlalchemy import Engine, select, text

from tests import factories
from training_coach.db.models import Exercise
from training_coach.db.session import make_engine, make_session_factory, session_scope


def test_sqlite_pragmas_applied(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_session_scope_rolls_back_on_error(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        session.execute(text("CREATE TABLE t (x INTEGER)"))

    def insert_then_fail() -> None:
        with session_scope(factory) as session:
            session.execute(text("INSERT INTO t VALUES (1)"))
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        insert_then_fail()
    with session_scope(factory) as session:
        assert session.execute(text("SELECT COUNT(*) FROM t")).scalar() == 0


def _saved(engine: Engine, slug: str) -> bool:
    with make_session_factory(engine)() as session:
        return session.scalars(select(Exercise).where(Exercise.slug == slug)).first() is not None


def test_a_savepoint_opened_first_stays_inside_the_transaction(engine: Engine) -> None:
    """sqlite3 began a transaction only at an INSERT, so a savepoint opened before any write
    stood alone: releasing it committed its rows, and the rollback left them in."""
    with make_session_factory(engine)() as session:
        with session.begin_nested():
            factories.exercise(session, "in-the-savepoint")
        session.rollback()
    assert not _saved(engine, "in-the-savepoint")


def test_a_savepoint_after_reads_stays_inside_the_transaction(engine: Engine) -> None:
    with make_session_factory(engine)() as session:
        session.scalars(select(Exercise)).all()  # a read began no transaction either
        with session.begin_nested():
            factories.exercise(session, "after-a-read")
        session.rollback()
    assert not _saved(engine, "after-a-read")


def test_a_savepoint_inside_a_write_undoes_only_its_own_rows(engine: Engine) -> None:
    with make_session_factory(engine)() as session:
        factories.exercise(session, "kept")  # the transaction is open already
        with session.begin_nested() as savepoint:
            factories.exercise(session, "undone")
            savepoint.rollback()
        session.commit()
    assert _saved(engine, "kept")
    assert not _saved(engine, "undone")
