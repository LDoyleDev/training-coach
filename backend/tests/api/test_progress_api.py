"""/api/progress: each exercise's standing for the web app, owner-only."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from tests.routes import api_routes
from training_coach.api.app import create_app
from training_coach.api.auth import owner
from training_coach.config import Settings
from training_coach.db.models import Event, Exercise, SetLog, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.services import auth, user_settings, users
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


def test_every_planned_exercise_is_listed_with_its_step(signed_in: TestClient) -> None:
    found = signed_in.get("/api/progress").json()
    assert isinstance(found["today"], str)
    standings = found["standings"]
    assert standings[0]["exercise"] == "Jump squat"  # the first in the Legs session
    first = standings[0]
    assert (first["step_number"], first["last"], first["best_set"], first["trend"]) == (
        1,
        [],
        None,
        [],
    )
    assert first["status"] == "hold"
    assert {s["unit"] for s in standings} >= {"reps", "seconds", "minutes"}
    assert not any(s["retired"] for s in standings)  # retired ones only show with history


def test_progress_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/progress").status_code == 401
        assert stranger.get("/api/progress/times").status_code == 401


MOVES = ("move-up", "not-yet", "level")


def _pull_up(engine: Engine) -> dict[str, Any]:
    """Pull-up's id, current step and ladder (step ids, easiest first)."""
    with make_session_factory(engine, user_id=OWNER)() as bound:
        exercise = bound.scalars(select(Exercise).where(Exercise.slug == "pull-up")).one()
        state = users.exercise_state(bound, exercise.id)
        assert state is not None
        return {
            "id": exercise.id,
            "step_id": state.ladder_step_id,
            "ladder": [s.id for s in exercise.ladder],
        }


def _ready(engine: Engine) -> None:
    """Two sessions at the top of Pull-up's range: ready to move up."""
    pull_up = _pull_up(engine)
    with make_session_factory(engine, user_id=OWNER)() as bound:
        for days_ago in (3, 1):
            workout = Workout(
                local_date=datetime.now(UTC).date() - timedelta(days=days_ago),
                template_id=None,
                status=WorkoutStatus.DONE,
            )
            workout.sets = [
                SetLog(
                    exercise_id=pull_up["id"],
                    ladder_step_id=pull_up["step_id"],
                    set_no=n,
                    side=Side.BOTH,
                    value=12,
                )
                for n in range(1, 5)
            ]
            bound.add(workout)
        bound.commit()


def _events(engine: Engine, kind: str) -> list[dict[str, Any]]:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        return list(bound.scalars(select(Event.payload).where(Event.kind == kind)))


def test_the_moves_are_owner_only(engine: Engine) -> None:
    """ADR-0036: each new route declares its access: behind ``owner``, not public."""
    app = create_app(Settings(environment="test", database_url=str(engine.url)))
    found = dict(api_routes(app))
    for move in MOVES:
        route = found[f"/api/progress/{{slug}}/{move}"]
        assert owner in {dep.call for dep in route.dependant.dependencies}, move


