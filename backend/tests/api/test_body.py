"""/api/body (2-B, #142): body measurements, owner-only and never logged."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from structlog.testing import capture_logs

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.session import make_session_factory
from training_coach.domain.queue import local_date
from training_coach.services import auth
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


def test_the_kinds_come_with_units_and_ranges(signed_in: TestClient) -> None:
    kinds = signed_in.get("/api/body/kinds").json()
    assert [k["kind"] for k in kinds][:4] == ["bodyweight", "body_fat_scale", "waist", "neck"]
    heart = next(k for k in kinds if k["kind"] == "resting_hr")
    assert (heart["unit"], heart["decimals"]) == ("bpm", 0)
    waist = next(k for k in kinds if k["kind"] == "waist")
    assert waist["how"] == "Horizontal at the navel, relaxed."


def test_the_thigh_is_taken_at_the_persons_own_distance(signed_in: TestClient) -> None:
    def thigh() -> str:
        found = next(k for k in signed_in.get("/api/body/kinds").json() if k["kind"] == "thigh")
        return str(found["how"])

    assert "15 cm above the top of the kneecap" in thigh()
    signed_in.put("/api/account/body", json={"thigh_offset_cm": 12})
    assert "12 cm above the top of the kneecap" in thigh()


def test_the_guide_has_the_checklist_and_the_cadence(signed_in: TestClient) -> None:
    guide = signed_in.get("/api/body/guide").json()
    assert guide["checklist"][0].startswith("In the morning")
    assert "2 to 4 weeks" in guide["cadence"]


def test_a_day_is_saved_replaced_listed_and_deleted(signed_in: TestClient) -> None:
    today = local_date(datetime.now(UTC), Settings().tz)
    put = signed_in.put("/api/body", json={"values": {"bodyweight": 83.4, "waist": 85}})
    assert put.status_code == 200
    assert put.json() == {"warnings": []}
    signed_in.put("/api/body", json={"values": {"bodyweight": 83.1}})
    yesterday = (today - timedelta(days=1)).isoformat()
    signed_in.put("/api/body", json={"on": yesterday, "values": {"bodyweight": 83.9}})
    assert signed_in.get("/api/body").json() == [
        {"on": today.isoformat(), "kind": "bodyweight", "value": 83.1},
        {"on": today.isoformat(), "kind": "waist", "value": 85.0},
        {"on": yesterday, "kind": "bodyweight", "value": 83.9},
    ]
    assert signed_in.delete(f"/api/body/{yesterday}/bodyweight").status_code == 204
    assert signed_in.delete(f"/api/body/{yesterday}/bodyweight").status_code == 404
    assert len(signed_in.get("/api/body").json()) == 2


@pytest.mark.parametrize(
    "body",
    [
        {"values": {"waist": 820}},
        {"values": {}},
        {"values": {"height": 180}},
        {"on": "2099-01-01", "values": {"waist": 85}},
    ],
)
def test_wrong_values_are_refused(signed_in: TestClient, body: dict[str, object]) -> None:
    assert signed_in.put("/api/body", json=body).status_code == 422
    assert signed_in.get("/api/body").json() == []


def test_a_far_value_is_saved_with_a_warning(signed_in: TestClient) -> None:
    today = local_date(datetime.now(UTC), Settings().tz)
    before = today - timedelta(days=13)
    signed_in.put("/api/body", json={"on": before.isoformat(), "values": {"waist": 85}})
    put = signed_in.put("/api/body", json={"values": {"waist": 88.5, "neck": 39}})
    assert put.status_code == 200
    day = f"{before.day} {before:%b}" + ("" if before.year == today.year else f" {before.year}")
    assert put.json() == {
        "warnings": [f"Waist is 3.5 cm off your last ({day}): different landmark? Re-measure."]
    }
    assert len(signed_in.get("/api/body").json()) == 3  # saved all the same


def test_the_estimate_and_the_average_are_worked_out_on_read(signed_in: TestClient) -> None:
    today = local_date(datetime.now(UTC), Settings().tz).isoformat()
    signed_in.put("/api/body", json={"values": {"waist": 93, "neck": 39, "bodyweight": 83.4}})
    assert signed_in.get("/api/body/estimates").json() == []  # off by default
    settings = {"height_cm": 182, "thigh_offset_cm": 15, "body_fat_estimate": "navy_male"}
    assert signed_in.put("/api/account/body", json=settings).json() == settings
    assert signed_in.get("/api/body/estimates").json() == [{"on": today, "value": 20.9}]
    assert signed_in.get("/api/body/averages").json() == [{"on": today, "value": 83.4, "count": 1}]


def test_measurements_never_reach_the_logs(signed_in: TestClient) -> None:
    with capture_logs() as logs:
        signed_in.put("/api/body", json={"values": {"bodyweight": 83.7, "waist": 91.3}})
        signed_in.get("/api/body")
        signed_in.put("/api/body", json={"values": {"waist": 999.9}})  # refused
    text = repr(logs)
    for value in ("83.7", "91.3", "999.9", "837", "913"):
        assert value not in text


def test_measurements_need_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/body").status_code == 401
        assert stranger.get("/api/body/kinds").status_code == 401
        for path in ("/api/body/guide", "/api/body/estimates", "/api/body/averages"):
            assert stranger.get(path).status_code == 401, path
        assert stranger.put("/api/body", json={"values": {"waist": 85}}).status_code == 401
        assert stranger.delete("/api/body/2026-10-10/waist").status_code == 401
