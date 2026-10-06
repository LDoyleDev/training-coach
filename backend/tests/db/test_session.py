from pathlib import Path

import pytest
from sqlalchemy import text

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
