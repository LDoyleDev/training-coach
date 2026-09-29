"""Schema tests against the real migrated database (not metadata.create_all)."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from training_coach.config import get_settings
from training_coach.db.base import Base
from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    LadderStep,
    PlanState,
    SessionTemplate,
    SetLog,
    TemplateItem,
    UserSettings,
    Workout,
)
from training_coach.db.session import make_engine
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    url = f"sqlite:///{tmp_path / 'models.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    get_settings.cache_clear()
    eng = make_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


def _exercise(session: Session, slug: str = "pull-up") -> Exercise:
    exercise = Exercise(slug=slug, name="Pull-up", kind=ExerciseKind.REPS, muscle_groups=["back"])
    exercise.ladder = [
        LadderStep(position=0, name="Negatives"),
        LadderStep(position=1, name="Strict"),
    ]
    session.add(exercise)
    session.flush()
    return exercise


def _template(session: Session, exercise: Exercise, position: int = 0) -> SessionTemplate:
    template = SessionTemplate(position=position, slug=f"upper-{position}", name="Upper", focus="x")
    template.items = [
        TemplateItem(position=0, exercise_id=exercise.id, sets=4, rep_min=5, rep_max=12)
    ]
    session.add(template)
    session.flush()
    return template


def test_migration_matches_models(engine: Engine) -> None:
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_full_graph_round_trip(session: Session) -> None:
    exercise = _exercise(session)
    template = _template(session, exercise)
    session.add_all(
        [
            ExerciseState(exercise_id=exercise.id, ladder_step_id=exercise.ladder[1].id),
            PlanState(next_template_id=template.id),
            UserSettings(),
        ]
    )
    workout = Workout(local_date=date(2026, 9, 30), template_id=template.id, status="done")
    workout.sets = [
        SetLog(exercise_id=exercise.id, ladder_step_id=exercise.ladder[1].id, set_no=n, value=v)
        for n, v in enumerate([8, 7, 6, 5], start=1)
    ]
    session.add(workout)
    session.commit()

    assert [s.value for s in session.get_one(Workout, workout.id).sets] == [8, 7, 6, 5]
    assert [step.name for step in session.get_one(Exercise, exercise.id).ladder] == [
        "Negatives",
        "Strict",
    ]


def test_settings_defaults(session: Session) -> None:
    session.add(UserSettings())
    session.commit()
    settings = session.get_one(UserSettings, 1)
    assert settings.morning_time == time(7, 30)
    assert settings.nudge_time == time(20, 0)
    assert settings.nudges_enabled is True
    assert settings.paused is False


@pytest.mark.parametrize("model", [UserSettings, PlanState])
def test_single_row_tables_reject_second_row(
    session: Session, model: type[UserSettings] | type[PlanState]
) -> None:
    session.add(model(id=2))
    with pytest.raises(IntegrityError):
        session.commit()


def test_several_workouts_per_day_allowed(session: Session) -> None:
    exercise = _exercise(session)
    template = _template(session, exercise)
    day = date(2026, 9, 30)
    session.add_all(
        [
            Workout(local_date=day, template_id=template.id, status=WorkoutStatus.DONE),
            Workout(local_date=day, template_id=None, status=WorkoutStatus.DONE),
        ]
    )
    session.commit()
    count = session.scalar(
        select(func.count()).select_from(Workout).where(Workout.local_date == day)
    )
    assert count == 2


def test_deleting_workout_deletes_its_sets(session: Session) -> None:
    exercise = _exercise(session)
    workout = Workout(local_date=date(2026, 9, 30), status=WorkoutStatus.DONE)
    workout.sets = [
        SetLog(exercise_id=exercise.id, ladder_step_id=exercise.ladder[0].id, set_no=1, value=5)
    ]
    session.add(workout)
    session.commit()
    session.delete(workout)
    session.commit()
    assert session.scalar(select(func.count()).select_from(SetLog)) == 0


def test_exercise_in_use_cannot_be_deleted(session: Session) -> None:
    exercise = _exercise(session)
    _template(session, exercise)
    session.commit()
    session.delete(exercise)
    with pytest.raises(IntegrityError):
        session.commit()


def _bad_set(session: Session, **overrides: object) -> None:
    exercise = _exercise(session)
    workout = Workout(local_date=date(2026, 9, 30), status=WorkoutStatus.DONE)
    session.add(workout)
    session.flush()
    fields: dict[str, object] = {
        "workout_id": workout.id,
        "exercise_id": exercise.id,
        "ladder_step_id": exercise.ladder[0].id,
        "set_no": 1,
        "value": 5,
    }
    fields.update(overrides)
    session.add(SetLog(**fields))


@pytest.mark.parametrize(
    "overrides",
    [{"value": -1}, {"value": 3601}, {"set_no": 0}, {"side": "middle"}],
    ids=["negative", "too-large", "set-zero", "bad-side"],
)
def test_set_log_constraints(session: Session, overrides: dict[str, object]) -> None:
    _bad_set(session, **overrides)
    with pytest.raises(IntegrityError):
        session.commit()


def test_same_set_number_allowed_per_side(session: Session) -> None:
    exercise = _exercise(session)
    workout = Workout(local_date=date(2026, 9, 30), status=WorkoutStatus.DONE)
    step = exercise.ladder[0].id
    workout.sets = [
        SetLog(exercise_id=exercise.id, ladder_step_id=step, set_no=1, value=10, side=Side.LEFT),
        SetLog(exercise_id=exercise.id, ladder_step_id=step, set_no=1, value=9, side=Side.RIGHT),
    ]
    session.add(workout)
    session.commit()


def test_duplicate_set_rejected(session: Session) -> None:
    _bad_set(session, side=Side.LEFT)
    session.flush()
    first = session.scalars(select(SetLog)).one()
    session.add(
        SetLog(
            workout_id=first.workout_id,
            exercise_id=first.exercise_id,
            ladder_step_id=first.ladder_step_id,
            set_no=1,
            value=6,
            side=Side.LEFT,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_invalid_workout_status_rejected(session: Session) -> None:
    session.add(Workout(local_date=date(2026, 9, 30), status="maybe"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_invalid_exercise_kind_rejected(session: Session) -> None:
    session.add(Exercise(slug="x", name="X", kind="kilograms"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_ladder_position_rejected(session: Session) -> None:
    exercise = _exercise(session)
    session.add(LadderStep(exercise_id=exercise.id, position=0, name="Duplicate"))
    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize(
    ("rep_min", "rep_max", "sets"),
    [(10, 5, 3), (0, 5, 3), (5, 10, 0)],
    ids=["range", "min", "sets"],
)
def test_template_item_constraints(session: Session, rep_min: int, rep_max: int, sets: int) -> None:
    exercise = _exercise(session)
    template = SessionTemplate(position=0, slug="s", name="S", focus="x")
    template.items = [
        TemplateItem(
            position=0, exercise_id=exercise.id, sets=sets, rep_min=rep_min, rep_max=rep_max
        )
    ]
    session.add(template)
    with pytest.raises(IntegrityError):
        session.commit()


def test_timestamps_are_utc_aware(session: Session) -> None:
    session.add(Event(kind="test.event", payload={"ok": True}))
    session.commit()
    event = session.scalars(select(Event)).one()
    assert event.at.tzinfo is UTC


def test_naive_datetimes_rejected(session: Session) -> None:
    session.add(Event(kind="test.event", at=datetime(2026, 9, 30, 7, 30)))  # noqa: DTZ001
    with pytest.raises(StatementError, match="naive datetime"):
        session.commit()
