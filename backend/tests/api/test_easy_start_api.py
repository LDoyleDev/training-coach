"""The easy start over the web (ADR-0094): the switch on Account, where it stands on Today, its
notices on the first page that lists them, and the two offers; never for the owner."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import SessionTemplate, User, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, easy_start, users
from training_coach.services.seed import apply_seed, bundled_plan

BASE = "https://testserver"
MEMBER = 2
START = date(2026, 12, 1)


def day(n: int) -> date:
    return START + timedelta(days=n)


def at(n: int, hour: int = 9) -> time_machine.travel:
    """Day ``n`` at ``hour`` UTC (an hour later in Berlin, in winter)."""
    on = day(n)
    return time_machine.travel(datetime(on.year, on.month, on.day, hour, tzinfo=UTC))


@pytest.fixture
def app(engine: Engine) -> Settings:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=MEMBER, role=users.MEMBER))
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, bundled_plan())
    return Settings(environment="test", database_url=str(engine.url), multi_user=True)


def _signed_in(settings: Settings, engine: Engine, user: int) -> Iterator[TestClient]:
    """Signed in on day 0, before any of the tests' days."""
    with TestClient(create_app(settings), base_url=BASE) as client:
        with at(0, hour=7), make_session_factory(engine, user_id=user)() as bound:
            token = auth.create_link(bound, datetime.now(UTC))
            bound.commit()
            assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


@pytest.fixture
def member(app: Settings, engine: Engine) -> Iterator[TestClient]:
    yield from _signed_in(app, engine, MEMBER)


@pytest.fixture
def owner(app: Settings, engine: Engine) -> Iterator[TestClient]:
    yield from _signed_in(app, engine, users.OWNER)


def _on(engine: Engine, *sessions: int) -> None:
    """The member's easy start on from day 0, with a strength session done on these days."""
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as theirs:
        assert easy_start.turn(theirs, True, day(0)) is None
        template = theirs.scalars(
            select(SessionTemplate.id).where(SessionTemplate.kind == "strength").limit(1)
        ).one()
        for n in sessions:
            theirs.add(Workout(local_date=day(n), template_id=template, status="done"))


def test_the_switch_on_account(member: TestClient) -> None:
    found = member.get("/api/settings").json()
    assert (found["easy_start"], found["easy_start_open"]) == (False, True)
    changed = member.patch("/api/settings", json={"easy_start": True})
    assert changed.status_code == 200
    assert changed.json()["easy_start"] is True
    assert member.patch("/api/settings", json={"easy_start": False}).json()["easy_start"] is False


def test_the_owner_is_never_offered_it(owner: TestClient) -> None:
    assert owner.get("/api/settings").json()["easy_start_open"] is False
    refused = owner.patch("/api/settings", json={"easy_start": True, "talk_test": True})
    assert refused.status_code == 409
    assert refused.json()["detail"] == easy_start.OWNER
    assert owner.get("/api/settings").json()["talk_test"] is False  # nothing else changed
    assert owner.post("/api/easy-start/extend").status_code == 409


def test_over_the_switch_is_closed(member: TestClient, engine: Engine) -> None:
    _on(engine, 0, 2, 4, 6, *range(14, 30, 2))  # over from day 42
    with at(21):  # a visit on the way, as a sign-in lasts 30 days from the last
        assert member.get("/api/settings").json()["easy_start_open"] is True
    with at(42):
        found = member.get("/api/settings").json()
        assert (found["easy_start"], found["easy_start_open"]) == (True, False)
        refused = member.patch("/api/settings", json={"easy_start": False})
        assert (refused.status_code, refused.json()["detail"]) == (409, easy_start.OVER)


def test_today_has_none_while_it_is_off(member: TestClient) -> None:
    assert member.get("/api/session/today").json()["easy_start"] is None


def test_today_says_where_it_stands(member: TestClient, engine: Engine) -> None:
    _on(engine, 0, 2)
    with at(3):
        found = member.get("/api/session/today").json()["easy_start"]
    assert found == {
        "phase": "light",
        "count": 2,
        "of": 4,
        "until": "2026-12-15",
        "over_from": "2027-01-12",
        "fresh": False,
        "ending": False,
        "restart": False,
        "extend": None,
        "line": "Easy start: light, session 3 of 4 (until at least 15 Dec). Then a 5-10 minute"
        " walk, if you can walk safely on your own.",
    }


def test_a_workout_from_before_midnight_counts_just_after_it(
    member: TestClient, engine: Engine
) -> None:
    """At 23:30 UTC on day 0 it is already day 1 in Berlin: day 0's session is behind."""
    _on(engine, 0)
    with at(0, hour=22):  # 23:00 in Berlin: still day 0, its own session not counted yet
        assert member.get("/api/session/today").json()["easy_start"]["phase"] == "waiting"
    with time_machine.travel(datetime(2026, 12, 1, 23, 30, tzinfo=UTC)):
        found = member.get("/api/session/today").json()["easy_start"]
    assert (found["phase"], found["count"]) == ("light", 1)


def test_a_step_up_is_noticed_once_on_the_first_page_that_lists_notices(
    member: TestClient, engine: Engine
) -> None:
    _on(engine, 0, 2, 4, 6)
    with at(13):
        assert member.get("/api/notices").json() == []
    with at(14):
        (notice,) = member.get("/api/notices").json()
        assert notice["text"] == easy_start.TOLD[easy_start.Phase.LOWER]
        assert member.get("/api/session/today").json()["easy_start"]["fresh"] is True
        assert len(member.get("/api/notices").json()) == 1


def test_one_more_easy_week(member: TestClient, engine: Engine) -> None:
    _on(engine, 0, 2, 4, 6)
    with at(10):
        refused = member.post("/api/easy-start/extend")
        assert (refused.status_code, refused.json()["detail"]) == (409, easy_start.NO_WEEK)
    with at(14):
        assert member.get("/api/session/today").json()["easy_start"]["extend"] == "light"
        taken = member.post("/api/easy-start/extend")
    assert taken.status_code == 200
    assert taken.json()["easy_start"]["phase"] == "light"
    assert taken.json()["easy_start"]["until"] == "2026-12-22"


def test_start_it_again_after_a_gap(member: TestClient, engine: Engine) -> None:
    _on(engine, 0, 2)
    with at(10):
        refused = member.post("/api/easy-start/restart")
        assert (refused.status_code, refused.json()["detail"]) == (409, easy_start.NO_RESTART)
    with at(16):
        assert member.get("/api/session/today").json()["easy_start"]["restart"] is True
        taken = member.post("/api/easy-start/restart")
    assert taken.status_code == 200
    assert taken.json()["easy_start"]["phase"] == "waiting"
