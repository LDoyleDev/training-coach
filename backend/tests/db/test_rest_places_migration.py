"""The rest places migration (ADR-0091): every existing session gets no rest places, so the queue
is as it was; 0 to 6 are allowed; a downgrade drops the column and keeps the sessions."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.db.test_migrations import BACKEND

BEFORE = "c3e5a7b9d1f4"
AFTER = "d5f7a9c1e3b6"


def test_sessions_keep_their_rows_and_get_no_rest_places(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from training_coach.config import get_settings

    url = f"sqlite:///{tmp_path / 'rest.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, BEFORE)
    engine = create_engine(url)
    with engine.begin() as db:  # the owner, user 1, is made by an earlier migration
        db.execute(
            text(
                "INSERT INTO session_templates (id, user_id, position, slug, name, focus)"
                " VALUES (1, 1, 0, 's1', 'S', 'F')"
            )
        )
    command.upgrade(cfg, AFTER)
    with engine.begin() as db:
        assert db.execute(text("SELECT id, rest_after FROM session_templates")).all() == [(1, 0)]
        db.execute(text("UPDATE session_templates SET rest_after = 6"))
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(text("UPDATE session_templates SET rest_after = 7"))
    command.downgrade(cfg, BEFORE)
    columns = {c["name"] for c in inspect(engine).get_columns("session_templates")}
    assert "rest_after" not in columns
    with engine.begin() as db:
        assert db.execute(text("SELECT id, slug FROM session_templates")).all() == [(1, "s1")]
    engine.dispose()
    get_settings.cache_clear()
