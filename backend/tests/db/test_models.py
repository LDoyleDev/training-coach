"""Schema tests against the real migrated database (not metadata.create_all)."""

from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, func, insert, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from tests import factories
from training_coach.db.base import Base
from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    LadderStep,
    PlanState,
    SessionProgress,
    SessionTemplate,
    SetLog,
    TemplateItem,
    UserSettings,
    Workout,
)
from training_coach.domain.enums import Place, Side, WorkoutStatus

BACKEND = Path(__file__).resolve().parents[2]


def test_migration_matches_models(engine: Engine) -> None:
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_full_graph_round_trip(session: Session) -> None:
    exercise = factories.exercise(session)
    template = factories.template(session, exercise)
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
def test_one_settings_and_plan_row_per_user(
    session: Session, model: type[UserSettings] | type[PlanState]
) -> None:
    """ADR-0026: what used to be single-row tables hold one row per person."""
    session.add(model())
    session.commit()
    session.add(model())
    with pytest.raises(IntegrityError):
        session.commit()


def test_session_progress_place_is_home_or_gym(session: Session) -> None:
    """ADR-0071: kept progress records where its sets were done, home unless set."""
    exercise = factories.exercise(session)
    template = factories.template(session, exercise)
    session.add(
        SessionProgress(local_date=date(2026, 10, 28), template_id=template.id, token="ab" * 16)
    )
    session.commit()
    assert session.execute(text("SELECT place FROM session_progress")).scalar_one() == "home"
    with pytest.raises(IntegrityError):
        session.execute(text("UPDATE session_progress SET place = 'office'"))


def test_a_step_level_is_empty_or_1_to_6_and_marks_start_empty(session: Session) -> None:
    """ADR-0083: the seed writes both; a step written before it runs has none."""
    exercise = factories.exercise(session)
    session.commit()
    assert session.execute(text("SELECT level, marks FROM ladder_steps")).first() == (None, "[]")
    assert exercise.failure_ok is False
    session.execute(text("UPDATE ladder_steps SET level = 6"))
    for level in (0, 7):
        with pytest.raises(IntegrityError):
            session.execute(text("UPDATE ladder_steps SET level = :level"), {"level": level})


@pytest.mark.parametrize("kit", ["barbell", "dumbbells", "machine"])
def test_an_own_weight_step_is_empty_or_in_range(session: Session, kit: str) -> None:
    """ADR-0072: empty keeps the default; a step of their own is 0.25 to 20 kg."""
    session.add(UserSettings())
    session.commit()
    row = session.get_one(UserSettings, 1)
    column = f"{kit}_increment_kg"
    assert getattr(row, column) is None
    setattr(row, column, 1.25)
    session.commit()
    for bad in (0.0, 20.5):
        setattr(row, column, bad)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_several_workouts_per_day_allowed(session: Session) -> None:
    exercise = factories.exercise(session)
    template = factories.template(session, exercise)
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
    exercise = factories.exercise(session)
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
    exercise = factories.exercise(session)
    factories.template(session, exercise)
    session.commit()
    session.delete(exercise)
    with pytest.raises(IntegrityError):
        session.commit()


def _bad_set(session: Session, **overrides: object) -> None:
    exercise = factories.exercise(session)
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
    exercise = factories.exercise(session)
    workout = Workout(local_date=date(2026, 9, 30), status=WorkoutStatus.DONE)
    step = exercise.ladder[0].id
    workout.sets = [
        SetLog(exercise_id=exercise.id, ladder_step_id=step, set_no=1, value=10, side=Side.LEFT),
        SetLog(exercise_id=exercise.id, ladder_step_id=step, set_no=1, value=9, side=Side.RIGHT),
    ]
    session.add(workout)
    session.commit()


