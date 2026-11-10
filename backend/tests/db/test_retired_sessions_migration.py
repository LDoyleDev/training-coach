"""The retired sessions migration (ADR-0093): every session stays in the cycle with no retired
day; a downgrade drops the column and keeps the sessions, and refuses while one is retired."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text

from tests.db.test_migrations import BACKEND

BEFORE = "a1c3e5f7b9d2"
AFTER = "b3d5f7a9c1e4"
SESSION = (
    "INSERT INTO session_templates (id, user_id, position, slug, name, focus)"
    " VALUES ({id}, 1, {position}, 's{id}', 'S{id}', 'F')"
)


def _sql(engine: Engine) -> str:
    with engine.begin() as db:
        return str(
            db.execute(
                text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :t"),
                {"t": "session_templates"},
            ).scalar_one()
        )


def _upgraded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Config, Engine, str]:
    """Upgraded past it with two sessions; and the table's SQL as it was before."""
    from training_coach.config import get_settings

    url = f"sqlite:///{tmp_path / 'retired.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, BEFORE)
    engine = create_engine(url)
    with engine.begin() as db:  # the owner, user 1, is made by an earlier migration
        db.execute(text(SESSION.format(id=1, position=0)))
        db.execute(text(SESSION.format(id=2, position=1)))
    before = _sql(engine)
    command.upgrade(cfg, AFTER)
    return cfg, engine, before


def test_every_session_stays_in_the_cycle_and_a_downgrade_drops_the_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from training_coach.config import get_settings

    cfg, engine, before = _upgraded(tmp_path, monkeypatch)
    with engine.begin() as db:
        rows = db.execute(text("SELECT id, retired_on FROM session_templates ORDER BY id"))
        assert rows.all() == [(1, None), (2, None)]
    # ADD COLUMN only, no rebuild: the table is as it was, plus the column after the others.
    assert _sql(engine).replace(", retired_on DATE", "") == before
    with engine.begin() as db:  # a workout naming a session, kept through the rebuild below
        db.execute(
            text(
                "INSERT INTO workouts (user_id, local_date, template_id, status, created_at)"
                " VALUES (1, '2026-11-09', 2, 'done', '2026-11-09 07:00:00')"
            )
        )
    command.downgrade(cfg, BEFORE)
    columns = {c["name"] for c in inspect(engine).get_columns("session_templates")}
    assert "retired_on" not in columns
    with engine.begin() as db:
        assert db.execute(text("SELECT id, slug FROM session_templates")).all() == [
            (1, "s1"),
            (2, "s2"),
        ]
        assert db.execute(text("SELECT template_id FROM workouts")).all() == [(2,)]
    command.upgrade(cfg, AFTER)  # and back up again
    engine.dispose()
    get_settings.cache_clear()


def test_a_downgrade_refuses_while_a_session_is_retired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from training_coach.config import get_settings

    cfg, engine, _ = _upgraded(tmp_path, monkeypatch)
    with engine.begin() as db:  # retired as ADR-0093 says: the day, parked at 10_000 + id
        db.execute(
            text(
                "UPDATE session_templates SET retired_on = '2026-11-10', position = 10002"
                " WHERE id = 2"
            )
        )
    with pytest.raises(RuntimeError, match="Retired sessions: 1 "):
        command.downgrade(cfg, BEFORE)
    with engine.begin() as db:  # nothing went
        rows = db.execute(text("SELECT id, retired_on FROM session_templates ORDER BY id"))
        assert rows.all() == [(1, None), (2, "2026-11-10")]
    engine.dispose()
    get_settings.cache_clear()
