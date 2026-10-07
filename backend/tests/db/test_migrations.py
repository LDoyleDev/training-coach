from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

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
                "INSERT INTO set_logs"
                " (workout_id, exercise_id, ladder_step_id, set_no, value, side)"
                " VALUES (999, 999, 999, 1, 10, 'both')"
            )
        )
    with pytest.raises(RuntimeError, match="broken foreign keys"):
        command.downgrade(cfg, "-1")
    with engine.connect() as db:
        version = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        columns = [row[1] for row in db.execute(text("PRAGMA table_info(workouts)"))]
    head = ScriptDirectory.from_config(cfg).get_current_head()
    assert version == head  # still at head: the downgrade was rolled back
    assert "user_id" in columns  # added by the head migration, so it wasn't undone
    engine.dispose()
    get_settings.cache_clear()


def test_users_migration_gives_everything_to_the_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-0026: existing personal rows become user 1's, nothing is lost, and the seed's own
    event belongs to no one. Downgrading keeps the owner's rows."""
    from sqlalchemy import create_engine, text

    from training_coach.config import get_settings

    url = f"sqlite:///{tmp_path / 'users.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, "f58870988024")  # before users
    engine = create_engine(url)
    rows = [
        "INSERT INTO exercises (id, slug, name, kind, muscle_groups, aliases)"
        " VALUES (1, 'dip', 'Dip', 'reps', '[]', '[]')",
        "INSERT INTO ladder_steps (id, exercise_id, position, name) VALUES (1, 1, 0, 'Bars')",
        "INSERT INTO session_templates (id, position, slug, name, focus, is_rest_optional)"
        " VALUES (1, 0, 'torso', 'Torso', 'x', 0)",
        "INSERT INTO exercise_state (exercise_id, ladder_step_id, updated_at)"
        " VALUES (1, 1, '2026-10-01 07:00:00')",
        "INSERT INTO plan_state (id, next_template_id, queued, updated_at)"
        " VALUES (1, 1, '[]', '2026-10-01 07:00:00')",
        "INSERT INTO settings (id, morning_time, nudge_time, nudges_enabled, paused, updated_at)"
        " VALUES (1, '07:30:00', '20:00:00', 1, 0, '2026-10-01 07:00:00')",
        "INSERT INTO workouts (id, local_date, status, created_at, log_token)"
        " VALUES (1, '2026-10-01', 'done', '2026-10-01 07:00:00', 'token')",
        "INSERT INTO set_logs (workout_id, exercise_id, ladder_step_id, set_no, value, side)"
        " VALUES (1, 1, 1, 1, 10, 'both')",
        "INSERT INTO events (at, kind, payload)"
        " VALUES ('2026-10-01 07:00:00', 'seed.applied', '{}')",
        "INSERT INTO events (at, kind, payload)"
        " VALUES ('2026-10-01 08:00:00', 'workout.logged', '{}')",
    ]
    with engine.begin() as db:
        for row in rows:
            db.execute(text(row))

    command.upgrade(cfg, "head")
    with engine.connect() as db:
        assert db.execute(text("SELECT id FROM users")).scalars().all() == [1]
        for table in ("workouts", "exercise_state", "plan_state", "settings"):
            owners = db.execute(text(f"SELECT user_id FROM {table}")).scalars().all()  # noqa: S608
            assert owners == [1], table
        events = db.execute(text("SELECT kind, user_id FROM events ORDER BY id")).all()
        assert [tuple(e) for e in events] == [("seed.applied", None), ("workout.logged", 1)]
        assert db.execute(text("SELECT count(*) FROM set_logs")).scalar_one() == 1
        # No default owner is left behind: a new row must name its user.
        with pytest.raises(Exception, match="NOT NULL"):
            db.execute(
                text(
                    "INSERT INTO workouts (local_date, status, created_at)"
                    " VALUES ('2026-10-02', 'done', '2026-10-02 07:00:00')"
                )
            )

    command.downgrade(cfg, "f58870988024")
    with engine.connect() as db:
        for table in ("workouts", "exercise_state", "plan_state", "settings", "set_logs"):
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 1, table  # noqa: S608
    engine.dispose()
    get_settings.cache_clear()