@pytest.mark.parametrize("side", [Side.BOTH, Side.LEFT])
def test_duplicate_set_rejected(session: Session, side: Side) -> None:
    _bad_set(session, side=side)
    session.flush()
    first = session.scalars(select(SetLog)).one()
    session.add(
        SetLog(
            workout_id=first.workout_id,
            exercise_id=first.exercise_id,
            ladder_step_id=first.ladder_step_id,
            set_no=1,
            value=6,
            side=side,
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
    exercise = factories.exercise(session)
    session.add(LadderStep(exercise_id=exercise.id, position=0, name="Duplicate"))
    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize(
    ("rep_min", "rep_max", "sets"),
    [(10, 5, 3), (0, 5, 3), (5, 10, 0)],
    ids=["range", "min", "sets"],
)
def test_template_item_constraints(session: Session, rep_min: int, rep_max: int, sets: int) -> None:
    exercise = factories.exercise(session)
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


def test_side_defaults_to_both(session: Session) -> None:
    _bad_set(session)
    session.commit()
    assert session.scalars(select(SetLog)).one().side == Side.BOTH


def test_set_ladder_step_must_belong_to_exercise(session: Session) -> None:
    pull_up = factories.exercise(session, "pull-up")
    dip = factories.exercise(session, "dip")
    workout = Workout(local_date=date(2026, 9, 30), status=WorkoutStatus.DONE)
    workout.sets = [
        SetLog(exercise_id=pull_up.id, ladder_step_id=dip.ladder[0].id, set_no=1, value=5)
    ]
    session.add(workout)
    with pytest.raises(IntegrityError):
        session.commit()


def test_exercise_state_step_must_belong_to_exercise(session: Session) -> None:
    pull_up = factories.exercise(session, "pull-up")
    dip = factories.exercise(session, "dip")
    session.add(ExerciseState(exercise_id=pull_up.id, ladder_step_id=dip.ladder[0].id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_migration_does_not_import_application_code() -> None:
    for migration in (BACKEND / "migrations" / "versions").glob("*.py"):
        assert "training_coach" not in migration.read_text(encoding="utf-8"), migration.name


def test_null_side_rejected_by_database(session: Session) -> None:
    _bad_set(session)
    session.flush()
    first = session.scalars(select(SetLog)).one()
    with pytest.raises(IntegrityError):
        session.execute(  # a plain table insert: the database itself must refuse it
            insert(SetLog.__table__).values(
                user_id=first.user_id,
                workout_id=first.workout_id,
                exercise_id=first.exercise_id,
                ladder_step_id=first.ladder_step_id,
                set_no=2,
                value=5,
                side=None,
            )
        )


def test_log_token_is_unique_but_may_repeat_as_null(session: Session) -> None:
    """Idempotent saves rely on the database refusing a second workout per token (#52)."""
    from datetime import date

    from sqlalchemy.exc import IntegrityError

    from training_coach.db.models import Workout

    day = date(2026, 10, 1)
    session.add_all(
        [
            Workout(local_date=day, status=WorkoutStatus.REST),
            Workout(local_date=day, status=WorkoutStatus.REST),
        ]
    )
    session.flush()  # several NULL tokens are fine
    session.add(Workout(local_date=day, status=WorkoutStatus.DONE, log_token="a" * 32))
    session.flush()
    session.add(Workout(local_date=day, status=WorkoutStatus.DONE, log_token="a" * 32))
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_session_keeps_its_home_and_gym_versions_apart(session: Session) -> None:
    """ADR-0071: each version numbers its own items; ``items`` is the home version, and the gym
    is done as at home when the session has no gym version."""
    exercise = factories.exercise(session)
    template = factories.template(session, exercise)
    home = template.items[0]
    assert template.version(Place.GYM) == [home]  # no gym version yet
    template.gym_items.append(
        TemplateItem(position=0, exercise_id=exercise.id, sets=3, rep_min=6, rep_max=10)
    )
    session.flush()
    session.expire_all()
    assert [i.place for i in template.items] == ["home"]
    assert [(i.place, i.rep_max) for i in template.gym_items] == [("gym", 10)]
    assert template.version(Place.HOME) == template.items
    assert template.version(Place.GYM) == template.gym_items
    session.add(
        TemplateItem(
            template_id=template.id,
            position=0,
            place="gym",
            exercise_id=exercise.id,
            sets=3,
            rep_min=6,
            rep_max=10,
        )
    )
    with pytest.raises(IntegrityError):  # one item a position, within each version
        session.flush()
