"""Old ids after a session is removed (ADR-0093 Decided 12): a pick menu left open, the Log
page's session choice and a guided start refuse a session that is no longer in the cycle,
retired or deleted, in words. Rest, Push and Swap were already safe, as they need the pointer.
(A proposal's save is in ``tests/api/test_mcp_propose.py``, the bot's buttons in
``tests/bot/test_removed_sessions.py``.)"""

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests import factories
from tests.services.test_today import PLAN
from tests.services.test_workout_log import BERLIN, TODAY
from training_coach.db.models import Event, PlanState, SessionTemplate, Workout
from training_coach.services import day_log, guided, queue_actions, workout_log
from training_coach.services.plan_rows import GONE
from training_coach.services.seed import apply_seed, load_plan

# Removed with workouts naming it, or with none (Decided 5).
HOW = ["retired", "deleted"]


@pytest.fixture
def seeded(session: Session) -> Session:
    apply_seed(session, load_plan(PLAN))
    session.flush()
    return session


def _id(session: Session, slug: str) -> int:
    return session.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == slug)).one()


def _remove(session: Session, slug: str, how: str) -> int:
    """Take a session out of the cycle, as the cycle edit does; its id."""
    row = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == slug)).one()
    gone = row.id
    if how == "retired":
        factories.retire(session, row, TODAY)
    else:
        session.delete(row)
        session.flush()
    return gone


def _pointer(session: Session) -> int | None:
    return session.get_one(PlanState, 1).next_template_id


def _events(session: Session) -> list[str]:
    return list(session.scalars(select(Event.kind).where(Event.kind.startswith("queue."))))


def _workouts(session: Session) -> int:
    return len(list(session.scalars(select(Workout.id))))


@pytest.mark.parametrize("how", HOW)
def test_a_pick_menu_left_open_is_refused_in_words(seeded: Session, how: str) -> None:
    upper = _id(seeded, "upper")  # the pointer
    gone = _remove(seeded, "zone2", how)
    assert queue_actions.pick(seeded, upper, gone) == GONE
    assert _events(seeded) == []
    assert _pointer(seeded) == upper


@pytest.mark.parametrize("how", HOW)
def test_rest_push_and_swap_naming_a_removed_session_stay_stale(seeded: Session, how: str) -> None:
    """Already safe before ADR-0093: each needs the pointer, which never names a removed one."""
    upper = _id(seeded, "upper")
    gone = _remove(seeded, "zone2", how)
    assert queue_actions.rest_today(seeded, gone, TODAY) is None
    assert queue_actions.push_to_tomorrow(seeded, gone, TODAY) is None
    assert queue_actions.swap_next(seeded, gone) is None
    assert (_workouts(seeded), _events(seeded), _pointer(seeded)) == (0, [], upper)


@pytest.mark.parametrize("how", HOW)
@pytest.mark.parametrize("days_ago", [0, 1])
@pytest.mark.parametrize("extra", [False, True])
def test_the_log_page_refuses_a_removed_session_in_words(
    seeded: Session, how: str, days_ago: int, extra: bool
) -> None:
    day = TODAY - timedelta(days=days_ago)
    gone = _remove(seeded, "zone2", how)
    assert day_log.plan(seeded, day, gone, BERLIN) is None
    sets = [guided.Done(item=0, set_no=1, left=40)]
    found = day_log.save_sets(seeded, day, TODAY, BERLIN, gone, sets, "ab" * 16, extra=extra)
    assert found == GONE
    assert _workouts(seeded) == 0


@pytest.mark.parametrize("how", HOW)
def test_a_guided_start_never_opens_a_session_removed_after_its_pick(
    seeded: Session, how: str
) -> None:
    upper, zone2 = _id(seeded, "upper"), _id(seeded, "zone2")
    queue_actions.pick(seeded, upper, zone2)
    picked = guided.today(seeded, TODAY, BERLIN)
    assert picked is not None
    assert picked.template_id == zone2
    _remove(seeded, "zone2", how)
    # The pick no longer holds: today is the queue's session again, guided and typed.
    found = guided.today(seeded, TODAY, BERLIN)
    assert found is not None
    assert found.template_id == upper
    target = workout_log.target(seeded, TODAY, BERLIN)
    assert target is not None
    assert target.id == upper
