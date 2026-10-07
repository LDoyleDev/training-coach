"""Training blocks from the settings and pause history (ADR-0028, #26)."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, SessionTemplate, Workout
from training_coach.domain.blocks import Block, BlockKind
from training_coach.domain.queue import local_date
from training_coach.services import blocks, user_settings, workout_log
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.today import today

BERLIN = ZoneInfo("Europe/Berlin")
START = date(2026, 10, 5)


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def test_blocks_are_off_until_turned_on(plan: Session) -> None:
    assert blocks.current(plan, START, BERLIN) is None
    user_settings.update(plan, blocks=True, today=START)
    assert blocks.current(plan, START + timedelta(days=7), BERLIN) == Block(
        1, BlockKind.STRENGTH, 2
    )
    user_settings.update(plan, blocks=False)
    assert blocks.current(plan, START + timedelta(days=7), BERLIN) is None


def test_turning_blocks_on_needs_a_date(plan: Session) -> None:
    with pytest.raises(ValueError, match="today"):
        user_settings.update(plan, blocks=True)


def _paused(session: Session, on: date, paused: bool) -> None:
    session.add(
        Event(
            kind="settings.changed",
            payload={"paused": paused},
            at=datetime(on.year, on.month, on.day, 10, tzinfo=UTC),
        )
    )
    session.flush()


def test_a_paused_week_does_not_count(plan: Session) -> None:
    user_settings.update(plan, blocks=True, today=START)
    _paused(plan, START + timedelta(days=7), True)
    _paused(plan, START + timedelta(days=14), False)
    # Day 28 would start hypertrophy; with a week paused it's still week 4 of strength.
    assert blocks.current(plan, START + timedelta(days=28), BERLIN) == Block(
        1, BlockKind.STRENGTH, 4
    )


def test_a_saved_workout_records_its_block(plan: Session) -> None:
    on = local_date(datetime.now(UTC), BERLIN)
    workout_log.save(plan, workout_log.draft(plan, "pull-ups 8", on, BERLIN), BERLIN)
    user_settings.update(plan, blocks=True, today=on)
    workout_log.save(plan, workout_log.draft(plan, "dips 10", on, BERLIN), BERLIN)
    kinds = plan.scalars(select(Workout.block).order_by(Workout.id)).all()
    assert kinds == [None, "strength"]


def test_today_carries_the_block_and_the_session_kind(plan: Session) -> None:
    user_settings.update(plan, blocks=True, today=START)
    plan_today = today(plan, START, BERLIN)
    assert plan_today is not None
    assert plan_today.block == Block(1, BlockKind.STRENGTH, 1)
    assert plan_today.session.kind == "strength"  # the plan starts with Legs
    no_tz = today(plan, START)
    assert no_tz is not None
    assert no_tz.block is None


def test_the_seed_stores_each_sessions_kind(plan: Session) -> None:
    kinds = dict(plan.execute(select(SessionTemplate.slug, SessionTemplate.kind)).all())
    assert kinds["legs"] == "strength"
    assert kinds["recovery"] == "recovery"
    assert "conditioning" in kinds.values()
