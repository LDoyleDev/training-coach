"""The roles migration (ADR-0059): the owner is the one admin, anyone else a member; a downgrade
drops both columns and keeps everyone."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests.db.test_migrations import BACKEND
from training_coach.config import get_settings

AFTER = "e2f4a6c8b0d1"
BEFORE = "d7a3f9c1e5b8"


def test_the_owner_is_admin_others_members_and_a_downgrade_drops_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'roles.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, BEFORE)
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO users (id, created_at, last_seen_in_europe)"
                " VALUES (2, '2026-11-01 07:00:00', '2026-11-01 07:00:00')"
            )
        )
        # users is rebuilt: a child row must survive it (foreign keys are off).
        db.execute(
            text(
                "INSERT INTO plan_state (user_id, queued, updated_at)"
                " VALUES (2, '[]', '2026-11-01 07:00:00')"
            )
        )
    command.upgrade(cfg, AFTER)
    with engine.begin() as db:
        rows = db.execute(text("SELECT id, role, label FROM users ORDER BY id")).all()
        assert [tuple(r) for r in rows] == [(1, "admin", None), (2, "member", None)]
        assert db.execute(text("SELECT user_id FROM plan_state")).scalars().all() == [2]
    command.downgrade(cfg, BEFORE)
    columns = {c["name"] for c in inspect(engine).get_columns("users")}
    assert not {"role", "label"} & columns
    with engine.begin() as db:
        assert db.execute(text("SELECT count(*) FROM users")).scalar_one() == 2
        assert db.execute(text("SELECT user_id FROM plan_state")).scalars().all() == [2]
    engine.dispose()
    get_settings.cache_clear()
