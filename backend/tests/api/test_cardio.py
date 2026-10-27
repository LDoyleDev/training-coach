"""/api/cardio (ux-flow-plan A1-A3): cardio logged in one step, planned or extra."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Event, SessionTemplate, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, cardio, undo, users, workout_log
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
TOKEN = "ab" * 16  # a log token, not a secret
BERLIN = Settings().tz


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


def _plan_next(engine: Engine, slug: str) -> int:
    """Point the queue at the session ``slug``."""
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        template = bound.scalars(select(SessionTemplate).where(SessionTemplate.slug == slug)).one()
        plan = users.plan_state(bound)
        assert plan is not None
        plan.next_template_id = template.id
        return template.id


def _workouts(engine: Engine) -> list[tuple[int | None, str | None, int]]:
    """Each workout as (template, activity, the first set's value)."""
    with make_session_factory(engine, user_id=OWNER)() as bound:
        return [
            (w.template_id, w.activity, w.sets[0].value) for w in bound.scalars(select(Workout))
        ]


def test_a_planned_zone2_day_offers_done_as_planned(signed_in: TestClient, engine: Engine) -> None:
    _plan_next(engine, "zone2")
    body = signed_in.get("/api/cardio").json()
    assert body["planned"] == {"kind": "zone2", "session": "Long zone 2", "target": 45}
    assert "walk" in body["activities"]
    nothing = dict.fromkeys(("below_zone1", "zone1", "zone2", "zone3", "zone4", "zone5"), 0)
    assert body["week"] == {
        "zone2": 0,
        "moderate": 0,
        "zone2_target": [45, 75],  # the cycle's Long zone 2 (ADR-0079)
        "zone2_left": 45,
        "total": 0,
        "total_target": [75, 115],  # and Cardio + core's 30-40
        "total_left": 75,
        "zones": nothing | {"zone2_no_hr": 0, "zone3_up_no_hr": 0},
    }


def test_a_strength_day_has_nothing_planned_for_cardio(signed_in: TestClient) -> None:
    assert signed_in.get("/api/cardio").json()["planned"] is None


def test_logging_the_planned_cardio_completes_it(signed_in: TestClient, engine: Engine) -> None:
    template = _plan_next(engine, "zone2")
    log = {"token": TOKEN, "kind": "zone2", "value": 62, "activity": "hike"}
    body = signed_in.post("/api/cardio", json=log).json()
    assert body["planned"] is True
    assert body["already_saved"] is False
    assert body["next_session"] not in (None, "Long zone 2")
    assert body["week"]["zone2"] == 62
    assert _workouts(engine) == [(template, "hike", 62)]


def test_cardio_on_a_strength_day_is_an_extra(signed_in: TestClient, engine: Engine) -> None:
    """A walk on a Legs day never completes Legs or moves the queue."""
    log = {"token": TOKEN, "kind": "zone2", "value": 30, "activity": "walk"}
    body = signed_in.post("/api/cardio", json=log).json()
    assert body["planned"] is False
    assert body["next_session"] == "Legs"
    assert _workouts(engine) == [(None, "walk", 30)]
    assert signed_in.get("/api/session/today").json()["session"]["name"] == "Legs"


def test_hiit_logs_rounds(signed_in: TestClient, engine: Engine) -> None:
    template = _plan_next(engine, "hiit")
    planned = signed_in.get("/api/cardio").json()["planned"]
    assert (planned["kind"], planned["target"]) == ("hiit", 8)
    body = signed_in.post("/api/cardio", json={"token": TOKEN, "kind": "hiit", "value": 10})
    assert body.json()["planned"] is True
    assert _workouts(engine) == [(template, None, 10)]


def test_the_same_log_saved_twice_is_saved_once(signed_in: TestClient, engine: Engine) -> None:
    _plan_next(engine, "zone2")
    log = {"token": TOKEN, "kind": "zone2", "value": 45}
    first = signed_in.post("/api/cardio", json=log).json()
    again = signed_in.post("/api/cardio", json=log).json()
    assert again["already_saved"] is True
    assert again["workout_id"] == first["workout_id"]
    assert again["planned"] is False  # nothing completed this time
    assert len(_workouts(engine)) == 1


def _pointer(engine: Engine) -> int | None:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        plan = users.plan_state(bound)
        return plan.next_template_id if plan is not None else None


def _undo(engine: Engine) -> None:
    now = datetime.now(UTC)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        found = undo.last(bound, now)
        assert isinstance(found, undo.Undoable)
        assert isinstance(undo.apply(bound, found.event_id, now), undo.Undone)


@pytest.mark.parametrize("planned", [True, False])
def test_undo_removes_the_log_and_restores_the_queue(
    signed_in: TestClient, engine: Engine, planned: bool
) -> None:
    """Undoing an extra leaves the queue where it was; undoing the planned log moves it back."""
    if planned:
        _plan_next(engine, "zone2")
    before = _pointer(engine)
    signed_in.post("/api/cardio", json={"token": TOKEN, "kind": "zone2", "value": 45})
    assert (_pointer(engine) != before) is planned
    _undo(engine)
    assert _workouts(engine) == []
    assert _pointer(engine) == before
    with make_session_factory(engine, user_id=OWNER)() as bound:
        assert bound.scalars(select(Event).where(Event.kind == undo.UNDONE)).one()


def test_a_session_that_changed_meanwhile_is_a_conflict(
    signed_in: TestClient, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Today's session moved between showing and saving (a rest, a swap): nothing is saved."""
    monkeypatch.setattr(workout_log, "save", lambda *_: workout_log.Stale())
    log = {"token": TOKEN, "kind": "zone2", "value": 30}
    assert signed_in.post("/api/cardio", json=log).status_code == 409


def test_a_log_the_service_would_not_save_reads_as_stale(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    monkeypatch.setattr(workout_log, "save", lambda *_: None)
    with make_session_factory(engine, user_id=OWNER)() as bound:
        today = datetime.now(UTC).date()
        result = cardio.log(bound, today, Settings().tz, "zone2", 30, None, TOKEN)
    assert isinstance(result, workout_log.Stale)


@pytest.mark.parametrize(
    "log",
    [
        {"token": TOKEN, "kind": "zone2", "value": 0},
        {"token": TOKEN, "kind": "zone2", "value": 601},
        {"token": TOKEN, "kind": "hiit", "value": 101},
        {"token": TOKEN, "kind": "pull-up", "value": 10},
        {"token": TOKEN, "kind": "zone2", "value": 30, "activity": "teleport"},
        {"token": "not-hex", "kind": "zone2", "value": 30},
    ],
)
def test_bad_logs_are_refused(
    signed_in: TestClient, engine: Engine, log: dict[str, object]
) -> None:
    assert signed_in.post("/api/cardio", json=log).status_code == 422
    assert _workouts(engine) == []


def test_cardio_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/cardio").status_code == 401
        log = {"token": TOKEN, "kind": "zone2", "value": 30}
        assert stranger.post("/api/cardio", json=log).status_code == 401


def test_a_log_keeps_its_effort_distance_heart_rate_and_start(
    signed_in: TestClient, engine: Engine
) -> None:
    _plan_next(engine, "moderate-cardio")
    log = {
        "token": TOKEN,
        "kind": "moderate-cardio",
        "value": 43,
        "activity": "run",
        "effort": 6,
        "distance_km": 7.29,
        "avg_hr": 139,
        "max_hr": 160,
        "start": f"{datetime.now(BERLIN) - timedelta(hours=1):%H:%M}",  # over by now
    }
    body = signed_in.post("/api/cardio", json=log).json()
    assert body["pace"] == 354  # 43 min over 7.29 km: 5:54 a km
    with make_session_factory(engine, user_id=OWNER)() as bound:
        workout = bound.scalars(select(Workout)).one()
        assert (workout.effort, workout.distance_m, workout.avg_hr, workout.max_hr) == (
            6,
            7290,
            139,
            160,
        )
        assert workout.started_at is not None
        assert workout.started_at <= datetime.now(UTC)


def test_a_log_without_details_stores_none(signed_in: TestClient, engine: Engine) -> None:
    _plan_next(engine, "zone2")
    body = signed_in.post("/api/cardio", json={"token": TOKEN, "kind": "zone2", "value": 45})
    assert body.json()["pace"] is None
    with make_session_factory(engine, user_id=OWNER)() as bound:
        workout = bound.scalars(select(Workout)).one()
        assert (workout.effort, workout.distance_m, workout.avg_hr, workout.started_at) == (
            None,
            None,
            None,
            None,
        )


@pytest.mark.parametrize(
    ("extra", "detail"),
    [
        ({"avg_hr": 150, "max_hr": 140}, "highest heart rate can't be below the average"),
        ({"kind": "hiit", "value": 8, "distance_km": 2}, "HIIT is counted in rounds: no distance"),
    ],
)
def test_details_that_make_no_sense_are_refused(
    signed_in: TestClient, engine: Engine, extra: dict[str, object], detail: str
) -> None:
    log = {"token": TOKEN, "kind": "zone2", "value": 45, **extra}
    response = signed_in.post("/api/cardio", json=log)
    assert response.status_code == 422
    assert response.json()["detail"] == detail
    assert _workouts(engine) == []


def test_a_run_still_going_is_refused(signed_in: TestClient, engine: Engine) -> None:
    """Eval of 2026-10-24: a start ten minutes ago with 30 minutes ends after now."""
    start = f"{datetime.now(BERLIN) - timedelta(minutes=10):%H:%M}"
    log = {"token": TOKEN, "kind": "zone2", "value": 30, "start": start}
    response = signed_in.post("/api/cardio", json=log)
    assert response.status_code == 422
    assert response.json()["detail"] == "start plus minutes can't be later than now"
    assert _workouts(engine) == []


def test_a_start_the_spring_change_skips_is_refused(signed_in: TestClient, engine: Engine) -> None:
    """Eval of 2026-10-24: 02:30 on 29 March never happens in Berlin; it was saved as 03:30."""
    log = {"token": TOKEN, "kind": "zone2", "value": 30, "start": "02:30"}
    with time_machine.travel(datetime(2026, 3, 29, 10, 0, tzinfo=UTC), tick=False):
        response = signed_in.post("/api/cardio", json=log)
    assert response.status_code == 422
    assert response.json()["detail"] == cardio.SKIPPED
    assert _workouts(engine) == []


def test_effort_outside_one_to_ten_is_refused(signed_in: TestClient) -> None:
    log = {"token": TOKEN, "kind": "zone2", "value": 45, "effort": 11}
    assert signed_in.post("/api/cardio", json=log).status_code == 422
