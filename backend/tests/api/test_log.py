"""/api/log (ADR-0060): any day from today back to 14 days, any session, an extra, cardio or
an earlier rest day; and the question when the day already has its session."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from tests.api.test_cardio import ORIGIN, _plan_next
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import SessionProgress, SessionTemplate, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import auth, users
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

TODAY = local_date(datetime.now(UTC), Settings(environment="test").tz)


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


def _ago(days: int) -> date:
    return TODAY - timedelta(days=days)


def _ids(engine: Engine) -> dict[str, int]:
    with make_session_factory(engine)() as shared:
        return {t.slug: t.id for t in shared.scalars(select(SessionTemplate))}


def _pointer(engine: Engine) -> int | None:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        state = users.plan_state(bound)
        return state.next_template_id if state is not None else None


def _days(engine: Engine) -> dict[date, list[tuple[str | None, str]]]:
    """Each day's workouts as (session slug, status)."""
    slugs = {v: k for k, v in _ids(engine).items()}
    found: dict[date, list[tuple[str | None, str]]] = {}
    with make_session_factory(engine, user_id=OWNER)() as bound:
        for w in bound.scalars(select(Workout).order_by(Workout.id)):
            slug = slugs[w.template_id] if w.template_id is not None else None
            found.setdefault(w.local_date, []).append((slug, w.status))
    return found


def _token(n: int) -> str:
    return f"{n:02x}" * 16


def _legs(client: TestClient, engine: Engine, day: date, n: int, **more: Any) -> Any:
    """Every set of Legs at its target, for ``day``."""
    plan = client.get(
        "/api/log/plan", params={"day": day.isoformat(), "template_id": _ids(engine)["legs"]}
    ).json()
    sets = [
        {"item": i, "set_no": s + 1, "left": t}
        for i, item in enumerate(plan["items"])
        for s, t in enumerate(item["targets"])
    ]
    body = {
        "token": _token(n),
        "day": day.isoformat(),
        "what": "session",
        "template_id": _ids(engine)["legs"],
        "sets": sets,
        **more,
    }
    return client.post("/api/log", json=body)


def _rest(client: TestClient, day: date, n: int, **more: Any) -> Any:
    body = {"token": _token(n), "day": day.isoformat(), "what": "rest", **more}
    return client.post("/api/log", json=body)


def test_the_options_are_two_weeks_of_days_and_every_session(signed_in: TestClient) -> None:
    body = signed_in.get("/api/log").json()
    assert body["days"][0] == TODAY.isoformat()
    assert body["days"][-1] == _ago(14).isoformat()
    assert [s["name"] for s in body["sessions"]][:2] == ["Legs", "Recovery + posture"]
    assert "walk" in body["activities"]


def test_a_sessions_plan_has_its_exercises_and_targets(
    signed_in: TestClient, engine: Engine
) -> None:
    legs = _ids(engine)["legs"]
    body = signed_in.get("/api/log/plan", params={"day": _ago(2), "template_id": legs}).json()
    assert body["name"] == "Legs"
    assert body["items"][0]["name"] == "Jump squat"
    assert body["items"][0]["targets"]
    future = {"day": TODAY + timedelta(days=1), "template_id": legs}
    assert signed_in.get("/api/log/plan", params=future).status_code == 422
    missing = {"day": TODAY, "template_id": 9999}
    assert signed_in.get("/api/log/plan", params=missing).status_code == 404


def test_a_past_session_is_filed_on_its_day_and_catches_up(
    signed_in: TestClient, engine: Engine
) -> None:
    ids = _ids(engine)
    _plan_next(engine, "torso")
    answer = _legs(signed_in, engine, _ago(3), 1)
    assert answer.status_code == 200, answer.text
    assert answer.json()["already_saved"] is False
    assert _days(engine) == {_ago(3): [("legs", "done")]}
    assert _pointer(engine) == ids["recovery"]  # nothing later: the session after Legs
    again = _legs(signed_in, engine, _ago(3), 1)
    assert again.json()["already_saved"] is True