def test_a_stranger_cannot_move_anything(engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    before = _pull_up(engine)
    bodies = (
        {"from_step_id": before["step_id"]},
        {"step_id": before["step_id"]},
        {"step_id": before["ladder"][0]},
    )
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        for move, body in zip(MOVES, bodies, strict=True):
            assert stranger.post(f"/api/progress/pull-up/{move}", json=body).status_code == 401
    assert _pull_up(engine)["step_id"] == before["step_id"]
    assert _events(engine, "progress.level_set") == []


def test_the_standing_carries_what_the_plan_page_needs(
    signed_in: TestClient, engine: Engine
) -> None:
    found = signed_in.get("/api/progress").json()
    assert found["strength_block"] is False
    pull_up = next(s for s in found["standings"] if s["slug"] == "pull-up")
    expected = _pull_up(engine)
    assert pull_up["step_id"] == expected["step_id"]
    assert [r["id"] for r in pull_up["ladder"]] == expected["ladder"]
    assert pull_up["ladder"][0] == {
        "id": expected["ladder"][0],
        "name": "Slow negatives",
        "cue": None,
    }


def test_move_up_when_ready_and_a_second_press_changes_nothing(
    signed_in: TestClient, engine: Engine
) -> None:
    _ready(engine)
    start = _pull_up(engine)
    body = {"from_step_id": start["step_id"]}
    moved = signed_in.post("/api/progress/pull-up/move-up", json=body)
    assert moved.json() == {"outcome": "moved", "exercise": "Pull-up", "step": "Pause at top"}
    again = signed_in.post("/api/progress/pull-up/move-up", json=body).json()
    assert again["outcome"] == "already_moved"
    assert _pull_up(engine)["step_id"] == start["ladder"][2]
    assert _events(engine, "progress.moved_up") == [
        {
            "exercise_id": start["id"],
            "from_step_id": start["step_id"],
            "to_step_id": start["ladder"][2],
        }
    ]


def test_a_forged_or_unready_move_changes_nothing(signed_in: TestClient, engine: Engine) -> None:
    start = _pull_up(engine)
    url = "/api/progress/pull-up/move-up"
    not_ready = signed_in.post(url, json={"from_step_id": start["step_id"]})
    assert not_ready.json()["outcome"] == "not_ready"
    _ready(engine)
    forged = signed_in.post(url, json={"from_step_id": start["ladder"][0]})
    assert forged.json()["outcome"] == "already_moved"
    unknown = signed_in.post("/api/progress/no-such/move-up", json={"from_step_id": 1})
    assert unknown.status_code == 404
    assert _pull_up(engine)["step_id"] == start["step_id"]
    assert _events(engine, "progress.moved_up") == []


def test_move_up_waits_in_a_strength_block(signed_in: TestClient, engine: Engine) -> None:
    """ADR-0028: the web holds Move up as the bot does; choosing a level is still allowed."""
    _ready(engine)
    with make_session_factory(engine, user_id=OWNER)() as bound:
        user_settings.update(bound, blocks=True, today=datetime.now(UTC).date())
        bound.commit()
    start = _pull_up(engine)
    assert signed_in.get("/api/progress").json()["strength_block"] is True
    url = "/api/progress/pull-up/move-up"
    held = signed_in.post(url, json={"from_step_id": start["step_id"]})
    assert held.json()["outcome"] == "strength_block"
    assert _pull_up(engine)["step_id"] == start["step_id"]
    by_hand = signed_in.post("/api/progress/pull-up/level", json={"step_id": start["ladder"][2]})
    assert by_hand.json()["outcome"] == "level_set"


def test_not_yet_is_recorded_once_and_not_from_a_stale_page(
    signed_in: TestClient, engine: Engine
) -> None:
    _ready(engine)
    start = _pull_up(engine)
    url = "/api/progress/pull-up/not-yet"
    stayed = signed_in.post(url, json={"step_id": start["step_id"]})
    assert stayed.json() == {"outcome": "stayed", "exercise": "Pull-up", "step": "Strict pull-up"}
    signed_in.post("/api/progress/pull-up/level", json={"step_id": start["ladder"][0]})
    stale = signed_in.post(url, json={"step_id": start["step_id"]})
    assert stale.json()["outcome"] == "already_moved"
    assert _events(engine, "progress.not_yet") == [
        {"exercise_id": start["id"], "step_id": start["step_id"]}
    ]


def test_a_level_can_be_chosen_down_and_up(signed_in: TestClient, engine: Engine) -> None:
    start = _pull_up(engine)
    first, top = start["ladder"][0], start["ladder"][-1]
    url = "/api/progress/pull-up/level"
    down = signed_in.post(url, json={"step_id": first}).json()
    assert down == {"outcome": "level_set", "exercise": "Pull-up", "step": "Slow negatives"}
    up = signed_in.post(url, json={"step_id": top}).json()
    assert up["step"] == "Weighted backpack"
    same = signed_in.post(url, json={"step_id": top}).json()
    assert same["outcome"] == "same_level"
    assert _pull_up(engine)["step_id"] == top
    assert _events(engine, "progress.level_set") == [
        {"exercise_id": start["id"], "from_step_id": start["step_id"], "to_step_id": first},
        {"exercise_id": start["id"], "from_step_id": first, "to_step_id": top},
    ]


def test_a_step_of_another_exercise_is_refused(signed_in: TestClient, engine: Engine) -> None:
    start = _pull_up(engine)
    with make_session_factory(engine, user_id=OWNER)() as bound:
        dip = bound.scalars(select(Exercise).where(Exercise.slug == "dip")).one()
        dip_step = dip.ladder[0].id
    for move in ("level", "not-yet"):
        refused = signed_in.post(f"/api/progress/pull-up/{move}", json={"step_id": dip_step})
        assert refused.status_code == 422, move
    assert _pull_up(engine)["step_id"] == start["step_id"]
    assert _events(engine, "progress.level_set") == []
