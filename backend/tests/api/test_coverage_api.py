from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.session import make_session_factory
from training_coach.domain.enums import Place, Places
from training_coach.services import auth, user_settings
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as signed_in:
        with make_session_factory(engine, user_id=OWNER)() as bound:
            apply_seed(bound, load_plan())
            token = auth.create_link(bound, datetime.now(UTC))
            bound.commit()
        assert signed_in.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield signed_in


def test_coverage_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as stranger:
        assert stranger.get("/api/plan/coverage").status_code == 401


def test_coverage_gives_each_muscle_its_band_and_warnings(client: TestClient) -> None:
    body = client.get("/api/plan/coverage").json()
    assert (body["main_on_target"], body["main_total"]) == (10, 10)
    assert (body["session_cap"], body["spine_cap"], body["grip_cap"]) == (11, 8, 8)
    assert (body["minimum"], body["ceiling"], body["back_to_back"]) == (4, 30, 4)
    muscles = {m["muscle"]: m for m in body["muscles"]}
    assert len(muscles) == 21
    assert [m["main"] for m in body["muscles"][:10]] == [True] * 10
    glutes = muscles["glutes"]
    assert (glutes["sets"], glutes["days"], glutes["band"]) == (15.5, 2, "green")
    assert (glutes["one_day"], glutes["over_session_cap"], glutes["most_in"]) == (
        False,
        False,
        "Legs",
    )
    assert {s["exercise"] for s in glutes["sources"]} >= {"Kettlebell swing", "Pistol squat"}
    assert muscles["triceps"]["missing_parts"] == []
    assert muscles["quads"]["missing_parts"] == []  # the reverse Nordic
    assert (muscles["abs"]["low"], muscles["abs"]["evidence"]) == (6, "low")
    assert (muscles["neck"]["low"], muscles["neck"]["high"], muscles["neck"]["evidence"]) == (
        3,
        9,
        "low",
    )
    assert muscles["quads"]["evidence"] is None
    legs = body["sessions"][0]
    assert {k: v for k, v in legs.items() if k != "muscles"} == {
        "session": "Legs",
        "slug": "legs",
        "place": "home",
        "spine_sets": 6,
        "grip_sets": 3,
        "spine_heavy": False,
        "grip_heavy": False,
    }
    assert body["hard_from"] == 6
    assert (body["place"], body["places"]) == ("home", "home")


def test_each_session_has_its_own_heat_map(client: TestClient) -> None:
    sessions = client.get("/api/plan/coverage").json()["sessions"]
    legs = {m["muscle"]: m for m in sessions[0]["muscles"]}
    assert (legs["glutes"]["sets"], legs["glutes"]["heat"]) == (10.5, "hard")
    assert "chest" not in legs  # only what the session works
    assert all(m["sets"] > 0 for s in sessions for m in s["muscles"])
    by_slug = {s["slug"]: s for s in sessions}
    assert by_slug["zone2"]["muscles"] == []  # cardio only
    core = {m["muscle"] for m in by_slug["moderate-cardio"]["muscles"]}
    assert {"abs", "obliques", "adductors"} <= core


def test_coverage_counts_the_place_asked_for(client: TestClient) -> None:
    body = client.get("/api/plan/coverage", params={"place": "gym"}).json()
    assert (body["place"], body["places"]) == ("gym", "home")  # anyone may look
    by_slug = {s["slug"]: s for s in body["sessions"]}
    assert (by_slug["legs"]["place"], by_slug["recovery"]["place"]) == ("gym", "home")
    hamstrings = {m["muscle"]: m for m in body["muscles"]}["hamstrings"]
    assert (hamstrings["sets"], hamstrings["days"]) == (12, 3)
    assert client.get("/api/plan/coverage", params={"place": "park"}).status_code == 422


def test_coverage_starts_at_the_days_place(client: TestClient, engine: Engine) -> None:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        user_settings.update(bound, places=Places.BOTH, place=Place.GYM)
        bound.commit()
    body = client.get("/api/plan/coverage").json()
    assert (body["place"], body["places"]) == ("gym", "both")
    home = client.get("/api/plan/coverage", params={"place": "home"}).json()
    assert home["place"] == "home"
    with make_session_factory(engine, user_id=OWNER)() as bound:
        assert user_settings.load(bound).place is Place.GYM  # looking changes nothing
