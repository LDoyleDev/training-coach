"""Plans per person (ADR-0073): the shared rows become the owner's with their ids, keys hold a
workout, a queue and a session in progress to the person's own plan, and anyone else stops it."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import Connection, Engine, create_engine, event, text
from sqlalchemy.exc import IntegrityError

from tests.db.test_migrations import BACKEND
from training_coach.config import get_settings

BEFORE = "c8d2e4f6a1b3"
AFTER = "b4e8d1f6a9c2"
PLAN_TABLES = ("session_templates", "template_items", "plan_versions")
SECOND_PERSON = (
    "INSERT INTO users (id, created_at, last_seen_in_europe)"
    " VALUES (2, '2026-11-01 07:00:00', '2026-11-01 07:00:00')"
)


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Config]:
    monkeypatch.setenv("TC_DATABASE_URL", f"sqlite:///{tmp_path / 'plans.db'}")
    get_settings.cache_clear()
    yield Config(str(BACKEND / "alembic.ini"))
    get_settings.cache_clear()


@pytest.fixture
def old(cfg: Config) -> Iterator[Engine]:
    """The shared plan, with what points at it: a workout, the queue and a session in progress."""
    command.upgrade(cfg, BEFORE)
    engine = create_engine(get_settings().database_url)
    with engine.begin() as db:
        for statement in (
            "INSERT INTO exercises (id, slug, name, kind, aliases)"
            " VALUES (1, 'x', 'X', 'reps', '[]')",
            "INSERT INTO session_templates (id, position, slug, name, focus)"
            " VALUES (7, 0, 'legs', 'Legs', 'Legs'), (8, 1, 'arms', 'Arms', 'Arms')",
            "INSERT INTO template_items (id, template_id, position, exercise_id, sets, rep_min,"
            " rep_max) VALUES (70, 7, 0, 1, 3, 8, 12)",
            "INSERT INTO plan_versions (id, since, name) VALUES (5, '2026-09-29', 'Original')",
            "INSERT INTO workouts (id, user_id, local_date, template_id, plan_version_id, status,"
            " created_at) VALUES (1, 1, '2026-11-02', 7, 5, 'done', '2026-11-02 07:00:00')",
            "INSERT INTO plan_state (user_id, next_template_id, queued, updated_at)"
            " VALUES (1, 8, '[7]', '2026-11-02 07:00:00')",
            "INSERT INTO session_progress (user_id, local_date, template_id, position, first,"
            " sets, token, revision, updated_at) VALUES (1, '2026-11-03', 8, 0, '[]', '[]',"
            " 'abababab', 1, '2026-11-03 07:00:00')",
        ):
            db.execute(text(statement))
    yield engine
    engine.dispose()


@pytest.fixture
def keys_on(old: Engine) -> Engine:
    """As the app runs: foreign keys checked."""

    @event.listens_for(old, "connect")
    def _on(connection: object, _record: object) -> None:
        connection.execute("PRAGMA foreign_keys=ON")  # type: ignore[attr-defined]  # a DBAPI connection

    old.dispose()
    return old


def _rows(db: Connection, statement: str) -> list[tuple[object, ...]]:
    return [tuple(row) for row in db.execute(text(statement))]


def test_the_owner_keeps_the_plan_and_every_id(cfg: Config, old: Engine) -> None:
    command.upgrade(cfg, AFTER)
    with old.begin() as db:
        assert _rows(db, "SELECT id, user_id FROM session_templates ORDER BY id") == [
            (7, 1),
            (8, 1),
        ]
        assert _rows(db, "SELECT id, user_id, template_id FROM template_items") == [(70, 1, 7)]
        assert _rows(db, "SELECT id, user_id FROM plan_versions") == [(5, 1)]
        assert _rows(db, "SELECT template_id, plan_version_id FROM workouts") == [(7, 5)]
        assert _rows(db, "SELECT next_template_id FROM plan_state") == [(8,)]
        assert _rows(db, "SELECT template_id FROM session_progress") == [(8,)]
        assert _rows(db, "PRAGMA foreign_key_check") == []


def test_anyone_else_stops_it_with_nothing_changed(cfg: Config, old: Engine) -> None:
    with old.begin() as db:
        db.execute(text(SECOND_PERSON))
    with pytest.raises((RuntimeError, CommandError), match="besides the owner"):
        command.upgrade(cfg, AFTER)
    with old.begin() as db:
        columns = [row[1] for row in _rows(db, "PRAGMA table_info(session_templates)")]
        assert "user_id" not in columns
        assert _rows(db, "SELECT version_num FROM alembic_version") == [(BEFORE,)]


def test_a_second_person_can_use_the_same_slugs_and_dates(cfg: Config, old: Engine) -> None:
    command.upgrade(cfg, AFTER)
    with old.begin() as db:
        db.execute(text(SECOND_PERSON))
        db.execute(
            text(
                "INSERT INTO session_templates (id, user_id, position, slug, name, focus)"
                " VALUES (9, 2, 0, 'legs', 'Legs', 'Legs')"
            )
        )
        db.execute(
            text(
                "INSERT INTO plan_versions (user_id, since, name) VALUES (2, '2026-09-29', 'Mine')"
            )
        )
    with pytest.raises(IntegrityError), old.begin() as db:
        db.execute(
            text(
                "INSERT INTO session_templates (user_id, position, slug, name, focus)"
                " VALUES (2, 1, 'legs', 'Legs', 'Legs')"
            )
        )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE workouts SET template_id = 9",
        "UPDATE plan_state SET next_template_id = 9",
        "UPDATE session_progress SET template_id = 9",
        "UPDATE workouts SET plan_version_id = 6",
        "INSERT INTO template_items (user_id, template_id, position, exercise_id, sets, rep_min,"
        " rep_max) VALUES (1, 9, 0, 1, 3, 8, 12)",
    ],
    ids=["workout", "queue", "in-progress", "version", "item"],
)
def test_nobody_can_point_at_someone_elses_plan(
    cfg: Config, keys_on: Engine, statement: str
) -> None:
    command.upgrade(cfg, AFTER)
    with keys_on.begin() as db:
        db.execute(text(SECOND_PERSON))
        db.execute(
            text(
                "INSERT INTO session_templates (id, user_id, position, slug, name, focus)"
                " VALUES (9, 2, 0, 'legs', 'Legs', 'Legs')"
            )
        )
        db.execute(
            text(
                "INSERT INTO plan_versions (id, user_id, since, name)"
                " VALUES (6, 2, '2026-09-29', 'Mine')"
            )
        )
    with pytest.raises(IntegrityError, match="FOREIGN KEY"), keys_on.begin() as db:
        db.execute(text(statement))


def test_a_downgrade_makes_the_owners_rows_the_shared_plan_again(cfg: Config, old: Engine) -> None:
    command.upgrade(cfg, AFTER)
    command.downgrade(cfg, BEFORE)
    with old.begin() as db:
        for table in PLAN_TABLES:
            assert "user_id" not in [row[1] for row in _rows(db, f"PRAGMA table_info({table})")]
        assert _rows(db, "SELECT id FROM session_templates ORDER BY id") == [(7,), (8,)]
        assert _rows(db, "SELECT template_id, plan_version_id FROM workouts") == [(7, 5)]
        assert _rows(db, "PRAGMA foreign_key_check") == []
    command.upgrade(cfg, AFTER)  # and back up again
    with old.begin() as db:
        assert _rows(db, "SELECT DISTINCT user_id FROM session_templates") == [(1,)]


def test_a_downgrade_refuses_while_someone_else_has_a_plan(cfg: Config, old: Engine) -> None:
    command.upgrade(cfg, AFTER)
    with old.begin() as db:
        db.execute(text(SECOND_PERSON))
        db.execute(
            text(
                "INSERT INTO session_templates (user_id, position, slug, name, focus)"
                " VALUES (2, 0, 'legs', 'Legs', 'Legs')"
            )
        )
    with pytest.raises((RuntimeError, CommandError), match="someone else's"):
        command.downgrade(cfg, BEFORE)
    with old.begin() as db:
        assert _rows(db, "SELECT version_num FROM alembic_version") == [(AFTER,)]
