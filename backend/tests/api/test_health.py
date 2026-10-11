"""/api/health and the band's sleep in the daily check (ADR-0054)."""

from typing import Any
from zoneinfo import ZoneInfo

import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests import hcw_payloads as hcw
from tests.api.test_erase import ORIGIN
from tests.api.test_erase import signed_in as signed_in  # a shared fixture
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import health_import
from training_coach.services.users import OWNER

BERLIN = ZoneInfo("Europe/Berlin")


def _import(engine: Engine, body: dict[str, Any]) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        health_import.store(mine, health_import.parse(body, hcw.NOW), BERLIN, hcw.NOW)


def _get(client: TestClient, path: str) -> dict[str, Any]:
    with time_machine.travel(hcw.NOW, tick=False):
        answer = client.get(path)
    assert answer.status_code == 200
    found: dict[str, Any] = answer.json()
    return found


def test_nothing_before_band_data(signed_in: TestClient) -> None:
    assert _get(signed_in, "/api/health") == {
        "sleep": None,
        "steps_today": None,
        "steps_yesterday": None,
        "resting": None,
        "usual_resting": None,
    }
    check = _get(signed_in, "/api/daily-check")
    assert (check["suggested_sleep"], check["band_asleep_min"]) == (None, None)


def test_last_night_steps_and_resting(signed_in: TestClient, engine: Engine) -> None:
    _import(engine, hcw.full())
    found = _get(signed_in, "/api/health")
    assert found["sleep"]["asleep"] == 440
    assert (found["sleep"]["deep"], found["sleep"]["rem"]) == (90, 100)
    assert (found["steps_today"], found["steps_yesterday"]) == (812, 11234)
    assert (found["resting"], found["usual_resting"]) == (48, 48)


def test_the_daily_check_suggests_last_nights_sleep(signed_in: TestClient, engine: Engine) -> None:
    _import(engine, hcw.full())
    check = _get(signed_in, "/api/daily-check")
    assert (check["suggested_sleep"], check["band_asleep_min"]) == ("good", 440)
    assert check["answers"] is None  # only a suggestion: nothing is answered for you


def test_strangers_get_nothing(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/health").status_code == 401
