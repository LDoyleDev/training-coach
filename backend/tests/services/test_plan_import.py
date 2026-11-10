"""plan.toml brought to the owner's plan (ADR-0073): nothing until they save it, then one version,
and it never reaches anyone else. The file is the whole plan (ADR-0093 Decided 14): a session it
lacks is removed, a retired one it has is put back."""

from datetime import date, timedelta

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests import factories
from tests.services.test_seed import MINI_PLAN, _sessions
from training_coach.db.models import (
    Event,
    PlanNotice,
    PlanVersion,
    SessionProgress,
    SessionTemplate,
    TemplateItem,
    User,
    Workout,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import plan_import, undo, users
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
        (
            lambda t: t.replace('slug = "upper"\n', 'slug = "upper"\nrest_after = 2\n', 1),
            "Upper: rest days after it, 0 becomes 2",  # ADR-0091
        ),
    ],
    ids=["renamed", "swapped", "added", "focus", "rest"],
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


def _retire_arms(session: Session) -> None:
    arms = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "arms")).one()
    factories.retire(session, arms, TODAY)
    session.commit()


def test_a_retired_session_missing_from_the_file_is_left_alone(
    session: Session, plan: PlanSeed
) -> None:
    """A workout names it, so it stays, out of the cycle (ADR-0093); the file need not have it."""
    _retire_arms(session)
    head, blocks = _sessions(MORE_SETS)
    found = plan_import.save(session, load_plan(head + blocks[0]), TODAY)
    assert found.blocked is None
    assert found.changes == ("Upper: Pull-up, 4 x 5-12 becomes 5 x 5-12",)
    rows = session.execute(select(SessionTemplate.slug, SessionTemplate.position)).all()
    arms = session.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == "arms")).one()
    assert sorted(rows) == [("arms", 10_000 + arms), ("upper", 0)]  # still parked


def _row(session: Session, slug: str) -> SessionTemplate:
    return session.scalars(select(SessionTemplate).where(SessionTemplate.slug == slug)).one()


def _only(text: str, slug: str) -> PlanSeed:
    """The file with only the session ``slug``."""
    head, blocks = _sessions(text)
    return load_plan(head + next(b for b in blocks if f'slug = "{slug}"' in b))


def _pointer(session: Session) -> tuple[int | None, list[int]]:
    state = users.plan_state(session)
    assert state is not None
    return state.next_template_id, state.queued


def _told(session: Session) -> tuple[list[str], list[dict[str, int]]]:
    notices = session.scalars(select(PlanNotice.text).order_by(PlanNotice.id))
    events = session.scalars(select(Event.payload).where(Event.kind == undo.CYCLE_CHANGED))
    return list(notices), list(events)


EXTRA = (
    '\n[[sessions]]\nslug = "extra"\nname = "Extra"\nfocus = "x"\n'
    'items = [{ exercise = "dip", sets = 3, rep_min = 8, rep_max = 15 }]\n'
)


def test_a_session_the_file_lacks_with_history_is_retired(session: Session, plan: PlanSeed) -> None:
    upper = _row(session, "upper")
    session.add(Workout(local_date=TODAY - timedelta(days=1), template_id=upper.id, status="done"))
    session.commit()
    file = _only(MINI_PLAN, "arms")
    assert plan_import.preview(session, file, TODAY).changes == (
        "Removes Upper: its history stays",
    )
    assert upper.retired_on is None  # nothing changes until he saves
    saved = plan_import.save(session, file, TODAY)
    session.commit()
    assert saved.blocked is None
    assert (upper.retired_on, upper.position, upper.name) == (TODAY, 10_000 + upper.id, "Upper")
    assert upper.items == []
    assert _row(session, "arms").position == 0
    assert plan_import.preview(session, file, TODAY) == plan_import.Preview(())


def test_a_session_the_file_lacks_with_nothing_logged_is_deleted(
    session: Session, plan: PlanSeed
) -> None:
    file = _only(MINI_PLAN, "arms")
    assert plan_import.preview(session, file, TODAY).changes == ("Removes Upper",)
    plan_import.save(session, file, TODAY)
    session.commit()
    assert list(session.scalars(select(SessionTemplate.slug))) == ["arms"]


