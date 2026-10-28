"""PUT /api/session/level (ADR-0080): change an exercise's level during today's session."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import SessionProgress
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, guided, session_levels
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


def _jump(today: dict[str, Any]) -> dict[str, Any]:
    item = next(i for i in today["session"]["items"] if i["slug"] == "jump-squat")
    return {**item["level"], "step": item["step"], "baseline": item["baseline"]}


def _change(client: TestClient, step_id: int, scope: str, revision: int = 0) -> Any:
    template = client.get("/api/session/today").json()["session"]["template_id"]
    body = {
        "template_id": template,
        "revision": revision,
        "slug": "jump-squat",
        "step_id": step_id,
        "scope": scope,
    }
    return client.put("/api/session/level", json=body)


def test_each_ladder_exercise_comes_with_its_ladder(signed_in: TestClient) -> None:
    today = signed_in.get("/api/session/today").json()
    jump = _jump(today)
    names = [r["name"] for r in jump["ladder"]]
    assert names == ["Bodyweight, full rest", "Pause at bottom, then jump", "Holding 8 kg"]
    assert jump["step_id"] == jump["ladder"][0]["id"]
    assert jump["for_today"] is False
    # A step for each level or none at all: an exercise with one step has no level to change.
    assert all(
        i["level"] is None or len(i["level"]["ladder"]) > 1 for i in today["session"]["items"]
    )


def test_for_today_changes_the_step_and_a_reload_keeps_it(signed_in: TestClient) -> None:
    pause = _jump(signed_in.get("/api/session/today").json())["ladder"][1]
    answer = _change(signed_in, pause["id"], "today")
    assert answer.status_code == 200
    body = answer.json()
    assert body["warning"] is None
    jump = _jump(body["today"])
    assert (jump["step"], jump["for_today"], jump["baseline"]) == (pause["name"], True, True)
    assert body["today"]["progress"]["revision"] == 2
    again = _jump(signed_in.get("/api/session/today").json())  # a reload
    assert (again["step_id"], again["for_today"]) == (pause["id"], True)
    standing = next(
        s for s in signed_in.get("/api/progress").json()["standings"] if s["slug"] == "jump-squat"
    )
    assert standing["step"] == "Bodyweight, full rest"  # the level stays


def test_the_saved_screen_says_the_step_the_sets_were_done_at(signed_in: TestClient) -> None:
    pause = _jump(signed_in.get("/api/session/today").json())["ladder"][1]
    today = _change(signed_in, pause["id"], "today").json()["today"]
    jump = next(
        i for i, item in enumerate(today["session"]["items"]) if item["slug"] == "jump-squat"
    )
    kept = {
        "template_id": today["session"]["template_id"],
        "place": today["session"]["place"],
        "revision": today["progress"]["revision"],
        "position": 1,
        "sets": [{"item": jump, "set_no": 1, "left": 6}],
    }
    assert signed_in.put("/api/session/progress", json=kept).status_code == 200
    saved = signed_in.post("/api/session/save", json={})
    assert saved.status_code == 200
    assert saved.json()["levels"] == [{"exercise": "Jump squat", "steps": [pause["name"]]}]


def test_from_now_on_changes_the_level(signed_in: TestClient) -> None:
    pause = _jump(signed_in.get("/api/session/today").json())["ladder"][1]
    answer = _change(signed_in, pause["id"], "from_now_on")
    assert answer.status_code == 200
    jump = _jump(answer.json()["today"])
    assert (jump["step"], jump["for_today"]) == (pause["name"], False)
    standing = next(
        s for s in signed_in.get("/api/progress").json()["standings"] if s["slug"] == "jump-squat"
    )
    assert standing["step_id"] == pause["id"]


def test_a_stale_browser_or_another_session_is_a_conflict(signed_in: TestClient) -> None:
    pause = _jump(signed_in.get("/api/session/today").json())["ladder"][1]
    assert _change(signed_in, pause["id"], "today").status_code == 200
    assert _change(signed_in, pause["id"], "today", revision=1).status_code == 409
    body = {"template_id": 99999, "slug": "jump-squat", "step_id": pause["id"], "scope": "today"}
    assert signed_in.put("/api/session/level", json=body).status_code == 409


def test_a_step_off_the_ladder_is_refused(signed_in: TestClient) -> None:
    tibialis = next(
        i
        for i in signed_in.get("/api/session/today").json()["session"]["items"]
        if i["slug"] == "tibialis-raise"
    )
    answer = _change(signed_in, tibialis["level"]["step_id"], "today")
    assert answer.status_code == 422
    assert answer.json()["detail"] == "that step isn't on this exercise's ladder"


def test_strangers_are_refused(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        body = {"template_id": 1, "slug": "jump-squat", "step_id": 1, "scope": "today"}
        assert client.put("/api/session/level", json=body).status_code == 401


def test_a_refused_change_writes_nothing(
    signed_in: TestClient, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A change refused after something was written leaves nothing behind: the refusal is
    raised inside the request's transaction, which rolls back."""
    pause = _jump(signed_in.get("/api/session/today").json())["ladder"][1]
    assert _change(signed_in, pause["id"], "today", revision=3).status_code == 409

    def written_then_refused(session: Session, plan: guided.Guided, *_: object) -> str:
        session.add(
            SessionProgress(local_date=plan.day, template_id=plan.template_id, token="ab" * 16)
        )
        session.flush()
        return guided.STALE

    monkeypatch.setattr(session_levels, "change", written_then_refused)
    assert _change(signed_in, pause["id"], "today").status_code == 409
    with make_session_factory(engine, user_id=OWNER)() as bound:
        assert bound.scalars(select(SessionProgress)).all() == []
    assert signed_in.get("/api/session/today").json()["progress"] is None
