"""The reverse fly on dumbbells (ADR-0072, 4 Nov 2026): its "3 s lowering" step goes when nothing
uses it, the seed then renames the 8 kg step in place to the dumbbell step, and anything using
the step that would go stops the migration unchanged."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import Engine, create_engine, text

from tests.db.test_migrations import BACKEND
from training_coach.config import get_settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services.seed import apply_seed, load_plan

BEFORE = "f3a9c1d7e5b2"  # the revision before
# The ladder as it is on a database seeded before this change, ids as on no real one.
OLD = [
    "Chest on bench/bed, water bottles",
    "Chest on bench/bed, 8 kg one arm",
    "Chest-supported, 3 s lowering",
]
WATER, EIGHT, GONE = 100, 101, 102


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Config]:
    monkeypatch.setenv("TC_DATABASE_URL", f"sqlite:///{tmp_path / 'fly.db'}")
    get_settings.cache_clear()
    yield Config(str(BACKEND / "alembic.ini"))
    get_settings.cache_clear()


@pytest.fixture
def old(cfg: Config) -> Iterator[Engine]:
    """A database at the revision before (its owner, user 1, made by an earlier migration),
    with the old ladder and a workout."""
    command.upgrade(cfg, BEFORE)
    engine = create_engine(get_settings().database_url)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO exercises (id, slug, name, kind, aliases)"
                " VALUES (1, 'reverse-fly', 'Rear-delt reverse fly', 'reps', '[]')"
            )
        )
        for position, name in enumerate(OLD):
            db.execute(
                text(
                    "INSERT INTO ladder_steps (id, exercise_id, position, name)"
                    " VALUES (:id, 1, :position, :name)"
                ),
                {"id": WATER + position, "position": position, "name": name},
            )
        db.execute(
            text(
                "INSERT INTO workouts (id, user_id, local_date, status, created_at)"
                " VALUES (1, 1, '2026-11-02', 'done', '2026-11-02 07:00:00')"
            )
        )
    yield engine
    engine.dispose()


def _ladder(engine: Engine) -> list[str]:
    with engine.begin() as db:
        rows = db.execute(
            text(
                "SELECT s.name FROM ladder_steps s JOIN exercises e ON e.id = s.exercise_id"
                " WHERE e.slug = 'reverse-fly' ORDER BY s.position"
            )
        )
        return list(rows.scalars())


def test_the_top_step_goes_and_the_seed_renames_the_eight_kg_step(cfg: Config, old: Engine) -> None:
    with old.begin() as db:
        db.execute(
            text(
                "INSERT INTO set_logs (user_id, workout_id, exercise_id, ladder_step_id, set_no,"
                " value, side) VALUES (1, 1, 1, :step, 1, 15, 'both')"
            ),
            {"step": WATER},
        )
        db.execute(
            text(
                "INSERT INTO exercise_state (user_id, exercise_id, ladder_step_id, updated_at)"
                " VALUES (1, 1, :step, '2026-11-02 07:00:00')"
            ),
            {"step": WATER},
        )
    command.upgrade(cfg, "head")
    assert _ladder(old) == OLD[:2]
    with session_scope(make_session_factory(old)) as session:
        apply_seed(session, load_plan())
    assert _ladder(old) == [OLD[0], "Chest on bench/bed, dumbbells"]
    with old.begin() as db:
        ids = db.execute(
            text("SELECT id FROM ladder_steps WHERE exercise_id = 1 ORDER BY position")
        )
        assert list(ids.scalars()) == [WATER, EIGHT]  # the same steps, the 8 kg one renamed
        on = db.execute(text("SELECT ladder_step_id FROM exercise_state WHERE exercise_id = 1"))
        assert on.scalar_one() == WATER  # the level and the water-bottle sets stay put
        logged = db.execute(text("SELECT ladder_step_id FROM set_logs"))
        assert list(logged.scalars()) == [WATER]


def test_a_fresh_database_gets_the_two_steps_and_a_downgrade_puts_the_third_back(
    cfg: Config,
) -> None:
    command.upgrade(cfg, "head")
    engine = create_engine(get_settings().database_url)
    with session_scope(make_session_factory(engine)) as session:
        apply_seed(session, load_plan())
    assert _ladder(engine) == [OLD[0], "Chest on bench/bed, dumbbells"]
    command.downgrade(
        cfg, BEFORE
    )  # the 3 s step back on top, the 8 kg name as the old seed knew it
    assert _ladder(engine) == OLD
    with engine.begin() as db:
        level = db.execute(
            text("SELECT level FROM ladder_steps WHERE name = :name"), {"name": OLD[2]}
        )
        assert level.scalar_one() == 5
    command.upgrade(cfg, "head")
    assert _ladder(engine) == OLD[:2]
    engine.dispose()


Rows = list[tuple[str, dict[str, object]]]
TEMPLATE = (
    "INSERT INTO session_templates (id, position, slug, name, focus)"
    " VALUES (1, 0, 'torso', 'Torso', 'Torso')"
)
PROGRESS = (
    "INSERT INTO session_progress (user_id, local_date, template_id, position, first, sets,"
    " token, revision, steps, updated_at) VALUES (1, '2026-11-04', 1, 0, '[]', :sets, :token,"
    " 1, :steps, '2026-11-04 07:00:00')"
)


def _session_progress(steps: dict[str, int], sets: list[dict[str, int]]) -> Rows:
    values = {"sets": json.dumps(sets), "token": "ab" * 16, "steps": json.dumps(steps)}
    return [(TEMPLATE, {}), (PROGRESS, values)]


@pytest.mark.parametrize(
    "using",
    [
        [
            (
                "INSERT INTO set_logs (user_id, workout_id, exercise_id, ladder_step_id, set_no,"
                " value, side) VALUES (1, 1, 1, 102, 1, 12, 'both')",
                {},
            )
        ],
        [
            (
                "INSERT INTO exercise_state (user_id, exercise_id, ladder_step_id, updated_at)"
                " VALUES (1, 1, 102, '2026-11-02 07:00:00')",
                {},
            )
        ],
        _session_progress({"reverse-fly": GONE}, []),
        _session_progress({}, [{"item": 0, "set_no": 1, "left": 12, "step_id": GONE}]),
        [
            (
                "INSERT INTO replaced_workouts (user_id, local_date, data, created_at)"
                " VALUES (1, '2026-11-02', :data, '2026-11-02 07:00:00')",
                {"data": json.dumps({"sets": [[1, GONE, 1, "both", 12]]})},
            )
        ],
        [
            (
                "INSERT INTO events (user_id, at, kind, payload)"
                " VALUES (1, '2026-11-02 07:00:00', 'progress.level_set', :payload)",
                {"payload": json.dumps({"exercise": "reverse-fly", "to_step_id": GONE})},
            )
        ],
    ],
    ids=["set-log", "level", "today-level", "kept-set", "replaced-workout", "event"],
)
def test_the_step_that_would_go_in_use_stops_it_unchanged(
    cfg: Config, old: Engine, using: Rows
) -> None:
    with old.begin() as db:
        for statement, values in using:
            db.execute(text(statement), values)
    with pytest.raises((RuntimeError, CommandError), match="in use"):
        command.upgrade(cfg, "head")
    assert _ladder(old) == OLD


def test_an_unexpected_ladder_stops_it(cfg: Config, old: Engine) -> None:
    with old.begin() as db:
        db.execute(
            text("UPDATE ladder_steps SET name = 'Something else' WHERE id = :id"), {"id": EIGHT}
        )
    with pytest.raises((RuntimeError, CommandError), match="expected the ladder to end"):
        command.upgrade(cfg, "head")
    assert _ladder(old) == [OLD[0], "Something else", OLD[2]]