def test_the_8_october_scenario(signed_in: TestClient, engine: Engine) -> None:
    """Legs on day N, Legs backdated to N-1, then a rest day for N: the question shows N's
    Legs and offers to replace or move it; replacing leaves Legs counted once."""
    ids = _ids(engine)
    n = _ago(1)
    assert _legs(signed_in, engine, n, 1).status_code == 200
    assert _legs(signed_in, engine, _ago(2), 2).status_code == 200
    assert _pointer(engine) == ids["recovery"]
    asked = _rest(signed_in, n, 3)
    assert asked.status_code == 409
    clash = asked.json()["detail"]
    assert clash["day"] == n.isoformat()
    assert clash["moving"] is False
    [there] = clash["recorded"]
    assert there["name"] == "Legs"
    assert there["summary"].startswith("25 sets: ")
    assert _days(engine)[n] == [("legs", "done")]  # nothing saved yet
    seen = [there["workout_id"]]
    replaced = _rest(signed_in, n, 3, resolution="replace", seen=seen)
    assert replaced.status_code == 200, replaced.text
    assert _days(engine) == {_ago(2): [("legs", "done")], n: [(None, "rest")]}
    assert _pointer(engine) == ids["recovery"]
    undo = signed_in.get("/api/today/undo").json()["offer"]
    assert undo["what"].endswith("which replaced Legs")
    assert signed_in.post("/api/today/undo", json={"event_id": undo["event_id"]}).is_success
    assert _days(engine)[n] == [("legs", "done")]


def test_moving_the_old_session_to_another_day(signed_in: TestClient, engine: Engine) -> None:
    n = _ago(1)
    _legs(signed_in, engine, n, 1)
    seen = [r["workout_id"] for r in _rest(signed_in, n, 2).json()["detail"]["recorded"]]
    moved = _rest(signed_in, n, 2, resolution=f"move:{_ago(4).isoformat()}", seen=seen)
    assert moved.status_code == 200, moved.text
    assert _days(engine) == {_ago(4): [("legs", "done")], n: [(None, "rest")]}


def test_moving_onto_a_day_with_a_session_asks_for_another(
    signed_in: TestClient, engine: Engine
) -> None:
    _legs(signed_in, engine, _ago(4), 1)
    _legs(signed_in, engine, _ago(1), 2)
    seen = [r["workout_id"] for r in _rest(signed_in, _ago(1), 3).json()["detail"]["recorded"]]
    asked = _rest(signed_in, _ago(1), 3, resolution=f"move:{_ago(4).isoformat()}", seen=seen)
    assert asked.status_code == 409
    assert (asked.json()["detail"]["day"], asked.json()["detail"]["moving"]) == (
        _ago(4).isoformat(),
        True,
    )
    future = _rest(signed_in, _ago(1), 3, resolution=f"move:{TODAY + timedelta(days=1)}", seen=seen)
    assert future.status_code == 422


def test_an_answer_about_what_isnt_there_any_more_asks_again(
    signed_in: TestClient, engine: Engine
) -> None:
    _legs(signed_in, engine, _ago(1), 1)
    asked = _rest(signed_in, _ago(1), 2, resolution="replace", seen=[12345])
    assert asked.status_code == 409
    assert asked.json()["detail"]["recorded"][0]["name"] == "Legs"
    assert _days(engine)[_ago(1)] == [("legs", "done")]


@pytest.mark.parametrize("answer", ["delete", "move:tomorrow", "move:2026-02-30"])
def test_an_answer_that_isnt_one_is_refused(
    signed_in: TestClient, engine: Engine, answer: str
) -> None:
    _legs(signed_in, engine, _ago(1), 1)
    assert _rest(signed_in, _ago(1), 2, resolution=answer, seen=[1]).status_code == 422


def test_add_keeps_both(signed_in: TestClient, engine: Engine) -> None:
    _legs(signed_in, engine, _ago(1), 1)
    seen = [r["workout_id"] for r in _rest(signed_in, _ago(1), 2).json()["detail"]["recorded"]]
    assert _rest(signed_in, _ago(1), 2, resolution="add", seen=seen).status_code == 200
    assert _days(engine)[_ago(1)] == [("legs", "done"), (None, "rest")]


