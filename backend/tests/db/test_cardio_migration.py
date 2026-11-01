"""The counted walks' data migration (ADR-0079): only sets the old Count it rule logged change."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, insert, select, text

from tests.db.test_migrations import BACKEND
from training_coach.db.models import ImportedWorkout, SetLog, Workout
from training_coach.db.session import make_session_factory
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus
from training_coach.services.users import OWNER

BEFORE = "a7d4c2e9f1b3"  # extra cardio
MONDAY = date(2026, 10, 26)


def test_only_a_walk_the_old_rule_logged_gets_its_full_minutes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Monday's walk (35 of 66 logged) becomes 66. A walk already logged in full, one the person
    edited, a moderate run and one whose zones 3-5 won stay as they are; going back restores
    the 35."""
    from training_coach.config import get_settings

    url = f"sqlite:///{tmp_path / 'walks.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, BEFORE)
    engine = create_engine(url)
    with make_session_factory(engine, user_id=OWNER)() as session:
        steps = {}
        # Plain SQL, not the ORM: the schema at BEFORE has none of the columns added since,
        # such as the steps' levels (ADR-0083).
        for slug in ("zone2", "moderate-cardio"):
            exercise_id = session.execute(
                text(
                    "INSERT INTO exercises (slug, name, kind, aliases)"
                    " VALUES (:slug, :slug, :kind, '[]') RETURNING id"
                ),
                {"slug": slug, "kind": ExerciseKind.DURATION_MIN.value},
            ).scalar_one()
            step_id = session.execute(
                text(
                    "INSERT INTO ladder_steps (exercise_id, position, name)"
                    " VALUES (:exercise, 0, 'Walk') RETURNING id"
                ),
                {"exercise": exercise_id},
            ).scalar_one()
            steps[slug] = (exercise_id, step_id)

        def counted(day: int, slug: str, logged: int, zones: tuple[int, ...]) -> int:
            on = MONDAY - timedelta(days=day)
            exercise_id, step_id = steps[slug]
            # Core, not the ORM, for the workout and its set (whose flush loads the workout): the
            # schema at BEFORE has no `workouts.place` (ADR-0071).
            workouts = Workout.__table__
            workout_id = session.execute(
                insert(workouts)
                .values(user_id=OWNER, local_date=on, status=WorkoutStatus.DONE, activity="walk")
                .returning(workouts.c.id)
            ).scalar_one()
            session.execute(
                insert(SetLog.__table__).values(
                    user_id=OWNER,
                    workout_id=workout_id,
                    exercise_id=exercise_id,
                    ladder_step_id=step_id,
                    set_no=1,
                    side=Side.BOTH,
                    value=logged,
                )
            )
            start = datetime(2026, 10, 26 - day, 6, 0, tzinfo=UTC)
            band = ImportedWorkout(
                source="com.mi.health",
                start_at=start,
                end_at=start + timedelta(minutes=66),
                local_date=on,
                exercise_type=79,
                activity="walk",
                minutes=66,
                status="counted",
                workout_id=workout_id,
            )
            band.zone1_min, band.zone2_min, band.zone3_min, band.zone4_min, band.zone5_min = zones
            session.add(band)
            session.flush()
            return workout_id

        legacy = counted(0, "zone2", 35, (7, 35, 4, 0, 0))  # Monday's walk
        full = counted(1, "zone2", 66, (7, 35, 4, 0, 0))  # counted the new way
        edited = counted(2, "zone2", 50, (7, 35, 4, 0, 0))  # the person typed 50
        harder = counted(3, "moderate-cardio", 66, (0, 10, 30, 0, 0))  # logged in full then
        tie = counted(4, "zone2", 20, (0, 20, 30, 0, 0))  # 20 = zone 2 but zones 3-5 won
        session.commit()

    def values() -> dict[int, int]:
        with make_session_factory(engine, user_id=OWNER)() as session:
            return dict(session.execute(select(SetLog.workout_id, SetLog.value)).all())

    before = values()
    command.upgrade(cfg, "head")
    assert values() == before | {legacy: 66}
    assert (values()[full], values()[edited], values()[harder], values()[tie]) == (66, 50, 66, 20)
    command.downgrade(cfg, BEFORE)
    assert values()[legacy] == 35  # and a full one goes back too: what the old code logged
    engine.dispose()
    get_settings.cache_clear()
