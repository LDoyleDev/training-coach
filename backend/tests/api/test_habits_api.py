"""/api/habits (ux-flow-plan C5): today's habits on the web, owner-only, the bot's service."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.habits import Habit
from training_coach.domain.queue import local_date
from training_coach.services import auth, habits, user_settings
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


def _today() -> date:
    return local_date(datetime.now(UTC), Settings().tz)


def test_lists_every_habit_with_what_counts(signed_in: TestClient) -> None:
    view = signed_in.get("/api/habits").json()
    assert view["day"] == _today().isoformat()
    assert view["week_days"] == _today().weekday() + 1
    assert [h["key"] for h in view["habits"]] == ["morning_light", "protein", "wind_down"]
    first = view["habits"][0]
    assert first["label"] == "Morning light"
    assert first["hint"].startswith("outside within an hour of waking")
    assert (first["done"], first["week_done"]) == (False, 0)


def test_the_protein_label_names_the_target_once_set(signed_in: TestClient, engine: Engine) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        user_settings.update(mine, protein_g=165)
    protein = signed_in.get("/api/habits").json()["habits"][1]
    assert protein["label"] == "Protein target (165 g)"


def test_a_tap_ticks_and_another_unticks(signed_in: TestClient, engine: Engine) -> None:
    ticked = signed_in.put("/api/habits/protein", json={"done": True}).json()
    assert [h["done"] for h in ticked["habits"]] == [False, True, False]
    assert ticked["habits"][1]["week_done"] == 1
    assert signed_in.put("/api/habits/protein", json={"done": True}).json() == ticked
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert habits.checked(mine, _today()) == {Habit.PROTEIN}  # what the bot shows
    unticked = signed_in.put("/api/habits/protein", json={"done": False}).json()
    assert unticked["habits"][1]["done"] is False
    assert unticked["habits"][1]["week_done"] == 0


def test_the_week_counts_ticks_from_the_bot_on_earlier_days(
    signed_in: TestClient, engine: Engine
) -> None:
    today = _today()
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        habits.toggle(mine, today, Habit.WIND_DOWN, today)
        if today.weekday() > 0:  # yesterday is in this week
            habits.toggle(mine, today - timedelta(days=1), Habit.WIND_DOWN, today)
    wind_down = signed_in.get("/api/habits").json()["habits"][2]
    assert wind_down["done"] is True
    assert wind_down["week_done"] == (2 if today.weekday() > 0 else 1)


def test_an_unknown_habit_or_no_state_is_refused(signed_in: TestClient) -> None:
    assert signed_in.put("/api/habits/sleep", json={"done": True}).status_code == 422
    assert signed_in.put("/api/habits/protein", json={}).status_code == 422


def test_signed_out_gets_nothing(client: TestClient) -> None:
    assert client.get("/api/habits").status_code == 401
    assert client.put("/api/habits/protein", json={"done": True}).status_code == 401
