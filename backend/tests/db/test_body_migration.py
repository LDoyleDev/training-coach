"""The body protocol's migration (ADR-0076)."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from tests.db.test_migrations import BACKEND

BEFORE = "4aa795c75305"  # the revision before the body protocol


def test_body_protocol_keeps_measurements_and_refuses_to_lose_new_kinds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-0076: the kind check is rebuilt with the old rows in place; going back refuses
    while a neck or scale body-fat measurement would no longer fit the old check."""
    from sqlalchemy import create_engine, text

    from training_coach.config import get_settings

    url = f"sqlite:///{tmp_path / 'body.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, BEFORE)
    engine = create_engine(url)
    insert = (
        "INSERT INTO measurements (user_id, local_date, kind, tenths, created_at)"
        " VALUES (1, '2026-10-10', :kind, 850, '2026-10-10 07:00:00')"
    )
    with engine.begin() as db:
        db.execute(text(insert), {"kind": "waist"})
    command.upgrade(cfg, "head")
    with engine.begin() as db:
        db.execute(text(insert), {"kind": "neck"})
        found = db.execute(text("SELECT thigh_offset_cm, body_fat_estimate FROM settings"))
        assert all(tuple(row) == (15, "off") for row in found)
    with pytest.raises(RuntimeError, match="neck or scale body-fat measurements exist"):
        command.downgrade(cfg, BEFORE)
    with engine.begin() as db:
        db.execute(text("DELETE FROM measurements WHERE kind = 'neck'"))
    command.downgrade(cfg, BEFORE)
    with engine.connect() as db:
        assert db.execute(text("SELECT kind FROM measurements")).scalars().all() == ["waist"]
    engine.dispose()
    get_settings.cache_clear()