def test_another_session_today_leaves_the_queue_where_it_is(
    signed_in: TestClient, engine: Engine
) -> None:
    """Legs is next; Arms done today instead is out of turn, so Legs stays next (ADR-0016)."""
    legs = _plan_next(engine, "legs")
    arms = _ids(engine)["arms"]
    plan = signed_in.get("/api/log/plan", params={"day": TODAY, "template_id": arms}).json()
    body = {
        "token": _token(1),
        "day": TODAY.isoformat(),
        "what": "session",
        "template_id": arms,
        "sets": [{"item": 0, "set_no": 1, "left": plan["items"][0]["targets"][0]}],
    }
    answer = signed_in.post("/api/log", json=body)
    assert answer.status_code == 200, answer.text
    assert answer.json()["next_session"] == "Legs"
    assert _days(engine) == {TODAY: [("arms", "done")]}
    assert _pointer(engine) == legs


def test_the_queues_session_picked_today_moves_it_on(signed_in: TestClient, engine: Engine) -> None:
    _plan_next(engine, "legs")
    assert _legs(signed_in, engine, TODAY, 1).status_code == 200
    assert _pointer(engine) == _ids(engine)["recovery"]


def test_an_extra_completes_nothing(signed_in: TestClient, engine: Engine) -> None:
    legs = _plan_next(engine, "legs")
    assert _legs(signed_in, engine, TODAY, 1, what="extra").status_code == 200
    assert _legs(signed_in, engine, _ago(2), 2, what="extra").status_code == 200
    assert _days(engine) == {TODAY: [(None, "done")], _ago(2): [(None, "done")]}
    assert _pointer(engine) == legs


def test_a_rest_day_today_is_rest_today(signed_in: TestClient) -> None:
    answer = _rest(signed_in, TODAY, 1)
    assert answer.status_code == 422
    assert "Rest today" in answer.json()["detail"]


def test_past_cardio_is_an_extra_with_what_it_was(signed_in: TestClient, engine: Engine) -> None:
    _legs(signed_in, engine, _ago(2), 1)
    body = {
        "token": _token(2),
        "day": _ago(2).isoformat(),
        "what": "cardio",
        "cardio": "hiit",
        "value": 8,
        "activity": "bike",
    }
    assert signed_in.post("/api/log", json=body).status_code == 200  # no question: an extra
    assert _days(engine)[_ago(2)] == [("legs", "done"), (None, "done")]
    no_value = {**body, "token": _token(3), "value": None}
    assert signed_in.post("/api/log", json=no_value).status_code == 422


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"day": (TODAY + timedelta(days=1)).isoformat()}, 422),
        ({"day": _ago(15).isoformat()}, 422),
        ({"sets": []}, 422),
        ({"template_id": None}, 422),
        ({"template_id": 9999}, 422),
        ({"sets": [{"item": 99, "set_no": 1, "left": 5}]}, 422),
    ],
)
def test_a_log_that_cant_be_saved_says_why(
    signed_in: TestClient, engine: Engine, change: dict[str, Any], status: int
) -> None:
    legs = _ids(engine)["legs"]
    body = {
        "token": _token(1),
        "day": _ago(1).isoformat(),
        "what": "session",
        "template_id": legs,
        "sets": [{"item": 0, "set_no": 1, "left": 5}],
        **change,
    }
    assert signed_in.post("/api/log", json=body).status_code == status
    assert _days(engine) == {}


def test_saving_an_earlier_guided_session_asks_too(signed_in: TestClient, engine: Engine) -> None:
    """A guided session left unsaved on a day that got its session another way since."""
    ids = _ids(engine)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        bound.add(
            SessionProgress(
                local_date=_ago(1),
                template_id=ids["legs"],
                token=_token(9),
                sets=[{"item": 0, "set_no": 1, "left": 6, "right": None}],
            )
        )
    _rest(signed_in, _ago(1), 1)
    asked = signed_in.post("/api/session/save", json={"day": _ago(1).isoformat()})
    assert asked.status_code == 409
    seen = [r["workout_id"] for r in asked.json()["detail"]["recorded"]]
    body = {"day": _ago(1).isoformat(), "resolution": "add", "seen": seen}
    assert signed_in.post("/api/session/save", json=body).status_code == 200
    assert _days(engine)[_ago(1)] == [(None, "rest"), ("legs", "done")]
