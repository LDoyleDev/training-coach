"""/api/account/body (ADR-0076): height, the thigh's landmark and the estimate setting."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.api.test_erase import ORIGIN
from tests.api.test_erase import signed_in as signed_in  # a shared fixture
from training_coach.api.app import create_app
from training_coach.config import Settings

PATH = "/api/account/body"


def test_nothing_set_is_off_with_the_usual_thigh(signed_in: TestClient) -> None:
    assert signed_in.get(PATH).json() == {
        "height_cm": None,
        "thigh_offset_cm": 15,
        "body_fat_estimate": "off",
    }


def test_settings_are_saved_and_cleared(signed_in: TestClient) -> None:
    chosen = {"height_cm": 182, "thigh_offset_cm": 12, "body_fat_estimate": "navy_male"}
    assert signed_in.put(PATH, json=chosen).json() == chosen
    assert signed_in.get(PATH).json() == chosen
    cleared = signed_in.put(PATH, json={}).json()
    assert cleared == {"height_cm": None, "thigh_offset_cm": 15, "body_fat_estimate": "off"}


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"height_cm": 90}, "height must be from 120 to 230 cm"),
        ({"thigh_offset_cm": 40}, "the thigh is measured from 5 to 30 cm above the kneecap"),
        ({"body_fat_estimate": "navy_female"}, None),  # no such setting: pydantic refuses it
        ({"height_cm": 181.5}, None),
    ],
)
def test_impossible_values_are_refused(
    signed_in: TestClient, body: dict[str, object], detail: str | None
) -> None:
    answer = signed_in.put(PATH, json=body)
    assert answer.status_code == 422
    if detail is not None:
        assert answer.json()["detail"] == detail
    assert signed_in.get(PATH).json()["body_fat_estimate"] == "off"


def test_strangers_get_nothing(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get(PATH).status_code == 401
        assert stranger.put(PATH, json={}).status_code == 401
