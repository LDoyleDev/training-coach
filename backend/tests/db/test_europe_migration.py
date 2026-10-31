"""The Europe-only migration (ADR-0085): everyone already there counts as just seen in Europe,
so the bot and MCP don't stop on deploy; a downgrade drops both columns."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from tests.db.test_migrations import BACKEND

BEFORE = "b7e1c3d5f9a2"  # the revision before country and last_seen_in_europe


def test_existing_people_are_seen_now_and_a_downgrade_drops_the_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import create_engine, inspect, text

    from training_coach.config import get_settings

    url = f"sqlite:///{tmp_path / 'europe.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, BEFORE)
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text("INSERT INTO users (id, created_at) VALUES (2, '2026-10-01 07:00:00')"))
    command.upgrade(cfg, "head")
    with engine.begin() as db:
        rows = db.execute(text("SELECT country, last_seen_in_europe FROM users")).all()
    assert len(rows) == 2  # the owner and the person added above
    for country, seen in rows:
        assert country is None
        moment = datetime.fromisoformat(seen).replace(tzinfo=UTC)
        assert abs(datetime.now(UTC) - moment) < timedelta(minutes=5)
    command.downgrade(cfg, BEFORE)
    columns = {c["name"] for c in inspect(engine).get_columns("users")}
    assert not {"country", "last_seen_in_europe"} & columns
    with engine.begin() as db:
        assert db.execute(text("SELECT count(*) FROM users")).scalar_one() == 2
    engine.dispose()
    get_settings.cache_clear()
