from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.services.test_today import PLAN
from training_coach.db.models import Event, PlanState, SessionTemplate, Workout
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import queue_actions
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.today import week

DAY = date(2026, 10, 6)


@pytest.fixture
def seeded(session: Session) -> Session:
    apply_seed(session, load_plan(PLAN))
    session.flush()
    return session


def _ids(session: Session) -> dict[str, int]:
    return {t.slug: t.id for t in session.scalars(select(SessionTemplate))}


def _state(session: Session) -> PlanState:
    state = session.get(PlanState, 1)
    assert state is not None
    return state


def _point_at(session: Session, slug: str) -> int:
    template_id = _ids(session)[slug]
    _state(session).next_template_id = template_id
    session.flush()
    return template_id


def _week(session: Session, on: date = DAY) -> list[str]:
    days = week(session, on, days=4)
    assert days is not None
    return [d.session for d in days]


def _workouts(session: Session) -> list[tuple[int | None, str]]:
    return [(w.template_id, w.status) for w in session.scalars(select(Workout))]


def _events(session: Session) -> list[str]:
    query = select(Event.kind).where(Event.kind.startswith("queue.")).order_by(Event.id)
    return list(session.scalars(query))


def test_rest_on_the_optional_session_counts_as_done(seeded: Session) -> None:
    rest = _point_at(seeded, "rest")
    outcome = queue_actions.rest_today(seeded, rest, DAY)
    assert outcome == queue_actions.RestOutcome(session="Rest", advanced=True)
    assert _workouts(seeded) == [(rest, WorkoutStatus.REST)]
    assert _state(seeded).next_template_id == _ids(seeded)["upper"]
    assert _events(seeded) == ["queue.rest"]


def test_rest_on_a_training_session_holds_it_for_tomorrow(seeded: Session) -> None:
    upper = _ids(seeded)["upper"]
    outcome = queue_actions.rest_today(seeded, upper, DAY)
    assert outcome == queue_actions.RestOutcome(session="Upper", advanced=False)
    assert _workouts(seeded) == [(upper, WorkoutStatus.SKIPPED)]
    assert _state(seeded).next_template_id == upper


def test_push_to_tomorrow_holds_the_session(seeded: Session) -> None:
    upper = _ids(seeded)["upper"]
    assert queue_actions.push_to_tomorrow(seeded, upper, DAY) == "Upper"
    assert _workouts(seeded) == [(upper, WorkoutStatus.SKIPPED)]
    assert _week(seeded, date(2026, 10, 7)) == ["Upper", "Zone 2", "Rest", "Upper"]
    assert _events(seeded) == ["queue.pushed"]


def test_swap_with_next_reorders_two_days_then_resumes(seeded: Session) -> None:
    upper = _ids(seeded)["upper"]
    plan = queue_actions.swap_next(seeded, upper)
    assert plan is not None
    assert plan.name == "Zone 2"
    assert _week(seeded) == ["Zone 2", "Upper", "Rest", "Upper"]
    assert _events(seeded) == ["queue.swapped"]


def test_pick_shows_another_session_and_keeps_the_queue(seeded: Session) -> None:
    ids = _ids(seeded)
    plan = queue_actions.pick(seeded, ids["upper"], ids["rest"])
    assert plan is not None
    assert plan.name == "Rest"
    assert _state(seeded).next_template_id == ids["upper"]
    assert _workouts(seeded) == []
    assert _events(seeded) == ["queue.picked"]


def test_pick_rejects_the_same_or_an_unknown_session(seeded: Session) -> None:
    upper = _ids(seeded)["upper"]
    assert queue_actions.pick(seeded, upper, upper) is None
    assert queue_actions.pick(seeded, upper, 999) is None
    assert _events(seeded) == []


def test_choices_lists_sessions_in_order(seeded: Session) -> None:
    assert [name for _, name in queue_actions.choices(seeded)] == ["Upper", "Zone 2", "Rest"]


@pytest.mark.parametrize("action", ["rest", "push", "swap", "pick"])
def test_buttons_on_an_old_message_change_nothing(seeded: Session, action: str) -> None:
    """The queue moved on since the message was sent: the button names a stale session."""
    ids = _ids(seeded)
    stale = ids["zone2"]  # the pointer is at upper
    result = {
        "rest": lambda: queue_actions.rest_today(seeded, stale, DAY),
        "push": lambda: queue_actions.push_to_tomorrow(seeded, stale, DAY),
        "swap": lambda: queue_actions.swap_next(seeded, stale),
        "pick": lambda: queue_actions.pick(seeded, stale, ids["rest"]),
    }[action]()
    assert result is None
    assert _state(seeded).next_template_id == ids["upper"]
    assert _workouts(seeded) == []
    assert _events(seeded) == []


def test_no_plan_means_every_action_is_stale(session: Session) -> None:
    assert queue_actions.rest_today(session, 1, DAY) is None
    assert queue_actions.push_to_tomorrow(session, 1, DAY) is None
    assert queue_actions.swap_next(session, 1) is None
    assert queue_actions.pick(session, 1, 2) is None


@pytest.mark.parametrize("action", ["rest", "push"])
def test_pressing_rest_or_push_twice_logs_once(seeded: Session, action: str) -> None:
    """The morning message and /today both carry buttons for the same session."""
    upper = _ids(seeded)["upper"]
    act = queue_actions.rest_today if action == "rest" else queue_actions.push_to_tomorrow
    assert act(seeded, upper, DAY) is not None
    assert act(seeded, upper, DAY) is not None
    assert _workouts(seeded) == [(upper, WorkoutStatus.SKIPPED)]
