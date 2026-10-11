"""/api/account/heart-rate: the zones and what sets them (ADR-0055)."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.api.test_erase import ORIGIN
from tests.api.test_erase import signed_in as signed_in  # a shared fixture
from training_coach.api.app import create_app
from training_coach.config import Settings

PATH = "/api/account/heart-rate"


def test_zones_with_nothing_set(signed_in: TestClient) -> None:
    found = signed_in.get(PATH).json()
    assert found["rest"] == 60
    assert found["max"] == 190
    assert found["zones"][1] == {"zone": 2, "low": 138, "high": 151}
    assert len(found["zones"]) == 5


def test_birth_year_and_own_max_set_the_zones(signed_in: TestClient) -> None:
    found = signed_in.put(PATH, json={"birth_year": 1986, "own_max": None}).json()
    assert found["birth_year"] == 1986
    assert found["estimated_max"] is not None
    assert found["max"] == found["estimated_max"]
    found = signed_in.put(PATH, json={"birth_year": 1986, "own_max": 182}).json()
    assert found["max"] == 182
    assert signed_in.get(PATH).json()["own_max"] == 182
    cleared = signed_in.put(PATH, json={}).json()
    assert (cleared["birth_year"], cleared["own_max"], cleared["max"]) == (None, None, 190)


def test_impossible_values_are_refused(signed_in: TestClient) -> None:
    answer = signed_in.put(PATH, json={"own_max": 260})
    assert answer.status_code == 422
    assert answer.json()["detail"] == "max heart rate must be from 120 to 230"


def test_strangers_get_nothing(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get(PATH).status_code == 401
        assert stranger.put(PATH, json={}).status_code == 401
