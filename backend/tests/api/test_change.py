"""/api/today (ux-flow-plan C2, C3): Rest today, Push, Swap and Undo on the web, owner-only."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import SessionTemplate, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import auth, users
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"


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


def _ids(engine: Engine) -> dict[str, int]:
    with make_session_factory(engine)() as shared:
        return {t.slug: t.id for t in shared.scalars(select(SessionTemplate))}


def _shown(client: TestClient) -> Any:
    return client.get("/api/session/today").json()["session"]


def _pointer(engine: Engine) -> int | None:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        state = users.plan_state(bound)
        assert state is not None
        return state.next_template_id


def _workouts(engine: Engine) -> list[tuple[int | None, str]]:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        return [(w.template_id, w.status) for w in bound.scalars(select(Workout))]


def test_rest_today_holds_the_session_and_offers_undo(
    signed_in: TestClient, engine: Engine
) -> None:
    legs = _shown(signed_in)["template_id"]
    body = signed_in.post("/api/today/rest", json={"template_id": legs}).json()
    assert (body["session"], body["advanced"]) == ("Legs", False)
    assert body["today"]["session"] is None  # nothing left today: it waits for tomorrow
    assert body["undo"]["what"] == "the rest day for Legs"
    assert _workouts(engine) == [(legs, WorkoutStatus.SKIPPED)]
    assert _pointer(engine) == legs


def test_rest_on_the_optional_rest_session_counts_it_done(
    signed_in: TestClient, engine: Engine
) -> None:
    recovery = _ids(engine)["recovery"]
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        state = users.plan_state(bound)
        assert state is not None
        state.next_template_id = recovery
    body = signed_in.post("/api/today/rest", json={"template_id": recovery}).json()
    assert body["advanced"] is True
    assert _pointer(engine) != recovery


def test_push_to_tomorrow_then_undo_brings_the_session_back(
    signed_in: TestClient, engine: Engine
) -> None:
    legs = _shown(signed_in)["template_id"]
    pushed = signed_in.post("/api/today/push", json={"template_id": legs}).json()
    assert pushed["session"] == "Legs"
    assert pushed["today"]["session"] is None
    offer = signed_in.get("/api/today/undo").json()
    assert offer == {"offer": pushed["undo"], "refused": None}
    assert offer["offer"]["what"] == "moving Legs to tomorrow"

    undone = signed_in.post("/api/today/undo", json={"event_id": offer["offer"]["event_id"]})
    assert undone.status_code == 200
    assert undone.json()["what"] == "moving Legs to tomorrow"
    assert undone.json()["next_session"] == "Legs"
    assert undone.json()["today"]["session"]["name"] == "Legs"
    assert _workouts(engine) == []


def test_swap_offers_the_next_session_and_any_other(signed_in: TestClient, engine: Engine) -> None:
    ids = _ids(engine)
    found = signed_in.get("/api/today/choices").json()
    assert found["template_id"] == ids["legs"]
    assert found["next"] == {"template_id": ids["recovery"], "name": "Recovery + posture"}
    assert ids["legs"] not in [c["template_id"] for c in found["others"]]
    assert len(found["others"]) == len(ids) - 1


def test_doing_the_next_one_first_swaps_the_queue(signed_in: TestClient, engine: Engine) -> None:
    ids = _ids(engine)
    body = signed_in.post("/api/today/next", json={"template_id": ids["legs"]}).json()
    assert body["session"] == "Recovery + posture"
    assert body["today"]["session"]["template_id"] == ids["recovery"]
    assert body["undo"]["what"] == "doing Recovery + posture before Legs"
    assert _pointer(engine) == ids["recovery"]


def test_picking_another_session_shows_it_and_keeps_the_queue(
    signed_in: TestClient, engine: Engine
) -> None:
    ids = _ids(engine)
    body = {"template_id": ids["legs"], "picked_id": ids["torso"]}
    picked = signed_in.post("/api/today/pick", json=body).json()
    assert picked["today"]["session"]["name"] == "Torso + neck"
    assert _pointer(engine) == ids["legs"]

    # After a pick, Swap lists the planned session to go back to, and no "next first".
    found = signed_in.get("/api/today/choices").json()
    assert found["next"] is None
    assert ids["legs"] in [c["template_id"] for c in found["others"]]
    back = {"template_id": ids["torso"], "picked_id": ids["legs"]}
    assert signed_in.post("/api/today/pick", json=back).json()["session"] == "Legs"
    next_after_pick = signed_in.post("/api/today/next", json={"template_id": ids["legs"]})
    assert next_after_pick.status_code == 200


def test_rest_after_a_pick_rests_the_planned_session(signed_in: TestClient, engine: Engine) -> None:
    ids = _ids(engine)
    signed_in.post("/api/today/pick", json={"template_id": ids["legs"], "picked_id": ids["hiit"]})
    body = signed_in.post("/api/today/rest", json={"template_id": ids["hiit"]}).json()
    assert body["session"] == "Legs"
    assert body["today"]["session"] is None


@pytest.mark.parametrize("path", ["/api/today/rest", "/api/today/push", "/api/today/next"])
def test_a_change_from_an_out_of_date_page_is_a_conflict(
    signed_in: TestClient, engine: Engine, path: str
) -> None:
    stale = _ids(engine)["torso"]  # the page shows a session that isn't today's any more
    answer = signed_in.post(path, json={"template_id": stale})
    assert answer.status_code == 409
    assert _workouts(engine) == []
    assert _pointer(engine) == _ids(engine)["legs"]


def test_picking_an_unknown_session_is_a_conflict(signed_in: TestClient, engine: Engine) -> None:
    body = {"template_id": _ids(engine)["legs"], "picked_id": 999}
    assert signed_in.post("/api/today/pick", json=body).status_code == 409


def test_nothing_to_swap_once_today_is_rested(signed_in: TestClient, engine: Engine) -> None:
    legs = _ids(engine)["legs"]
    signed_in.post("/api/today/rest", json={"template_id": legs})
    assert signed_in.get("/api/today/choices").status_code == 409
    assert signed_in.post("/api/today/rest", json={"template_id": legs}).status_code == 409


def test_nothing_to_undo_says_why(signed_in: TestClient) -> None:
    body = signed_in.get("/api/today/undo").json()
    assert body["offer"] is None
    assert body["refused"].startswith("Nothing to undo")


def test_an_old_undo_cannot_take_back_a_newer_change(signed_in: TestClient, engine: Engine) -> None:
    """ADR-0048: the confirm names its change; a newer one since makes it a conflict."""
    ids = _ids(engine)
    swapped = signed_in.post("/api/today/next", json={"template_id": ids["legs"]}).json()
    old = swapped["undo"]["event_id"]
    signed_in.post("/api/today/push", json={"template_id": ids["recovery"]})
    answer = signed_in.post("/api/today/undo", json={"event_id": old})
    assert answer.status_code == 409
    assert "Something changed" in answer.json()["detail"]
    assert _pointer(engine) == ids["recovery"]


def test_changing_today_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        for path in ("/api/today/rest", "/api/today/push", "/api/today/next"):
            assert stranger.post(path, json={"template_id": 1}).status_code == 401
        body = {"template_id": 1, "picked_id": 2}
        assert stranger.post("/api/today/pick", json=body).status_code == 401
        assert stranger.get("/api/today/choices").status_code == 401
        assert stranger.get("/api/today/undo").status_code == 401
        assert stranger.post("/api/today/undo", json={"event_id": 1}).status_code == 401
