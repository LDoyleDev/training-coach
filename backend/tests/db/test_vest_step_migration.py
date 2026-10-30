"""The one-vest-step migration (ADR-0072, 29 Oct 2026): the pull-up's and chin-up's 10 and 15 kg
vest steps go when nothing uses them, sets at the 5 kg step get 5 kg, the seed then renames
that step in place, and anything using a step that would go stops the migration unchanged."""

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

BEFORE = "a4d8f2c6e9b1"  # the revision before
# The ladders as they are on a database seeded before this change, ids as on no real one.
OLD = {
    "pull-up": [
        "Slow negatives",
        "Strict pull-up",
        "Pause at top",
        "Vest or backpack, 5 kg",
        "Vest or backpack, 10 kg",
        "Vest or backpack, 15 kg",
    ],
    "chin-up": [
        "Strict",
        "3 s lowering",
        "Vest or backpack, 5 kg",
        "Vest or backpack, 10 kg",
        "Vest or backpack, 15 kg",
    ],
}


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Config]:
    monkeypatch.setenv("TC_DATABASE_URL", f"sqlite:///{tmp_path / 'vest.db'}")
    get_settings.cache_clear()
    yield Config(str(BACKEND / "alembic.ini"))
    get_settings.cache_clear()


@pytest.fixture
def old(cfg: Config) -> Iterator[Engine]:
    """A database at the revision before (its owner, user 1, made by an earlier migration),
    with the old ladders and a workout."""
    command.upgrade(cfg, BEFORE)
    engine = create_engine(get_settings().database_url)
    with engine.begin() as db:
        for exercise_id, (slug, ladder) in enumerate(OLD.items(), start=1):
            db.execute(
                text(
                    "INSERT INTO exercises (id, slug, name, kind, aliases)"
                    " VALUES (:id, :slug, :slug, 'reps', '[]')"
                ),
                {"id": exercise_id, "slug": slug},
            )
            for position, name in enumerate(ladder):
                db.execute(
                    text(
                        "INSERT INTO ladder_steps (id, exercise_id, position, name)"
                        " VALUES (:id, :exercise, :position, :name)"
                    ),
                    {"id": exercise_id * 100 + position, "exercise": exercise_id}
                    | {"position": position, "name": name},
                )
        db.execute(
            text(
                "INSERT INTO workouts (id, user_id, local_date, status, created_at)"
                " VALUES (1, 1, '2026-10-20', 'done', '2026-10-20 07:00:00')"
            )
        )
    yield engine
    engine.dispose()


def _ladder(engine: Engine, slug: str) -> list[str]:
    with engine.begin() as db:
        rows = db.execute(
            text(
                "SELECT s.name FROM ladder_steps s JOIN exercises e ON e.id = s.exercise_id"
                " WHERE e.slug = :slug ORDER BY s.position"
            ),
            {"slug": slug},
        )
        return list(rows.scalars())


def _set(engine: Engine, step_id: int, load_kg: float | None = None) -> None:
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO set_logs (user_id, workout_id, exercise_id, ladder_step_id, set_no,"
                " value, side, load_kg) VALUES (1, 1, :exercise, :step, :n, 8, 'both', :kg)"
            ),
            {"exercise": step_id // 100, "step": step_id, "n": step_id % 100 + 1, "kg": load_kg},
        )


def test_the_two_steps_go_and_the_seed_renames_the_five_kg_step(cfg: Config, old: Engine) -> None:
    _set(old, 103)  # a pull-up set at the 5 kg step, no weight
    _set(old, 202, 7.5)  # a chin-up set there with one
    with old.begin() as db:
        db.execute(
            text(
                "INSERT INTO exercise_state (user_id, exercise_id, ladder_step_id, updated_at)"
                " VALUES (1, 1, 103, '2026-10-20 07:00:00')"
            )
        )
    command.upgrade(cfg, "head")
    assert _ladder(old, "pull-up") == OLD["pull-up"][:4]
    assert _ladder(old, "chin-up") == OLD["chin-up"][:3]
    with old.begin() as db:
        loads = db.execute(text("SELECT ladder_step_id, load_kg FROM set_logs ORDER BY id"))
        assert [tuple(row) for row in loads] == [(103, 5.0), (202, 7.5)]
    with session_scope(make_session_factory(old)) as session:
        apply_seed(session, load_plan())
    assert _ladder(old, "pull-up")[-1] == _ladder(old, "chin-up")[-1] == "Vest or backpack"
    with old.begin() as db:
        on = db.execute(text("SELECT ladder_step_id FROM exercise_state WHERE exercise_id = 1"))
        assert on.scalar_one() == 103  # the same step, under its new name


def test_a_fresh_database_gets_the_one_step_from_the_seed(cfg: Config) -> None:
    command.upgrade(cfg, "head")
    engine = create_engine(get_settings().database_url)
    with session_scope(make_session_factory(engine)) as session:
        apply_seed(session, load_plan())
    assert _ladder(engine, "chin-up") == ["Strict", "3 s lowering", "Vest or backpack"]
    command.downgrade(cfg, BEFORE)  # puts the 10 and 15 kg steps back, as the old seed knew it
    assert _ladder(engine, "chin-up") == OLD["chin-up"]
    command.upgrade(cfg, "head")
    assert _ladder(engine, "chin-up") == OLD["chin-up"][:3]
    engine.dispose()


Rows = list[tuple[str, dict[str, object]]]
TEMPLATE = (
    "INSERT INTO session_templates (id, position, slug, name, focus)"
    " VALUES (1, 0, 'torso', 'Torso', 'Torso')"
)
PROGRESS = (
    "INSERT INTO session_progress (user_id, local_date, template_id, position, first, sets,"
    " token, revision, steps, updated_at) VALUES (1, '2026-10-29', 1, 0, '[]', :sets, :token,"
    " 1, :steps, '2026-10-29 07:00:00')"
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
                " value, side) VALUES (1, 1, 1, 104, 2, 8, 'both')",
                {},
            )
        ],
        [
            (
                "INSERT INTO exercise_state (user_id, exercise_id, ladder_step_id, updated_at)"
                " VALUES (1, 2, 204, '2026-10-20 07:00:00')",
                {},
            )
        ],
        _session_progress({"pull-up": 105}, []),
        _session_progress({}, [{"item": 0, "set_no": 1, "left": 8, "step_id": 104}]),
        [
            (
                "INSERT INTO replaced_workouts (user_id, local_date, data, created_at)"
                " VALUES (1, '2026-10-29', :data, '2026-10-29 07:00:00')",
                {"data": json.dumps({"sets": [[2, 203, 1, "both", 8]]})},
            )
        ],
    ],
    ids=["set-log", "level", "today-level", "kept-set", "replaced-workout"],
)
def test_a_step_that_would_go_and_is_used_stops_it_unchanged(
    cfg: Config, old: Engine, using: Rows
) -> None:
    _set(old, 103)  # at the 5 kg step, no weight: still none after the refusal
    with old.begin() as db:
        for statement, values in using:
            db.execute(text(statement), values)
    with pytest.raises((RuntimeError, CommandError), match="in use"):
        command.upgrade(cfg, "head")
    assert _ladder(old, "pull-up") == OLD["pull-up"]
    with old.begin() as db:
        assert db.execute(text("SELECT load_kg FROM set_logs WHERE id = 1")).scalar_one() is None
