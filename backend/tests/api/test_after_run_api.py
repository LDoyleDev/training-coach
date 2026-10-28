"""The block after a run over the API (ADR-0066): the run logged in one step, then the rest of
the session guided and saved into the same workout."""

from collections.abc import Iterator
from datetime import UTC, datetime
from importlib.resources import files

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import SessionTemplate, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, users
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
CARDIO_CORE = """[[sessions]]
slug = "moderate-cardio"
type = "conditioning"
name = "Cardio + core"
focus = "~35 min at 75-80% effort, then core"
items = [
  { exercise = "moderate-cardio", sets = 1, rep_min = 30, rep_max = 40 },
  { exercise = "hanging-raise", sets = 2, rep_min = 8, rep_max = 15, pair = 1 },
  { exercise = "back-extension", sets = 2, rep_min = 10, rep_max = 15, pair = 1 },
]

"""


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    text = files("training_coach.seed").joinpath("plan.toml").read_text(encoding="utf-8")
    start = text.index('[[sessions]]\nslug = "moderate-cardio"')
    end = text.index("[[sessions]]", start + 1)
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan(text[:start] + CARDIO_CORE + text[end:]))
    with make_session_factory(engine, user_id=OWNER)() as bound:
        cardio_day = bound.scalars(
            select(SessionTemplate).where(SessionTemplate.slug == "moderate-cardio")
        ).one()
        state = users.plan_state(bound)
        assert state is not None
        state.next_template_id = cardio_day.id
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


def test_the_run_then_the_block_after_it(signed_in: TestClient, engine: Engine) -> None:
    before = signed_in.get("/api/session/today").json()["session"]
    assert (before["name"], before["after_run"]) == ("Cardio + core", False)
    assert len(before["items"]) == 3
    planned = signed_in.get("/api/cardio").json()["planned"]
    assert (planned["kind"], planned["session"]) == ("moderate-cardio", "Cardio + core")
    run = signed_in.post(
        "/api/cardio", json={"token": "ab" * 16, "kind": "moderate-cardio", "value": 35}
    )
    assert run.status_code == 200
    run_id = run.json()["workout_id"]
    assert signed_in.get("/api/cardio").json()["planned"] is None  # the run is logged

    after = signed_in.get("/api/session/today").json()["session"]
    assert after["after_run"]
    assert [i["slug"] for i in after["items"]] == ["hanging-raise", "back-extension"]
    assert after["usual_minutes"] is None
    sets = [{"item": s["item"], "set_no": s["set_no"], "left": 10} for s in after["order"]]
    kept = signed_in.put(
        "/api/session/progress",
        json={
            "template_id": after["template_id"],
            "place": after["place"],
            "position": len(sets),
            "sets": sets,
        },
    )
    assert kept.status_code == 200
    saved = signed_in.post("/api/session/save", json={})
    assert saved.status_code == 200
    assert (saved.json()["workout_id"], saved.json()["already_saved"]) == (run_id, False)
    assert signed_in.get("/api/session/today").json()["session"] is None
    with make_session_factory(engine, user_id=OWNER)() as bound:
        workout = bound.get_one(Workout, run_id)
        assert len(workout.sets) == 5  # the run and four sets after it
