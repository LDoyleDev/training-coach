"""Ladders down (ADR-0083, #508): migration 5ebed72122f7 puts easier steps below twelve ladders
and brings the goblet squat back as the Squat. Every step keeps its id, so levels, logged sets,
a session in progress, a replaced workout and events still point at the same step; it stops
before any write when the live ladders aren't as expected, and going back refuses once anything
uses a new step."""

import importlib.util
import json
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import Connection, Engine, create_engine, text

from tests.db.test_migrations import BACKEND
from training_coach.config import get_settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services.seed import PlanSeed, apply_seed, load_plan

BEFORE = "d4f9b2a6e8c1"
REVISION = "5ebed72122f7"


def _migration() -> ModuleType:
    path = next((BACKEND / "migrations" / "versions").glob(f"*{REVISION}*.py"))
    spec = importlib.util.spec_from_file_location("ladders_down", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _migration()
LADDERS: dict[str, tuple[tuple[str, ...], tuple[Any, ...]]] = MIGRATION.LADDERS


def _previous() -> PlanSeed:
    """The bundled plan as the release before had it: the old ladders and starts, the squat
    retired as the goblet squat."""
    plan = load_plan()
    exercises = []
    for seed in plan.exercises:
        if seed.slug not in LADDERS:
            exercises.append(seed)
            continue
        old, new = LADDERS[seed.slug]
        gone = {step.name for step in new} | {old[0]}  # the old first step asked nothing

        def kept(named: dict[str, Any], gone: set[str] = gone) -> dict[str, Any]:
            return {step: value for step, value in named.items() if step not in gone}

        update: dict[str, Any] = {
            "ladder": list(old),
            "start": seed.start - len(new),
            "cues": kept(seed.cues),
            "questions": kept(seed.questions),
            "needs": kept(seed.needs),
            "levels": {step: seed.levels[step] for step in old},
            "marks": {step: seed.marks[step] for step in old if step in seed.marks},
        }
        if seed.slug == MIGRATION.SQUAT:
            update |= {"name": "Goblet squat", "retired": True, "range": None, "summary": None}
        exercises.append(seed.model_copy(update=update))
    return plan.model_copy(update={"exercises": exercises})


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Config]:
    monkeypatch.setenv("TC_DATABASE_URL", f"sqlite:///{tmp_path / 'ladders.db'}")
    get_settings.cache_clear()
    yield Config(str(BACKEND / "alembic.ini"))
    get_settings.cache_clear()


def _seed(engine: Engine, plan: PlanSeed) -> Any:
    with session_scope(make_session_factory(engine)) as session:
        return apply_seed(session, plan)


def _step(db: Connection, slug: str, name: str) -> int:
    query = (
        "SELECT s.id FROM ladder_steps s JOIN exercises e ON e.id = s.exercise_id"
        " WHERE e.slug = :slug AND s.name = :name"
    )
    return int(db.execute(text(query), {"slug": slug, "name": name}).scalar_one())


def _exercise(db: Connection, slug: str) -> int:
    query = "SELECT id FROM exercises WHERE slug = :slug"
    return int(db.execute(text(query), {"slug": slug}).scalar_one())


# Levels at middle steps, and sets logged at several, as a person a few weeks in would have.
LEVELS = {
    "push-up": "Deficit",
    "pull-up": "Pause at top",
    "kb-curl": "8 kg, slow tempo",
    "goblet-squat": "1.5-rep squats, 8 kg",
}
LOGGED = [
    ("push-up", "Standard", 1),
    ("push-up", "Deficit", 2),
    ("pull-up", "Strict pull-up", 2),
    ("goblet-squat", "8 kg, 3 s lowering", 1),  # from before it was retired
    ("calf-raise", "Bodyweight on a step", 3),
    ("suitcase-carry", "8 kg", 3),
]


