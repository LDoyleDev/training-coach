"""The cycle through the plan editor's routes (ADR-0093): what GET /api/plan/edit says about each
session, a save that adds, copies, removes and moves sessions, and the map per cycle at the
person's minutes a session."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import SessionProgress, SessionTemplate, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import WorkoutStatus
from training_coach.domain.queue import local_date
from training_coach.services import auth, user_settings
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

PUSH_UPS = {"exercise": "push-up", "sets": 4, "rep_min": 5, "rep_max": 10}


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as signed_in:
        with make_session_factory(engine, user_id=OWNER)() as bound:
            token = auth.create_link(bound, datetime.now(UTC))
            bound.commit()
        assert signed_in.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield signed_in


def _kept(client: TestClient) -> list[dict[str, Any]]:
    """The cycle as saved, as a draft sends it."""
    return [
        {k: s[k] for k in ("slug", "name", "kind", "rest_after")}
        for s in client.get("/api/plan/edit").json()["sessions"]
    ]


def _save(client: TestClient, **body: Any) -> Any:
    revision = client.get("/api/plan/edit").json()["revision"]
    return client.post("/api/plan/changes", json={"revision": revision, "note": "Mine", **body})


def _map(client: TestClient, **body: Any) -> dict[str, Any]:
    found = client.post("/api/plan/coverage/draft", json={"place": "home", "versions": [], **body})
    assert found.status_code == 200, found.text
    view: dict[str, Any] = found.json()
    return view


def _muscles(view: dict[str, Any]) -> dict[str, Any]:
    return {m["muscle"]: m for m in view["muscles"]}


def test_the_editor_gets_each_sessions_kind_rest_and_history(
    client: TestClient, engine: Engine
) -> None:
    plan = load_plan()
    edit = client.get("/api/plan/edit").json()
    sessions = edit["sessions"]
    assert [s["kind"] for s in sessions] == [s.type for s in plan.sessions]
    assert [s["optional"] for s in sessions] == [s.is_rest_optional for s in plan.sessions]
    assert [s["rest_after"] for s in sessions] == [0] * 7  # the owner's have no rest places
    assert [s["next"] for s in sessions] == [True] + [False] * 6
    assert [s["logged"] for s in sessions] == [0] * 7
    assert edit["limits"] == {"max_sessions": 10, "max_cycle_days": 14, "max_rest": 6}
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        legs = bound.scalars(select(SessionTemplate).where(SessionTemplate.slug == "legs")).one()
        for day in (1, 2):
            bound.add(
                Workout(
                    local_date=date(2026, 11, day),
                    status=WorkoutStatus.DONE,
                    template_id=legs.id,
                )
            )
    assert client.get("/api/plan/edit").json()["sessions"][0]["logged"] == 2


def test_the_plan_gives_each_sessions_rest_places(client: TestClient) -> None:
    cycle = _kept(client)
    cycle[0]["rest_after"] = 2
    assert _save(client, cycle=cycle).status_code == 200
    rest = [s["rest_after"] for s in client.get("/api/plan").json()["sessions"]]
    assert rest == [2, 0, 0, 0, 0, 0, 0]


def test_a_new_session_and_its_exercises_save_in_one_request(client: TestClient) -> None:
    cycle = [*_kept(client), {"new": "n1", "name": "Legs 2", "kind": "strength", "rest_after": 0}]
    version = {"slug": "new:n1", "place": "home", "items": [PUSH_UPS]}
    saved = _save(client, cycle=cycle, versions=[version])
    assert saved.status_code == 200, saved.text
    assert saved.json()["slugs"] == {"n1": "legs-2"}
    assert saved.json()["version"] == "Mine"
    assert saved.json()["revision"] == client.get("/api/plan/edit").json()["revision"]
    last = client.get("/api/plan").json()["sessions"][-1]
    assert (last["slug"], last["name"]) == ("legs-2", "Legs 2")
    assert [e["slug"] for e in last["exercises"]] == ["push-up"]


def test_a_cycle_alone_saves_a_copy_a_removal_and_a_move(client: TestClient) -> None:
    kept = _kept(client)
    copy = {"new": "n1", "name": "Torso again", "kind": "strength", "rest_after": 0}
    cycle = [kept[1], kept[0], *kept[2:6], {**copy, "copy_of": "torso"}]  # zone2 removed
    saved = _save(client, cycle=cycle)  # no versions
    assert saved.status_code == 200, saved.text
    assert saved.json()["slugs"] == {"n1": "torso-again"}
    sessions = client.get("/api/plan").json()["sessions"]
    assert [s["slug"] for s in sessions] == [
        "recovery",
        "legs",
        "torso",
        "moderate-cardio",
        "hiit",
        "arms",
        "torso-again",
    ]
    assert sessions[-1]["exercises"] == sessions[2]["exercises"]


def test_a_save_without_a_cycle_answers_no_new_slugs(client: TestClient) -> None:
    first = client.get("/api/plan/edit").json()["sessions"][0]
    version = {"slug": first["slug"], "place": "home", "items": [PUSH_UPS]}
    assert _save(client, versions=[version]).json()["slugs"] == {}


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda c: [*c, *({**c[0], "slug": "nope"},)], "nope isn't one of your sessions."),
        (lambda c: [{**c[0], "name": "Push-up"}, *c[1:]], "an exercise's name"),
        (lambda c: [{**c[0], "name": "Today"}, *c[1:]], "reads as a day"),
        (lambda c: [{**c[0], "name": c[1]["name"]}, *c[1:]], "can't both be called"),
        (lambda c: [{**c[0], "rest_after": 7}, *c[1:]], "0 to 6"),
        (lambda c: [{**s, "rest_after": 2} for s in c], "at most 14"),
        (lambda c: [c[0], c[0]], "only once"),
        (
            lambda c: [
                *c,
                *(
                    {"new": f"n{n}", "name": f"Extra {n}", "kind": "strength", "rest_after": 0}
                    for n in range(4)
                ),
            ],
            "at most 10 sessions",
        ),
        (
            lambda c: [*c, {"new": "n1", "name": "Empty", "kind": "strength", "rest_after": 0}],
            "Empty needs at least one exercise.",
        ),
        (
            lambda c: [
                *c,
                {"new": "n1", "name": "X", "kind": "strength", "rest_after": 0, "copy_of": "nope"},
            ],
            "nope isn't one of your sessions to copy.",
        ),
    ],
    ids=[
        "unknown",
        "exercise-name",
        "a-day",
        "two-names",
        "rest",
        "days",
        "twice",
        "sessions",
        "empty",
        "copy-of",
    ],
)
def test_a_cycle_that_cant_be_saved_is_refused_in_words(
    client: TestClient, change: Any, reason: str
) -> None:
    before = client.get("/api/plan").json()
    refused = _save(client, cycle=change(_kept(client)))
    assert refused.status_code == 422, refused.text
    assert reason in refused.json()["detail"]
    assert client.get("/api/plan").json() == before


@pytest.mark.parametrize(
    "entry",
    [
        {"slug": "legs", "name": "Legs", "kind": "strength", "rest_after": 0, "extra": 1},
        {"slug": "legs", "new": "n1", "name": "Legs", "kind": "strength", "rest_after": 0},
        {"slug": "legs", "name": "Legs", "kind": "yoga", "rest_after": 0},
        {"new": "N 1", "name": "Legs 2", "kind": "strength", "rest_after": 0},
    ],
    ids=["extra-field", "both", "kind", "key"],
)
def test_a_cycle_entry_is_one_shape_or_the_other(client: TestClient, entry: Any) -> None:
    assert _save(client, cycle=[entry]).status_code == 422
    assert _map(client)["sessions"]  # the map route checks the same shape
    body = {"place": "home", "versions": [], "cycle": [entry]}
    assert client.post("/api/plan/coverage/draft", json=body).status_code == 422


def test_an_empty_cycle_is_refused(client: TestClient) -> None:
    assert _save(client, cycle=[]).status_code == 422


def test_a_stale_cycle_and_one_during_a_session_are_conflicts(
    client: TestClient, engine: Engine
) -> None:
    kept = _kept(client)
    revision = client.get("/api/plan/edit").json()["revision"]
    assert _save(client, cycle=kept[:-1]).status_code == 200
    late = client.post(
        "/api/plan/changes", json={"revision": revision, "note": "Late", "cycle": kept}
    )
    assert (late.status_code, late.json()["detail"]) == (409, "stale")
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        template = bound.scalars(select(SessionTemplate).order_by(SessionTemplate.position)).first()
        assert template is not None
        today = local_date(datetime.now(UTC), Settings().tz)
        kept_sets = [{"item": 0, "set_no": 1, "left": 8}]
        bound.add(
            SessionProgress(
                local_date=today, template_id=template.id, token="ab" * 16, sets=kept_sets
            )
        )
    busy = _save(client, cycle=_kept(client)[:-1])
    assert (busy.status_code, busy.json()["detail"]) == (409, "in-progress")


def test_a_seven_day_plan_at_empty_settings_is_todays_map(client: TestClient) -> None:
    saved = client.get("/api/plan/coverage", params={"place": "home"}).json()
    assert (saved["cycle_days"], saved["session_minutes"], saved["session_exercises"]) == (
        7,
        None,
        None,
    )
    assert _map(client, cycle=_kept(client)) == saved


def test_the_draft_map_counts_an_8_day_cycle_with_its_bands_stretched(client: TestClient) -> None:
    saved = client.get("/api/plan/coverage", params={"place": "home"}).json()
    cycle = _kept(client)
    cycle[-1]["rest_after"] = 1
    eight = _map(client, cycle=cycle)
    assert eight["cycle_days"] == 8
    before, after = _muscles(saved), _muscles(eight)
    for muscle, m in after.items():
        assert m["sets"] == before[muscle]["sets"], muscle  # the same sessions
        assert m["low"] == pytest.approx(before[muscle]["low"] * 8 / 7), muscle
        assert m["high"] == pytest.approx(before[muscle]["high"] * 8 / 7), muscle
    assert after["lats"]["band"] == "light green"  # 10 sets: green a week, not per 8 days
    assert client.get("/api/plan/coverage", params={"place": "home"}).json() == saved


def test_the_draft_map_counts_added_and_removed_sessions(client: TestClient) -> None:
    saved = _muscles(client.get("/api/plan/coverage", params={"place": "home"}).json())
    kept = [s for s in _kept(client) if s["slug"] != "legs"]
    new = {"new": "n1", "name": "Push day", "kind": "strength", "rest_after": 0}
    view = _map(
        client,
        cycle=[*kept, new],
        versions=[{"slug": "new:n1", "place": "home", "items": [PUSH_UPS]}],
    )
    assert [s["slug"] for s in view["sessions"]] == [*(s["slug"] for s in kept), "new:n1"]
    assert view["sessions"][-1]["session"] == "Push day"
    assert _muscles(view)["chest"]["sets"] > saved["chest"]["sets"]
    assert _muscles(view)["glutes"]["sets"] < saved["glutes"]["sets"]
    copy = _map(client, cycle=[*_kept(client), {**new, "copy_of": "legs"}])
    assert _muscles(copy)["glutes"]["sets"] > saved["glutes"]["sets"]  # its versions come along


def test_the_draft_map_draws_what_it_can_of_a_cycle(client: TestClient) -> None:
    """Save refuses a bad cycle; the map leaves out an entry it can't draw."""
    kept = _kept(client)
    view = _map(client, cycle=[*kept, {**kept[0], "slug": "nope"}, kept[0]])
    assert [s["slug"] for s in view["sessions"]] == [s["slug"] for s in kept]


def test_every_map_counts_at_the_persons_minutes_a_session(
    client: TestClient, engine: Engine
) -> None:
    planned = client.get("/api/plan/coverage", params={"place": "home"}).json()
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        user_settings.update(bound, session_minutes=30)
    at_30 = client.get("/api/plan/coverage", params={"place": "home"}).json()
    assert (at_30["session_minutes"], at_30["session_exercises"]) == (30, None)
    minutes = {s["slug"]: s["minutes"] for s in at_30["sessions"]}
    assert minutes["legs"] < 49  # as planned it is 49
    assert minutes["recovery"] == {s["slug"]: s["minutes"] for s in planned["sessions"]}["recovery"]
    assert sum(m["sets"] for m in at_30["muscles"]) < sum(m["sets"] for m in planned["muscles"])
    assert _map(client) == at_30
    assert _map(client, cycle=_kept(client)) == at_30
