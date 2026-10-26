"""/api/equipment: the home kit, saved whole, what an item unlocks, and the locks it puts on
/api/progress (ADR-0071). Owner-only."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Exercise
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
KB8: dict[str, Any] = {"kit": "kettlebell", "kg": 8}
STOOLS: dict[str, Any] = {"kit": "bench", "note": "two stools"}


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


def test_the_kit_starts_unlisted(signed_in: TestClient) -> None:
    found = signed_in.get("/api/equipment").json()
    assert (found["listed"], found["saved_at"], found["items"]) == (False, None, [])
    kinds = {k["kit"]: k["name"] for k in found["kinds"]}
    assert kinds["dip bars"] == "dip bars or two chairs"
    assert kinds["bench"] == "bench, stools or bed to lie on"


def test_the_whole_list_is_saved_and_read_back(signed_in: TestClient) -> None:
    body = {"items": [KB8, {"kit": "band", "resistance": "medium"}, STOOLS]}
    saved = signed_in.put("/api/equipment", json=body).json()
    assert saved["listed"] is True
    assert [i["label"] for i in saved["items"]] == [
        "8 kg kettlebell",
        "medium band",
        "bench, stools or bed to lie on",
    ]
    assert saved["items"][2]["note"] == "two stools"
    assert signed_in.get("/api/equipment").json()["items"] == saved["items"]
    emptied = signed_in.put("/api/equipment", json={"items": []}).json()
    assert (emptied["listed"], emptied["items"]) == (True, [])


@pytest.mark.parametrize(
    ("items", "reason"),
    [
        ([{"kit": "kettlebell"}], "kettlebell: say the weight in kg"),
        ([KB8, KB8], "8 kg kettlebell is listed twice"),
        ([{"kit": "band"}], "a band: say light, medium or heavy"),
    ],
)
def test_a_bad_list_is_refused_whole(
    signed_in: TestClient, items: list[dict[str, Any]], reason: str
) -> None:
    signed_in.put("/api/equipment", json={"items": [STOOLS]})
    refused = signed_in.put("/api/equipment", json={"items": items})
    assert refused.status_code == 422
    assert refused.json()["detail"] == reason
    assert [i["kit"] for i in signed_in.get("/api/equipment").json()["items"]] == ["bench"]


def test_unknown_kit_is_refused_by_the_schema(signed_in: TestClient) -> None:
    assert signed_in.put("/api/equipment", json={"items": [{"kit": "sofa"}]}).status_code == 422


def test_what_an_item_unlocks(signed_in: TestClient) -> None:
    signed_in.put("/api/equipment", json={"items": [KB8, {"kit": "pull-up bar"}]})
    found = signed_in.get("/api/equipment/unlocks", params={"add": "kettlebell:16"}).json()
    assert found["item"] == "16 kg kettlebell"
    assert found["summary"] == f"16 kg kettlebell: {len(found['steps'])} new steps"
    assert {"exercise": "Kettlebell swing", "slug": "kb-swing", "step": "Heavier kettlebell"} in (
        found["steps"]
    )
    nothing = signed_in.get("/api/equipment/unlocks", params={"add": "rings"}).json()
    assert (nothing["summary"], nothing["steps"]) == ("rings: no new steps", [])
    wheel = signed_in.get("/api/equipment/unlocks", params={"add": "ab wheel"}).json()
    assert wheel["summary"] == "ab wheel: 2 new steps"


def test_a_bad_item_to_unlock_is_refused(signed_in: TestClient) -> None:
    refused = signed_in.get("/api/equipment/unlocks", params={"add": "kettlebell:heavy"})
    assert refused.status_code == 422


def test_progress_shows_the_locks_once_a_kit_is_listed(
    signed_in: TestClient, engine: Engine
) -> None:
    signed_in.put("/api/equipment", json={"items": [KB8]})
    found = signed_in.get("/api/progress").json()
    assert found["kit_listed"] is True
    swing = next(s for s in found["standings"] if s["slug"] == "kb-swing")
    assert [r["missing"] for r in swing["ladder"]] == [[], [], ["a 16 kg kettlebell"]]
    pull_up = next(s for s in found["standings"] if s["slug"] == "pull-up")
    assert all(r["missing"] for r in pull_up["ladder"])  # no bar listed
    with make_session_factory(engine, user_id=OWNER)() as bound:
        heavier = bound.scalars(select(Exercise).where(Exercise.slug == "kb-swing")).one()
        step = heavier.ladder[2].id
    chosen = signed_in.post("/api/progress/kb-swing/level", json={"step_id": step}).json()
    assert chosen["outcome"] == "level_set"  # the person decides: allowed, with a warning
    assert chosen["warning"] == "Heavier kettlebell needs a 16 kg kettlebell, not in your kit."


def test_equipment_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/equipment").status_code == 401
        assert stranger.put("/api/equipment", json={"items": []}).status_code == 401
        assert stranger.get("/api/equipment/unlocks", params={"add": "rings"}).status_code == 401
