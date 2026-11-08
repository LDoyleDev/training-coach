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