@pytest.fixture
def old(cfg: Config) -> Iterator[Engine]:
    """A database at the revision before, seeded with the release before's plan, with a person's
    levels, logged sets, a session in progress, a replaced workout and events."""
    command.upgrade(cfg, BEFORE)
    engine = create_engine(get_settings().database_url)
    _seed(engine, _previous())
    with engine.begin() as db:
        for slug, step in LEVELS.items():
            db.execute(
                text("UPDATE exercise_state SET ladder_step_id = :step WHERE exercise_id = :id"),
                {"step": _step(db, slug, step), "id": _exercise(db, slug)},
            )
        for workout in (1, 2, 3):
            db.execute(
                text(
                    "INSERT INTO workouts (id, user_id, local_date, status, created_at)"
                    " VALUES (:id, 1, :day, 'done', '2026-10-20 07:00:00')"
                ),
                {"id": workout, "day": f"2026-10-{20 + workout}"},
            )
        for n, (slug, step, workout) in enumerate(LOGGED, start=1):
            db.execute(
                text(
                    "INSERT INTO set_logs (user_id, workout_id, exercise_id, ladder_step_id,"
                    " set_no, value, side) VALUES (1, :workout, :exercise, :step, :n, 10, 'both')"
                ),
                {"workout": workout, "exercise": _exercise(db, slug)}
                | {"step": _step(db, slug, step), "n": n},
            )
        deficit, standard = _step(db, "push-up", "Deficit"), _step(db, "push-up", "Standard")
        torso = db.execute(text("SELECT id FROM session_templates WHERE slug = 'torso'"))
        db.execute(
            text(
                "INSERT INTO session_progress (user_id, local_date, template_id, position, first,"
                " sets, token, revision, steps, updated_at) VALUES (1, '2026-10-31', :template,"
                " 1, '[]', :sets, :token, 1, :steps, '2026-10-31 07:00:00')"
            ),
            {"template": torso.scalar_one(), "token": "ab" * 16}
            | {"steps": json.dumps({"push-up": standard})}
            | {"sets": json.dumps([{"item": 3, "set_no": 1, "left": 9, "step_id": deficit}])},
        )
        kept = {"sets": [[_exercise(db, "pull-up"), _step(db, "pull-up", "Slow negatives"), 1]]}
        db.execute(
            text(
                "INSERT INTO replaced_workouts (user_id, local_date, data, created_at)"
                " VALUES (1, '2026-10-29', :data, '2026-10-29 07:00:00')"
            ),
            {"data": json.dumps(kept)},
        )
        moved = {"exercise_id": _exercise(db, "push-up"), "from_step_id": standard}
        db.execute(
            text(
                "INSERT INTO events (user_id, at, kind, payload)"
                " VALUES (1, '2026-10-30 07:00:00', 'progress.moved_up', :payload)"
            ),
            {"payload": json.dumps(moved | {"to_step_id": deficit})},
        )
    yield engine
    engine.dispose()


def _steps(engine: Engine) -> dict[int, tuple[str, int, str, int | None, str]]:
    """Every step: id -> (exercise slug, position, name, level, marks)."""
    with engine.begin() as db:
        rows = db.execute(
            text(
                "SELECT s.id, e.slug, s.position, s.name, s.level, s.marks FROM ladder_steps s"
                " JOIN exercises e ON e.id = s.exercise_id"
            )
        )
        return {row[0]: (row[1], row[2], row[3], row[4], row[5]) for row in rows}


def _ladder(engine: Engine, slug: str) -> list[str]:
    return [name for s, _, name, _, _ in sorted(v for v in _steps(engine).values() if v[0] == slug)]