def test_the_pointer_on_a_removed_session_moves_to_the_next(
    session: Session, plan: PlanSeed
) -> None:
    """Decided 9: the next live session after it in the old order, and ``queued`` drops it."""
    upper, arms = _row(session, "upper"), _row(session, "arms")
    state = users.plan_state(session)
    assert state is not None
    state.next_template_id, state.queued = arms.id, [upper.id]
    session.commit()
    plan_import.save(session, _only(MINI_PLAN, "upper"), TODAY)
    session.commit()
    assert _pointer(session) == (upper.id, [])
    notices, events = _told(session)
    assert notices == ["Your plan changed: removed Arms. Next is Upper."]
    assert events == [{"added": 0, "removed": 1, "retired": 0, "moved": 0}]


def test_a_retired_session_the_file_has_is_put_back_under_its_name(
    session: Session, plan: PlanSeed
) -> None:
    _retire_arms(session)
    file = load_plan(MINI_PLAN.replace('name = "Arms"', 'name = "Arms day"'))
    assert plan_import.preview(session, file, TODAY).changes == ("Puts back Arms day",)
    saved = plan_import.save(session, file, TODAY)
    session.commit()
    assert saved.blocked is None
    arms = _row(session, "arms")
    assert (arms.retired_on, arms.position, arms.name) == (None, 1, "Arms day")
    assert [(i.exercise.slug, i.sets) for i in arms.items] == [("dip", 3)]
    notices, events = _told(session)
    assert notices == ["Your plan changed: put back Arms day. Next is Upper."]
    assert events == [{"added": 1, "removed": 0, "retired": 0, "moved": 0}]
    assert plan_import.preview(session, file, TODAY) == plan_import.Preview(())


def test_a_new_session_after_the_one_done_last_is_next(session: Session, plan: PlanSeed) -> None:
    arms = _row(session, "arms")
    session.add(Workout(local_date=TODAY - timedelta(days=1), template_id=arms.id, status="done"))
    session.commit()
    plan_import.save(session, load_plan(MINI_PLAN + EXTRA), TODAY)
    session.commit()
    assert _pointer(session) == (_row(session, "extra").id, [])
    assert _told(session)[0] == ["Your plan changed: added Extra. Next is Extra."]


def test_only_a_reorder_is_said_as_a_move(session: Session, plan: PlanSeed) -> None:
    """A session shifted by an add or a removal hasn't moved; a reorder moves the fewest."""
    head, blocks = _sessions(MINI_PLAN)
    changes = plan_import.preview(session, load_plan(head + blocks[1] + blocks[0]), TODAY).changes
    assert len(changes) == 1
    assert "moves to place" in changes[0]
    first = load_plan(head + EXTRA + "".join(blocks))
    assert plan_import.preview(session, first, TODAY).changes == ("New session: Extra",)


def test_an_item_change_writes_no_notice_or_cycle_event(session: Session, plan: PlanSeed) -> None:
    plan_import.save(session, load_plan(MORE_SETS), TODAY)
    session.commit()
    assert _told(session) == ([], [])


@pytest.mark.parametrize(
    ("text", "refusal"),
    [
        (
            MINI_PLAN.replace('name = "Arms"', 'name = "upper"'),
            "Two sessions can't both be called upper.",
        ),
        (
            MINI_PLAN.replace('name = "Arms"', 'name = "Dip"'),
            "Dip is an exercise's name; pick another for a session.",
        ),
        (
            MINI_PLAN.replace('name = "Dip"', 'name = "Dip"\naliases = ["arms"]'),
            "Arms is an exercise's name; pick another for a session.",
        ),
    ],
    ids=["two-sessions", "an-exercise", "an-alias"],
)
def test_a_name_clash_is_refused_before_anything_is_listed(
    session: Session, plan: PlanSeed, text: str, refusal: str
) -> None:
    """Decided 3 over the plan the file makes (Decided 14): the file is fixed first."""
    file = load_plan(VERSIONS + text.replace("sets = 4", "sets = 5"))
    expected = plan_import.Preview((), plan_import.FIX + refusal)
    assert plan_import.preview(session, file, TODAY) == expected
    assert plan_import.save(session, file, TODAY) == expected
    assert 5 not in _items(session)


def test_a_cycle_past_the_limits_is_refused(session: Session, plan: PlanSeed) -> None:
    rested = MINI_PLAN.replace('focus = "Strength"', 'focus = "Strength"\nrest_after = 6')
    rested = rested.replace('focus = "Accessories"', 'focus = "Accessories"\nrest_after = 6')
    found = plan_import.preview(session, load_plan(rested + EXTRA), TODAY)
    expected = "Your cycle would be 15 days; it can be at most 14."
    assert found == plan_import.Preview((), plan_import.FIX + expected)


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
