"""plan.toml brought to the owner's plan (ADR-0073): nothing until they save it, then one version,
and it never reaches anyone else."""

from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.services.test_seed import MINI_PLAN, _sessions
from training_coach.db.models import (
    PlanVersion,
    SessionProgress,
    SessionTemplate,
    TemplateItem,
    User,
    Workout,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import plan_import
from training_coach.services.seed import PlanSeed, apply_seed, load_plan

TODAY = date(2026, 11, 7)
VERSIONS = """
[[versions]]
since = 2026-11-06
name = "More pulling"
"""
MORE_SETS = VERSIONS + MINI_PLAN.replace("sets = 4", "sets = 5")


def _items(session: Session) -> list[int]:
    return sorted(session.scalars(select(TemplateItem.sets)))


@pytest.fixture
def plan(session: Session) -> PlanSeed:
    started = load_plan(MINI_PLAN)
    apply_seed(session, started)
    session.commit()
    return started


def test_a_plan_matching_the_file_has_nothing_waiting(session: Session, plan: PlanSeed) -> None:
    assert plan_import.preview(session, plan, TODAY) == plan_import.Preview(())


def test_the_preview_says_what_would_change_and_changes_nothing(
    session: Session, plan: PlanSeed
) -> None:
    before = _items(session)
    found = plan_import.preview(session, load_plan(MORE_SETS), TODAY)
    assert found.changes == ("Upper: Pull-up, 4 x 5-12 becomes 5 x 5-12",)
    assert found.version == "More pulling"
    assert found.blocked is None
    assert _items(session) == before


@pytest.mark.parametrize(
    ("edit", "line"),
    [
        (lambda t: t.replace('name = "Upper"', 'name = "Top half"'), "Upper: now called Top half"),
        (
            lambda t: t.replace(
                'items = [{ exercise = "pull-up", sets = 4, rep_min = 5, rep_max = 12 }]',
                'items = [{ exercise = "dip", sets = 4, rep_min = 5, rep_max = 12 }]',
            ),
            "Upper: Pull-up becomes Dip, 4 x 5-12",
        ),
        (
            lambda t: t.replace(
                'items = [{ exercise = "pull-up", sets = 4, rep_min = 5, rep_max = 12 }]',
                'items = [{ exercise = "pull-up", sets = 4, rep_min = 5, rep_max = 12 },'
                ' { exercise = "dip", sets = 3, rep_min = 8, rep_max = 15 }]',
            ),
            "Upper: adds Dip, 3 x 8-15",
        ),
        (
            lambda t: t.replace('focus = "Strength"', 'focus = "Power"', 1),
            "Upper: its focus or kind",
        ),
    ],
    ids=["renamed", "swapped", "added", "focus"],
)
def test_each_kind_of_change_is_said(session: Session, plan: PlanSeed, edit, line: str) -> None:  # type: ignore[no-untyped-def]  # a lambda per case
    assert line in plan_import.preview(session, load_plan(edit(MINI_PLAN)), TODAY).changes


def test_a_new_session_and_a_dropped_item_are_said(session: Session) -> None:
    two = MINI_PLAN.replace(
        'items = [{ exercise = "pull-up", sets = 4, rep_min = 5, rep_max = 12 }]',
        'items = [{ exercise = "pull-up", sets = 4, rep_min = 5, rep_max = 12 },'
        ' { exercise = "dip", sets = 3, rep_min = 8, rep_max = 15 }]',
    )
    apply_seed(session, load_plan(two))
    session.commit()
    extra = MINI_PLAN + (
        '\n[[sessions]]\nslug = "extra"\nname = "Extra"\nfocus = "x"\n'
        'items = [{ exercise = "dip", sets = 3, rep_min = 8, rep_max = 15 }]\n'
    )
    changes = plan_import.preview(session, load_plan(extra), TODAY).changes
    assert "Upper: drops Dip" in changes
    assert "New session: Extra" in changes


def test_saving_changes_the_sessions_and_makes_one_version(
    session: Session, plan: PlanSeed
) -> None:
    file = load_plan(MORE_SETS)
    saved = plan_import.save(session, file, TODAY)
    session.commit()
    assert saved.changes
    assert 5 in _items(session)
    versions = [(v.since, v.name) for v in session.scalars(select(PlanVersion))]
    assert versions == [(TODAY, "More pulling")]
    assert plan_import.preview(session, file, TODAY) == plan_import.Preview(())


def test_a_second_save_that_day_updates_its_version(session: Session, plan: PlanSeed) -> None:
    plan_import.save(session, load_plan(MORE_SETS), TODAY)
    session.commit()
    again = MORE_SETS.replace("sets = 5", "sets = 6").replace("More pulling", "Even more")
    plan_import.save(session, load_plan(again), TODAY)
    session.commit()
    assert [(v.since, v.name) for v in session.scalars(select(PlanVersion))] == [
        (TODAY, "Even more")
    ]


def test_a_workout_keeps_the_version_it_has(session: Session, plan: PlanSeed) -> None:
    session.add(PlanVersion(since=date(2026, 11, 1), name="Before"))
    session.flush()
    earlier_today = Workout(local_date=TODAY, status=WorkoutStatus.REST)
    session.add(earlier_today)
    session.commit()
    before = earlier_today.plan_version_id
    assert before is not None
    plan_import.save(session, load_plan(MORE_SETS), TODAY)
    session.commit()
    session.refresh(earlier_today)
    assert earlier_today.plan_version_id == before


def _first(session: Session) -> SessionTemplate:
    found = session.scalars(select(SessionTemplate).order_by(SessionTemplate.position)).first()
    assert found is not None
    return found


@pytest.mark.parametrize("day", [TODAY, date(2026, 11, 5)], ids=["today", "left-from-before"])
def test_a_session_in_progress_blocks_it_with_nothing_changed(
    session: Session, plan: PlanSeed, day: date
) -> None:
    kept = [{"item": 0, "set_no": 1, "left": 8}]
    session.add(
        SessionProgress(local_date=day, template_id=_first(session).id, token="ab" * 16, sets=kept)
    )
    session.commit()
    before = _items(session)
    found = plan_import.save(session, load_plan(MORE_SETS), TODAY)
    assert found.blocked == plan_import.IN_PROGRESS
    assert _items(session) == before
    assert session.scalars(select(PlanVersion)).all() == []


def test_a_session_started_with_no_sets_doesnt_block_it(session: Session, plan: PlanSeed) -> None:
    session.add(SessionProgress(local_date=TODAY, template_id=_first(session).id, token="ab" * 16))
    session.commit()
    assert plan_import.preview(session, load_plan(MORE_SETS), TODAY).blocked is None


def test_a_session_missing_from_the_file_blocks_it(session: Session, plan: PlanSeed) -> None:
    head, blocks = _sessions(MINI_PLAN)
    found = plan_import.save(session, load_plan(head + blocks[1]), TODAY)
    assert found.blocked is not None
    assert "Upper" in found.blocked
    names = session.scalars(select(SessionTemplate.name).order_by(SessionTemplate.position))
    assert list(names) == ["Upper", "Arms"]


def test_an_exercise_the_seed_hasnt_added_blocks_it(session: Session, plan: PlanSeed) -> None:
    added = MINI_PLAN.replace('slug = "dip"', 'slug = "ring-dip"').replace(
        'exercise = "dip"', 'exercise = "ring-dip"'
    )
    found = plan_import.preview(session, load_plan(added), TODAY)
    assert found.blocked is not None
    assert "catalogue" in found.blocked


def test_it_is_nothing_to_anyone_but_the_owner(engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
        shared.flush()
        apply_seed(shared, load_plan(MINI_PLAN))
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        file = load_plan(MORE_SETS)
        assert plan_import.preview(theirs, file, TODAY) == plan_import.Preview(())
        assert plan_import.save(theirs, file, TODAY) == plan_import.Preview(())
        assert 5 not in _items(theirs)
