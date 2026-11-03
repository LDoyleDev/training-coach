"""The away migration (ADR-0086): template items, workouts and progress take ``away``; the
place Today starts at doesn't; a downgrade drops the away versions and refuses while a
person's workout or progress was away."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from tests.db.test_migrations import BACKEND

BEFORE = "e5a7c9d1f3b4"  # the revision before away
ITEM = (
    "INSERT INTO template_items (template_id, position, exercise_id, sets, rep_min, rep_max,"
    " place) VALUES (1, 0, 1, 3, 8, 12, '{place}')"
)
WORKOUT = (
    "INSERT INTO workouts (user_id, local_date, status, created_at, place)"
    " VALUES (1, '2026-11-01', 'done', '2026-11-01 07:00:00', '{place}')"
)


def _upgraded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Config, Engine]:
    from training_coach.config import get_settings

    url = f"sqlite:///{tmp_path / 'away.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, "head")
    engine = create_engine(url)
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
        db.execute(text(ITEM.format(place="home")))
        db.execute(text(ITEM.format(place="away")))
    return cfg, engine


def test_away_rows_are_allowed_and_a_downgrade_drops_only_the_away_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from training_coach.config import get_settings

    cfg, engine = _upgraded(tmp_path, monkeypatch)
    with engine.begin() as db:
        db.execute(text(WORKOUT.format(place="home")))
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(text(ITEM.format(place="hotel").replace("0, 1, 3", "1, 1, 3")))
    command.downgrade(cfg, BEFORE)
    with engine.begin() as db:
        assert db.execute(text("SELECT place FROM template_items")).scalars().all() == ["home"]
        assert db.execute(text("SELECT count(*) FROM workouts")).scalar_one() == 1
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(text(ITEM.format(place="away")))
    command.upgrade(cfg, "head")  # and back up again
    engine.dispose()
    get_settings.cache_clear()


def test_the_place_today_starts_at_is_never_away(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from training_coach.config import get_settings

    _, engine = _upgraded(tmp_path, monkeypatch)
    with engine.begin() as db:
        found = text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :table")
        settings = db.execute(found, {"table": "settings"}).scalar_one()
        workouts = db.execute(found, {"table": "workouts"}).scalar_one()
    assert "place IN ('home', 'gym'))" in settings
    assert "place IN ('home', 'gym', 'away'))" in workouts
    engine.dispose()
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "held",
    [
        WORKOUT.format(place="away"),
        "INSERT INTO session_progress (user_id, local_date, template_id, position, first, sets,"
        " token, revision, updated_at, place) VALUES (1, '2026-11-01', 1, 0, '[]', '[]', 'ab', 1,"
        " '2026-11-01 07:00:00', 'away')",
    ],
    ids=["workout", "progress"],
)
def test_a_downgrade_refuses_while_a_persons_day_was_away(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, held: str
) -> None:
    from training_coach.config import get_settings

    cfg, engine = _upgraded(tmp_path, monkeypatch)
    with engine.begin() as db:
        db.execute(text(held))
    with pytest.raises(RuntimeError, match="done away"):
        command.downgrade(cfg, BEFORE)
    with engine.begin() as db:  # nothing went
        assert db.execute(text("SELECT count(*) FROM template_items")).scalar_one() == 2
    engine.dispose()
    get_settings.cache_clear()
