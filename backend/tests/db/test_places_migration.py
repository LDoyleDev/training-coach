"""The places migration (ADR-0071): every workout so far was at home, and gym versions go back
out on a downgrade while the home ones stay."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from tests.db.test_migrations import BACKEND

BEFORE = "c3e8a1f5d9b2"  # the revision before places


def test_existing_workouts_and_items_are_home_and_a_downgrade_drops_only_gym_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import create_engine, text

    from training_coach.config import get_settings

    url = f"sqlite:///{tmp_path / 'places.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, BEFORE)
    engine = create_engine(url)
    item = (
        "INSERT INTO template_items (template_id, position, exercise_id, sets, rep_min, rep_max)"
        " VALUES (1, 0, 1, 3, 8, 12)"
    )
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO exercises (id, slug, name, kind, aliases)"
                " VALUES (1, 'x', 'X', 'reps', '[]')"
            )
        )
        db.execute(
            text(
                "INSERT INTO session_templates (id, position, slug, name, focus)"
                " VALUES (1, 0, 'legs', 'Legs', 'Legs')"
            )
        )
        db.execute(text(item))
        db.execute(
            text(
                "INSERT INTO workouts (user_id, local_date, status, created_at)"
                " VALUES (1, '2026-10-26', 'done', '2026-10-26 07:00:00')"
            )
        )
    command.upgrade(cfg, "head")
    with engine.begin() as db:
        assert db.execute(text("SELECT place FROM workouts")).scalars().all() == ["home"]
        assert db.execute(text("SELECT place FROM template_items")).scalars().all() == ["home"]
        places = db.execute(text("SELECT places, place FROM settings")).all()
        assert all(tuple(row) == ("home", "home") for row in places)
        # A gym version's first item shares position 0 with the home version's.
        db.execute(text(item.replace("rep_max)", "rep_max, place)").replace("12)", "12, 'gym')")))
    command.downgrade(cfg, BEFORE)
    with engine.begin() as db:
        assert db.execute(text("SELECT count(*) FROM template_items")).scalar_one() == 1
        assert db.execute(text("SELECT count(*) FROM workouts")).scalar_one() == 1
    engine.dispose()
    get_settings.cache_clear()
