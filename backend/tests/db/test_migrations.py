from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

BACKEND = Path(__file__).resolve().parents[2]


def test_migrations_upgrade_and_downgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from training_coach.config import get_settings

    monkeypatch.setenv("TC_DATABASE_URL", f"sqlite:///{tmp_path / 'm.db'}")
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    get_settings.cache_clear()


def test_batch_migrations_keep_logged_sets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite batch mode rebuilds a table by dropping it. With foreign keys on, that drop
    cascaded to set_logs and silently deleted every logged set (review of #52)."""
    from sqlalchemy import create_engine, text

    from training_coach.config import get_settings

    url = f"sqlite:///{tmp_path / 'keep.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, "8fa501cc9ce3")  # before workouts.log_token
    engine = create_engine(url)
    rows = [
        "INSERT INTO exercises (id, slug, name, kind, muscle_groups, aliases)"
        " VALUES (1, 'dip', 'Dip', 'reps', '[]', '[]')",
        "INSERT INTO ladder_steps (id, exercise_id, position, name) VALUES (1, 1, 0, 'Bars')",
        "INSERT INTO workouts (id, local_date, status, created_at)"
        " VALUES (1, '2026-10-01', 'done', '2026-10-01 07:00:00')",
        "INSERT INTO set_logs (workout_id, exercise_id, ladder_step_id, set_no, value, side)"
        " VALUES (1, 1, 1, 1, 10, 'both')",
    ]
    with engine.begin() as db:
        for row in rows:
            db.execute(text(row))

    def sets() -> int:
        with engine.connect() as db:
            return int(db.execute(text("SELECT count(*) FROM set_logs")).scalar_one())

    command.upgrade(cfg, "head")
    assert sets() == 1
    command.downgrade(cfg, "8fa501cc9ce3")
    assert sets() == 1
    engine.dispose()
    get_settings.cache_clear()


def test_a_migration_that_leaves_dangling_keys_is_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """foreign_key_check runs inside the migration's transaction, so a failure undoes it."""
    from sqlalchemy import create_engine, text

    from training_coach.config import get_settings

    url = f"sqlite:///{tmp_path / 'dangling.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, "head")
    engine = create_engine(url)  # plain engine: foreign keys off, so a dangling row can exist
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO set_logs (workout_id, exercise_id, ladder_step_id, set_no, value, side)"
                " VALUES (999, 999, 999, 1, 10, 'both')"
            )
        )
    with pytest.raises(RuntimeError, match="broken foreign keys"):
        command.downgrade(cfg, "-1")
    with engine.connect() as db:
        version = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        columns = [row[1] for row in db.execute(text("PRAGMA table_info(workouts)"))]
    assert version == "f58870988024"  # still at head: the downgrade was rolled back
    assert "log_token" in columns
    engine.dispose()
    get_settings.cache_clear()
