"""The easy start migration (ADR-0094): every settings row gets the switch off, no day, no easy
weeks and nothing told; the checks hold; a downgrade drops the columns and keeps the rows."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.db.test_migrations import BACKEND

BEFORE = "b3d5f7a9c1e4"
AFTER = "c5e7a9b1d3f6"
COLUMNS = (
    "easy_start, easy_start_from, easy_start_weeks_light, easy_start_weeks_lower, easy_start_told"
)


def test_off_for_everyone_and_a_downgrade_keeps_the_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from training_coach.config import get_settings

    url = f"sqlite:///{tmp_path / 'easy.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, BEFORE)
    engine = create_engine(url)
    with engine.begin() as db:  # the owner, user 1, is made by an earlier migration
        db.execute(
            text(
                "INSERT INTO settings (user_id, morning_time, nudge_time, protein_g, updated_at)"
                " VALUES (1, '07:30:00', '20:00:00', 150, '2026-11-01')"
            )
        )
    command.upgrade(cfg, AFTER)
    with engine.begin() as db:
        found = db.execute(text(f"SELECT protein_g, {COLUMNS} FROM settings")).all()  # noqa: S608 - constants
        assert found == [(150, 0, None, 0, 0, None)]
    for change in (
        "easy_start_weeks_light = 2, easy_start_weeks_lower = 1",
        "easy_start_weeks_light = -1",
        "easy_start_told = 'soon'",
    ):
        with pytest.raises(IntegrityError), engine.begin() as db:
            db.execute(text(f"UPDATE settings SET {change}"))  # noqa: S608 - constants
    with engine.begin() as db:
        db.execute(text("UPDATE settings SET easy_start = 1, easy_start_told = 'lower'"))
    command.downgrade(cfg, BEFORE)
    columns = {c["name"] for c in inspect(engine).get_columns("settings")}
    assert not {c for c in columns if c.startswith("easy_start")}
    with engine.begin() as db:
        assert db.execute(text("SELECT user_id, protein_g FROM settings")).all() == [(1, 150)]
    engine.dispose()
    get_settings.cache_clear()
