"""Rest places in the queue (ADR-0091): a session's rest days come after it, offer no session,
and pass by the calendar; a missed session still waits."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.services.test_today import PLAN
from training_coach.db.models import PlanState, SessionTemplate, Workout
from training_coach.domain.enums import WorkoutStatus
from training_coach.domain.queue import local_date
from training_coach.services import ai_summary, guided, home, queue_actions
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.today import REST_DAY, rest_days, today, week

BERLIN = ZoneInfo("Europe/Berlin")
# Upper, a rest place, Zone 2, then the optional Rest session (test_today's plan).
RESTED = PLAN.replace('slug = "upper"\n', 'slug = "upper"\nrest_after = 1\n', 1)
NOW = local_date(datetime.now(UTC), BERLIN)  # picks are dated by when they happen


def _id(session: Session, slug: str) -> int:
    return session.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == slug)).one()


@pytest.fixture
def rested(session: Session) -> Session:
    """Upper done yesterday, so today is its rest place and Zone 2 is next."""
    apply_seed(session, load_plan(RESTED))
    session.add(
        Workout(
            local_date=NOW - timedelta(days=1),
            template_id=_id(session, "upper"),
            status=WorkoutStatus.DONE,
        )
    )
    state = session.scalars(select(PlanState)).one()
    state.next_template_id = _id(session, "zone2")
    session.flush()
    return session


def test_the_day_after_a_session_is_its_rest_place(rested: Session) -> None:
    found = today(rested, NOW)
    assert found is not None
    assert (found.rest_day, found.session.name) == (True, "Zone 2")
    later = today(rested, NOW + timedelta(days=1))
    assert later is not None
    assert (later.rest_day, later.session.name) == (False, "Zone 2")


def test_a_missed_session_still_waits(rested: Session) -> None:
    assert rest_days(rested, NOW + timedelta(days=5)) == 0
    found = today(rested, NOW + timedelta(days=5))
    assert found is not None
    assert (found.rest_day, found.session.name) == (False, "Zone 2")


def test_the_week_gives_each_rest_place_its_day(rested: Session) -> None:
    days = week(rested, NOW)
    assert days is not None
    assert [d.session for d in days] == [
        REST_DAY,
        "Zone 2",
        "Rest",
        "Upper",
        REST_DAY,
        "Zone 2",
        "Rest",
    ]
    assert [d.date for d in days] == [NOW + timedelta(days=n) for n in range(7)]


def test_a_session_done_today_is_not_followed_by_rest_today(rested: Session) -> None:
    rested.add(Workout(local_date=NOW, template_id=_id(rested, "zone2"), status="done"))
    rested.flush()
    assert rest_days(rested, NOW) == 0


def test_a_rest_day_offers_no_guided_session_unless_one_is_picked(rested: Session) -> None:
    assert guided.today(rested, NOW, BERLIN) is None
    assert home.home(rested, NOW, BERLIN).today == REST_DAY
    assert "Today is a rest day." in ai_summary.summary(rested, NOW, ai_summary.Options(weeks=4))
    queue_actions.pick(rested, _id(rested, "zone2"), _id(rested, "upper"))
    picked = guided.today(rested, NOW, BERLIN)
    assert picked is not None
    assert picked.name == "Upper"


def test_without_rest_places_nothing_changes(session: Session) -> None:
    """The owner's 7-day cycle has none: the day after a session offers the next one."""
    apply_seed(session, load_plan(PLAN))
    yesterday = date(2026, 10, 5)
    session.add(Workout(local_date=yesterday, template_id=_id(session, "upper"), status="done"))
    session.flush()
    found = today(session, yesterday + timedelta(days=1))
    assert found is not None
    assert found.rest_day is False
    assert [t.rest_after for t in session.scalars(select(SessionTemplate))] == [0, 0, 0]


@pytest.fixture
def starting(session: Session) -> Session:
    """A plan that starts in three days (ADR-0091 addendum), nothing done yet."""
    apply_seed(session, load_plan(RESTED))
    session.scalars(select(PlanState)).one().starts_on = NOW + timedelta(days=3)
    session.flush()
    return session


def test_before_the_start_every_day_is_a_rest_day_that_names_the_first(
    starting: Session,
) -> None:
    for n in range(3):
        found = today(starting, NOW + timedelta(days=n))
        assert found is not None
        assert (found.rest_day, found.starts_on) == (True, NOW + timedelta(days=3))
    first = today(starting, NOW + timedelta(days=3))
    assert first is not None
    assert (first.rest_day, first.starts_on, first.session.name) == (False, None, "Upper")
    days = week(starting, NOW)
    assert days is not None
    assert [d.session for d in days][:5] == [REST_DAY, REST_DAY, REST_DAY, "Upper", REST_DAY]


def test_before_the_start_the_person_can_still_train(starting: Session) -> None:
    """Train today instead (a pick), and once a planned session is done the start day no longer
    matters: the rest places count from it, as before."""
    assert guided.today(starting, NOW, BERLIN) is None
    upper = _id(starting, "upper")
    queue_actions.pick(starting, upper, upper)
    picked = guided.today(starting, NOW, BERLIN)
    assert picked is not None
    assert picked.name == "Upper"
    starting.add(Workout(local_date=NOW, template_id=upper, status=WorkoutStatus.DONE))
    state = starting.scalars(select(PlanState)).one()
    state.next_template_id = _id(starting, "zone2")
    starting.flush()
    later = today(starting, NOW + timedelta(days=2))
    assert later is not None
    assert (later.rest_day, later.starts_on, later.session.name) == (False, None, "Zone 2")


def test_a_start_day_today_or_past_changes_nothing(starting: Session) -> None:
    starting.scalars(select(PlanState)).one().starts_on = NOW
    starting.flush()
    found = today(starting, NOW)
    assert found is not None
    assert (found.rest_day, found.starts_on) == (False, None)