def _history(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    """Everything that points at a step, as stored."""
    tables = {
        "exercise_state": "SELECT user_id, exercise_id, ladder_step_id FROM exercise_state",
        "set_logs": "SELECT id, workout_id, exercise_id, ladder_step_id, value FROM set_logs",
        "session_progress": "SELECT id, steps, sets FROM session_progress",
        "replaced_workouts": "SELECT id, data FROM replaced_workouts",
        "events": "SELECT id, kind, payload FROM events WHERE kind != 'seed.applied'",
    }
    with engine.begin() as db:
        return {
            table: sorted(tuple(row) for row in db.execute(text(query)))
            for table, query in tables.items()
        }


def _squat(engine: Engine) -> tuple[str, bool]:
    with engine.begin() as db:
        row = db.execute(text("SELECT name, retired FROM exercises WHERE slug = 'goblet-squat'"))
        name, retired = row.one()
        return name, bool(retired)


def test_the_steps_move_up_keeping_their_ids_and_everything_that_points_at_them(
    cfg: Config, old: Engine
) -> None:
    before, history = _steps(old), _history(old)
    assert all(history.values())  # something of each kind points at a step
    assert len(history["set_logs"]) == len(LOGGED)
    assert _squat(old) == ("Goblet squat", True)
    command.upgrade(cfg, REVISION)
    after = _steps(old)
    shift = {slug: len(new) for slug, (_, new) in LADDERS.items()}
    for step_id, (slug, position, name, level, marks) in before.items():
        moved = position + shift.get(slug, 0)
        assert after[step_id] == (slug, moved, name, level, marks), (slug, name)
    added = {i: v for i, v in after.items() if i not in before}
    for slug, (old_names, new) in LADDERS.items():
        mine = sorted(v[1:] for v in added.values() if v[0] == slug)
        assert mine == [
            (n, s.name, s.level, json.dumps(list(s.marks))) for n, s in enumerate(new)
        ], slug
        assert _ladder(old, slug) == [s.name for s in new] + list(old_names)
    assert _history(old) == history  # levels, sets, kept sets, replaced workouts, events
    assert _squat(old) == ("Squat", False)

    # The seed then finds every step where the plan has it: nothing added, nothing moved.
    seeded = _seed(old, load_plan())
    assert seeded.created == 0
    assert {i: v[:3] for i, v in _steps(old).items()} == {i: v[:3] for i, v in after.items()}
    assert _history(old) == history
    assert not _seed(old, load_plan()).changed

    command.downgrade(cfg, BEFORE)  # nothing uses a new step yet: they go, the rest move back
    assert {i: v[:3] for i, v in _steps(old).items()} == {i: v[:3] for i, v in before.items()}
    assert _history(old) == history
    assert _squat(old) == ("Goblet squat", True)


def test_the_plan_has_the_steps_the_migration_writes() -> None:
    """The seed matches by position, so plan.toml's ladder is the new steps, then the old."""
    plan = {e.slug: e for e in load_plan().exercises}
    previous = {e.slug: e for e in _previous().exercises}
    for slug, (old, new) in LADDERS.items():
        seed = plan[slug]
        assert seed.ladder == [s.name for s in new] + list(old), slug
        assert [(seed.levels[s.name], tuple(seed.marks.get(s.name, []))) for s in new] == [
            (s.level, s.marks) for s in new
        ], slug
        # start names the same step as before (ADR-0083: the migration moves start)
        assert seed.ladder[seed.start] == previous[slug].ladder[previous[slug].start], slug
    assert (plan[MIGRATION.SQUAT].name, plan[MIGRATION.SQUAT].retired) == ("Squat", False)


def test_a_ladder_not_as_expected_stops_it_before_any_write(cfg: Config, old: Engine) -> None:
    with old.begin() as db:
        db.execute(text("UPDATE ladder_steps SET name = 'Wall' WHERE id = :id"),
                   {"id": _step(db, "zone2", "Easy jog / bike")})  # fmt: skip
    before = _steps(old)
    with pytest.raises((RuntimeError, CommandError), match=r"zone2: expected .* found"):
        command.upgrade(cfg, "head")
    assert _steps(old) == before
    assert _squat(old) == ("Goblet squat", True)


def test_a_squat_not_retired_stops_it_before_any_write(cfg: Config, old: Engine) -> None:
    with old.begin() as db:
        db.execute(text("UPDATE exercises SET retired = 0 WHERE slug = 'goblet-squat'"))
    before = _steps(old)
    with pytest.raises((RuntimeError, CommandError), match="goblet-squat: expected the retired"):
        command.upgrade(cfg, "head")
    assert _steps(old) == before


def test_a_fresh_database_gets_the_whole_ladders_from_the_seed(cfg: Config) -> None:
    command.upgrade(cfg, "head")
    engine = create_engine(get_settings().database_url)
    _seed(engine, load_plan())
    _, new = LADDERS["push-up"]
    assert _ladder(engine, "push-up")[: len(new)] == [s.name for s in new]
    command.downgrade(cfg, BEFORE)
    assert _ladder(engine, "push-up") == list(LADDERS["push-up"][0])
    command.upgrade(cfg, "head")
    assert _ladder(engine, "push-up")[: len(new)] == [s.name for s in new]
    engine.dispose()


Using = list[tuple[str, dict[str, object]]]


def _uses(kind: str, step: int, exercise: int) -> Using:
    if kind == "set-log":
        return [
            (
                "INSERT INTO set_logs (user_id, workout_id, exercise_id, ladder_step_id, set_no,"
                " value, side) VALUES (1, 3, :exercise, :step, 9, 5, 'both')",
                {"exercise": exercise, "step": step},
            )
        ]
    if kind == "level":
        return [
            (
                "UPDATE exercise_state SET ladder_step_id = :step WHERE exercise_id = :exercise",
                {"exercise": exercise, "step": step},
            )
        ]
    if kind == "today-level":
        steps = json.dumps({"push-up": step})
        return [("UPDATE session_progress SET steps = :steps", {"steps": steps})]
    if kind == "kept-set":
        sets = json.dumps([{"item": 3, "set_no": 2, "left": 5, "step_id": step}])
        return [("UPDATE session_progress SET sets = :sets", {"sets": sets})]
    if kind == "replaced-workout":
        data = {"sets": [[exercise, step, 1, "both", 5]]}
        return [("UPDATE replaced_workouts SET data = :data", {"data": json.dumps(data)})]
    payload = {"exercise_id": exercise, "step_id": step}
    return [
        (
            "INSERT INTO events (user_id, at, kind, payload)"
            " VALUES (1, '2026-11-01 07:00:00', 'progress.not_yet', :payload)",
            {"payload": json.dumps(payload)},
        )
    ]


@pytest.mark.parametrize(
    "kind", ["set-log", "level", "today-level", "kept-set", "replaced-workout", "event"]
)
def test_going_back_refuses_once_a_new_step_is_used(cfg: Config, old: Engine, kind: str) -> None:
    command.upgrade(cfg, REVISION)
    with old.begin() as db:
        wall = _step(db, "push-up", "Hands on a wall")
        for statement, values in _uses(kind, wall, _exercise(db, "push-up")):
            db.execute(text(statement), values)
    before = _steps(old)
    with pytest.raises((RuntimeError, CommandError), match="restore the pre-deploy backup"):
        command.downgrade(cfg, BEFORE)
    assert _steps(old) == before
    assert _squat(old) == ("Squat", False)


def test_going_back_stops_when_a_ladder_is_not_as_it_left_it(cfg: Config, old: Engine) -> None:
    command.upgrade(cfg, REVISION)
    with old.begin() as db:
        db.execute(text("UPDATE ladder_steps SET name = 'Elsewhere' WHERE id = :id"),
                   {"id": _step(db, "kb-curl", "A bag, 2-4 kg")})  # fmt: skip
    before = _steps(old)
    with pytest.raises((RuntimeError, CommandError), match="kb-curl: expected"):
        command.downgrade(cfg, BEFORE)
    assert _steps(old) == before
