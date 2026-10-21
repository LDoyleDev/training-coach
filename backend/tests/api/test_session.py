"""GET /api/session/today (#117): today's guided session, owner-only."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Exercise, SessionProgress, SessionTemplate, SetLog, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.queue import local_date
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


def test_today_comes_in_work_order(signed_in: TestClient) -> None:
    body = signed_in.get("/api/session/today").json()["session"]
    assert body["name"] == "Legs"
    assert body["warm_up"] is True
    items = body["items"]
    assert [items[s["item"]]["slug"] for s in body["order"][:2]] == ["jump-squat", "tibialis-raise"]
    calf = next(i for i in items if i["slug"] == "calf-raise")
    assert (calf["unit"], calf["per_side"], calf["pair"]) == ("reps", True, 2)
    assert calf["summary"].startswith("Ball of one foot")


def _first_slug(client: TestClient) -> str:
    session = client.get("/api/session/today").json()["session"]
    slug: str = session["items"][session["order"][0]["item"]]["slug"]
    return slug


def test_a_pair_can_be_swapped_and_swapped_back(signed_in: TestClient) -> None:
    """The swap lives in the kept progress, so an un-swap sticks too."""
    template = signed_in.get("/api/session/today").json()["session"]["template_id"]

    revision = 0

    def swap(first: list[int]) -> None:
        nonlocal revision
        body = {"template_id": template, "revision": revision, "first": first, "position": 0}
        kept = signed_in.put("/api/session/progress", json=body)
        assert kept.status_code == 200
        revision = kept.json()["revision"]

    assert _first_slug(signed_in) == "jump-squat"
    swap([1])
    assert _first_slug(signed_in) == "tibialis-raise"
    swap([])
    assert _first_slug(signed_in) == "jump-squat"


def test_today_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/session/today").status_code == 401


def test_nothing_to_guide_once_today_is_done(signed_in: TestClient, engine: Engine) -> None:
    template = signed_in.get("/api/session/today").json()["session"]["template_id"]
    today = local_date(datetime.now(UTC), Settings().tz)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        bound.add(Workout(local_date=today, template_id=template, status=WorkoutStatus.REST))
    assert signed_in.get("/api/session/today").json() == {
        "session": None,
        "planned": None,
        "progress": None,
        "test_day": None,
        "readiness_note": None,
        "daily_check": None,
    }


def _log_yesterday(engine: Engine, done: dict[str, int]) -> None:
    """Every set of each exercise in ``done`` at that value, logged yesterday."""
    yesterday = local_date(datetime.now(UTC), Settings().tz) - timedelta(days=1)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        workout = Workout(local_date=yesterday, status=WorkoutStatus.DONE)
        for slug, value in done.items():
            exercise = bound.scalars(select(Exercise).where(Exercise.slug == slug)).one()
            state = users.exercise_state(bound, exercise.id)
            assert state is not None
            workout.sets += [
                SetLog(
                    exercise_id=exercise.id,
                    ladder_step_id=state.ladder_step_id,
                    set_no=n,
                    side=Side.BOTH,
                    value=value,
                )
                for n in (1, 2, 3)
            ]
        bound.add(workout)


def _targets(client: TestClient, slug: str) -> list[int]:
    items = client.get("/api/session/today").json()["session"]["items"]
    targets: list[int] = next(i["targets"] for i in items if i["slug"] == slug)
    return targets


@pytest.mark.parametrize(
    ("pace", "jump_squat", "tibialis"),
    [
        pytest.param("standard", [7, 7, 7], [21, 21, 21], id="standard"),  # +1 in 5-8, +3 in 15-25
        pytest.param("steady", [7, 7, 7], [19, 19, 19], id="steady"),  # +1 everywhere
        pytest.param("fast", [8, 8, 8], [21, 21, 21], id="fast"),  # at least +2
    ],
)
def test_the_pace_setting_changes_the_next_targets(
    signed_in: TestClient, engine: Engine, pace: str, jump_squat: list[int], tibialis: list[int]
) -> None:
    """ADR-0057: the session page's targets take the person's pace."""
    _log_yesterday(engine, {"jump-squat": 6, "tibialis-raise": 18})
    assert signed_in.patch("/api/settings", json={"pace": pace}).json()["pace"] == pace
    assert _targets(signed_in, "jump-squat") == jump_squat
    assert _targets(signed_in, "tibialis-raise") == tibialis


# ------------------------------------------------------------------ progress and saving


def _today_view(client: TestClient) -> dict[str, Any]:
    body: dict[str, Any] = client.get("/api/session/today").json()
    return body


def _do_first_sets(client: TestClient, count: int) -> dict[str, Any]:
    """Confirm the first ``count`` sets at their targets, as the screens would."""
    session = _today_view(client)["session"]
    sets = [
        {"item": s["item"], "set_no": s["set_no"], "left": s["target"]}
        for s in session["order"][:count]
    ]
    kept = client.put(
        "/api/session/progress",
        json={"template_id": session["template_id"], "position": count, "sets": sets},
    )
    assert kept.status_code == 200
    return session


def test_progress_is_kept_and_resumed(signed_in: TestClient) -> None:
    _do_first_sets(signed_in, 3)
    view = _today_view(signed_in)
    assert view["progress"]["position"] == 3
    assert len(view["progress"]["sets"]) == 3
    assert view["progress"]["saved"] is False


def test_a_swapped_pair_is_kept(signed_in: TestClient) -> None:
    session = _today_view(signed_in)["session"]
    body = {"template_id": session["template_id"], "position": 0, "first": [1], "sets": []}
    assert signed_in.put("/api/session/progress", json=body).status_code == 200
    view = _today_view(signed_in)
    assert view["progress"]["first"] == [1]
    first_item = view["session"]["items"][view["session"]["order"][0]["item"]]
    assert first_item["slug"] == "tibialis-raise"


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"sets": [{"item": 99, "set_no": 1, "left": 5}]}, 422),
        ({"sets": [{"item": 0, "set_no": 9, "left": 5}]}, 422),
        ({"sets": [{"item": 0, "set_no": 1, "left": 5, "right": 5}]}, 422),  # not one-sided
        ({"sets": [{"item": 0, "set_no": 1, "left": -1}]}, 422),
        ({"position": 999}, 422),  # the request schema
        ({"position": 100}, 422),  # the plan: Legs has 25 sets
        ({"sets": [{"item": 0, "set_no": 1, "left": 500}]}, 422),  # over 200 reps
        (
            {
                "sets": [
                    {"item": 0, "set_no": 1, "left": 5},
                    {"item": 0, "set_no": 1, "left": 5},
                ]
            },
            422,
        ),  # the same set twice
        ({"first": [9]}, 422),  # Legs has pairs 1-4
        ({"first": [-1]}, 422),
        ({"template_id": 999999}, 409),
    ],
)
def test_nothing_from_the_browser_is_trusted(
    signed_in: TestClient, change: dict[str, Any], status: int
) -> None:
    session = _today_view(signed_in)["session"]
    body = {"template_id": session["template_id"], "position": 0, "sets": [], **change}
    assert signed_in.put("/api/session/progress", json=body).status_code == status


def test_saving_logs_the_sets_once_and_moves_the_queue(
    signed_in: TestClient, engine: Engine
) -> None:
    session = _do_first_sets(signed_in, 6)  # three rounds of jump squat + tibialis raise
    saved = signed_in.post("/api/session/save", json={})
    assert saved.status_code == 200
    body = saved.json()
    assert (body["already_saved"], body["next_session"], body["stretching"]) == (
        False,
        "Recovery + posture",
        True,
    )
    with make_session_factory(engine, user_id=OWNER)() as bound:
        workout = bound.get_one(Workout, body["workout_id"])
        assert workout.template_id == session["template_id"]
        assert len(workout.sets) == 6
    again = signed_in.post("/api/session/save", json={})
    assert again.json()["already_saved"] is True
    assert again.json()["workout_id"] == body["workout_id"]
    assert _today_view(signed_in) == {
        "session": None,
        "planned": None,
        "progress": None,
        "test_day": None,
        "readiness_note": None,
        "daily_check": None,
    }


def test_one_sided_sets_log_both_sides(signed_in: TestClient, engine: Engine) -> None:
    session = _today_view(signed_in)["session"]
    calf = next(i for i, item in enumerate(session["items"]) if item["slug"] == "calf-raise")
    sets = [{"item": calf, "set_no": 1, "left": 15, "right": 12}]
    body = {"template_id": session["template_id"], "position": 1, "sets": sets}
    assert signed_in.put("/api/session/progress", json=body).status_code == 200
    workout_id = signed_in.post("/api/session/save", json={}).json()["workout_id"]
    with make_session_factory(engine, user_id=OWNER)() as bound:
        values = sorted((s.side, s.value) for s in bound.get_one(Workout, workout_id).sets)
    assert values == [("left", 15), ("right", 12)]


def test_nothing_recorded_is_nothing_to_save(signed_in: TestClient) -> None:
    assert signed_in.post("/api/session/save", json={}).status_code == 400
    assert signed_in.post("/api/session/save", json={"day": "2999-01-01"}).status_code == 400


def test_a_day_left_unsaved_is_offered_and_saved_there(
    signed_in: TestClient, engine: Engine
) -> None:
    session = _do_first_sets(signed_in, 2)
    yesterday = local_date(datetime.now(UTC), Settings().tz) - timedelta(days=1)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        progress = bound.scalars(select(SessionProgress)).one()
        progress.local_date = yesterday  # as if it was yesterday's, never saved
    (pending,) = signed_in.get("/api/session/pending").json()
    assert (pending["day"], pending["session"], pending["sets"]) == (
        yesterday.isoformat(),
        session["name"],
        2,
    )
    saved = signed_in.post("/api/session/save", json={"day": yesterday.isoformat()}).json()
    assert saved["stretching"] is False  # not offered for a past day
    with make_session_factory(engine, user_id=OWNER)() as bound:
        assert bound.get_one(Workout, saved["workout_id"]).local_date == yesterday
    assert signed_in.get("/api/session/pending").json() == []


def test_a_session_that_changed_since_is_a_conflict(signed_in: TestClient, engine: Engine) -> None:
    _do_first_sets(signed_in, 1)
    session = _today_view(signed_in)["session"]
    today = local_date(datetime.now(UTC), Settings().tz)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        bound.add(
            Workout(local_date=today, template_id=session["template_id"], status=WorkoutStatus.REST)
        )
    assert signed_in.post("/api/session/save", json={}).status_code == 409


def test_progress_and_saving_need_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        body = {"template_id": 1, "position": 0}
        assert stranger.put("/api/session/progress", json=body).status_code == 401
        assert stranger.post("/api/session/save", json={}).status_code == 401
        assert stranger.get("/api/session/pending").status_code == 401


def test_a_swap_kept_for_another_session_does_not_apply(
    signed_in: TestClient, engine: Engine
) -> None:
    """Kept on Legs, then today's session changes: Torso's pairs stay in order."""
    template = signed_in.get("/api/session/today").json()["session"]["template_id"]
    body = {"template_id": template, "position": 0, "first": [1], "sets": []}
    assert signed_in.put("/api/session/progress", json=body).status_code == 200
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        torso = bound.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == "torso"))
        state = users.plan_state(bound)
        assert state is not None
        state.next_template_id = torso.one()
    view = signed_in.get("/api/session/today").json()
    assert view["progress"] is None
    assert _first_slug(signed_in) == "pull-up"


def test_a_stale_tab_gets_a_conflict_not_an_overwrite(signed_in: TestClient) -> None:
    _do_first_sets(signed_in, 3)  # the phone: revision 1
    view = signed_in.get("/api/session/today").json()
    assert view["progress"]["revision"] == 1
    stale = {"template_id": view["session"]["template_id"], "revision": 0, "position": 0}
    assert signed_in.put("/api/session/progress", json=stale).status_code == 409
    assert len(signed_in.get("/api/session/today").json()["progress"]["sets"]) == 3


# ------------------------------------------------------------------ stretching (#135)


def _saved_legs(client: TestClient) -> int:
    _do_first_sets(client, 6)
    workout: int = client.post("/api/session/save", json={}).json()["workout_id"]
    return workout


def test_stretching_after_a_saved_session_is_shown_then_logged_once(
    signed_in: TestClient, engine: Engine
) -> None:
    workout = _saved_legs(signed_in)
    routine = signed_in.get(f"/api/session/stretching/{workout}", params={"minutes": 10})
    assert routine.status_code == 200
    body = routine.json()
    assert (body["session"], body["minutes"], body["hold_seconds"]) == ("Legs", 10, 30)
    assert body["steps"]
    assert all(s["rounds"] >= 2 and s["cue"] for s in body["steps"])
    done = signed_in.post(f"/api/session/stretching/{workout}", json={"minutes": 10})
    assert done.json() == {"logged": True}
    again = signed_in.post(f"/api/session/stretching/{workout}", json={"minutes": 20})
    assert again.json() == {"logged": False}  # one per workout
    with make_session_factory(engine, user_id=OWNER)() as bound:
        mobility = bound.scalars(select(Exercise.id).where(Exercise.slug == "mobility")).one()
        sets = bound.get_one(Workout, workout).sets
        assert [s.value for s in sets if s.exercise_id == mobility] == [10]


@pytest.mark.parametrize("minutes", [15, 0])
def test_only_the_offered_times_make_a_routine(signed_in: TestClient, minutes: int) -> None:
    workout = _saved_legs(signed_in)
    path = f"/api/session/stretching/{workout}"
    assert signed_in.get(path, params={"minutes": minutes}).status_code == 404
    assert signed_in.post(path, json={"minutes": minutes}).status_code == 404


def test_no_stretching_for_a_workout_that_isnt_there(signed_in: TestClient) -> None:
    assert signed_in.get("/api/session/stretching/999", params={"minutes": 10}).status_code == 404
    assert signed_in.post("/api/session/stretching/999", json={"minutes": 10}).status_code == 404


def test_stretching_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/session/stretching/1", params={"minutes": 10}).status_code == 401
        assert stranger.post("/api/session/stretching/1", json={"minutes": 10}).status_code == 401


def test_set_times_are_kept_resumed_and_saved(signed_in: TestClient, engine: Engine) -> None:
    """The phone's times for each set (ADR-0061), with its own offset, come back on resume
    and end up on the saved sets."""
    session = _today_view(signed_in)["session"]
    start = datetime.now(UTC) - timedelta(minutes=10)
    sets = []
    for n, s in enumerate(session["order"][:2]):
        at = start + timedelta(minutes=2 * n)
        sets.append(
            {
                "item": s["item"],
                "set_no": s["set_no"],
                "left": s["target"],
                "started_at": at.astimezone(timezone(timedelta(hours=2))).isoformat(),
                "done_at": (at + timedelta(seconds=45)).isoformat(),
            }
        )
    body = {"template_id": session["template_id"], "position": 2, "sets": sets}
    assert signed_in.put("/api/session/progress", json=body).status_code == 200
    kept = _today_view(signed_in)["progress"]["sets"]
    assert [datetime.fromisoformat(s["started_at"]) for s in kept] == [
        start,
        start + timedelta(minutes=2),
    ]
    saved = signed_in.post("/api/session/save", json={}).json()
    with make_session_factory(engine, user_id=OWNER)() as bound:
        rows = bound.get_one(Workout, saved["workout_id"]).sets
        times = sorted((r.started_at, r.done_at) for r in rows)
    assert times == [
        (start, start + timedelta(seconds=45)),
        (start + timedelta(minutes=2), start + timedelta(minutes=2, seconds=45)),
    ]
    # 2:45 in all: 90 s on sets, 75 s resting, each rounded to whole minutes (#266).
    assert saved["timing"] == {"minutes": 3, "on_sets": 2, "resting": 1, "breaks": 0}
    assert signed_in.get("/api/progress/times").json() == [
        {"session": "Legs", "usual": 3, "last": 3, "fastest": 3, "timed": 1}
    ]


def test_a_set_time_without_an_offset_is_refused(signed_in: TestClient) -> None:
    session = _today_view(signed_in)["session"]
    step = session["order"][0]
    naive = datetime.now(UTC).replace(tzinfo=None).isoformat()
    done = {"item": step["item"], "set_no": 1, "left": 5, "started_at": naive, "done_at": naive}
    body = {"template_id": session["template_id"], "position": 1, "sets": [done]}
    assert signed_in.put("/api/session/progress", json=body).status_code == 422


def test_untimed_sets_save_without_a_timing(signed_in: TestClient) -> None:
    _do_first_sets(signed_in, 2)
    assert signed_in.post("/api/session/save", json={}).json()["timing"] is None
    assert signed_in.get("/api/progress/times").json() == []


def test_today_says_how_long_this_session_usually_takes(
    signed_in: TestClient, engine: Engine
) -> None:
    session = _today_view(signed_in)["session"]
    assert session["usual_minutes"] is None  # never timed yet
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        jump = bound.scalars(select(Exercise).where(Exercise.slug == "jump-squat")).one()
        start = datetime.now(UTC) - timedelta(days=7)
        workout = Workout(
            local_date=start.date(), template_id=session["template_id"], status=WorkoutStatus.DONE
        )
        workout.sets = [
            SetLog(
                exercise_id=jump.id,
                ladder_step_id=jump.ladder[0].id,
                set_no=n + 1,
                value=6,
                started_at=start + timedelta(minutes=3 * n),
                done_at=start + timedelta(minutes=3 * n + 1),
            )
            for n in range(14)
        ]
        bound.add(workout)
    assert _today_view(signed_in)["session"]["usual_minutes"] == 40


def test_the_mobility_item_comes_with_its_guided_flow(
    signed_in: TestClient, engine: Engine
) -> None:
    """ADR-0062: the Recovery day's mobility is eight timed movements, ten minutes in all."""
    legs = signed_in.get("/api/session/today").json()["session"]["items"]
    assert all(i["flow"] is None for i in legs)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        recovery = bound.scalars(
            select(SessionTemplate.id).where(SessionTemplate.slug == "recovery")
        )
        state = users.plan_state(bound)
        assert state is not None
        state.next_template_id = recovery.one()
    items = signed_in.get("/api/session/today").json()["session"]["items"]
    flow = next(i for i in items if i["slug"] == "mobility")["flow"]
    assert flow["seconds"] == 600
    assert flow["safety"].startswith("If something hurts")
    assert [m["slug"] for m in flow["moves"]] == [
        "y-reach",
        "hip-hinge",
        "half-kneeling-hip-flexor",
        "kneeling-lunge-rotation",
        "cat-cow",
        "quadruped-t-spine-rotation",
        "hamstring-floss",
        "glute-bridge",
    ]
    lunge = flow["moves"][3]
    assert (lunge["seconds"], lunge["per_side"]) == (45, True)
    assert all(lunge[k] for k in ("start", "end", "cues", "breathing", "easier", "pacing"))
    assert all(i["flow"] is None for i in items if i["slug"] != "mobility")
