"""Two people on the plan: what builder step 5 (plans per person, ADR-0073) must keep and make true.

The canary in ``test_two_people`` puts marks in each person's rows. Here one person moves through
the plan (logs a day, pushes a session, changes a level) and the other's answers must not move.
That holds on today's shared plan and must keep holding after step 5.

The ``xfail(strict=True)`` tests are what only step 5 makes true: an edit to my sessions leaves
yours alone, the Plan page and body map read my own sessions, a session id and a plan version
belong to one person, and the seed stops changing anyone's sessions. They fail on the shared
plan today; step 5 removes the markers, and each must then pass. The read inventory behind
them: ``docs/specs/plans-per-person.md``.
"""

import io
import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine, select

from tests.routes import api_routes
from training_coach.api.app import create_app
from training_coach.api.auth import owner
from training_coach.config import Settings
from training_coach.db.models import PlanVersion, SessionTemplate, TemplateItem, User, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import ai_summary, auth, seed, users

ORIGIN = "https://coach.example.com"
NOW = datetime(2026, 10, 12, 10, tzinfo=UTC)  # a Monday
TODAY = NOW.date()
# True only once step 5 lands. raises: an error (a broken test) is not an expected failure.
STEP_5 = pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="builder step 5 (ADR-0073): sessions and plan versions become each person's own",
)
Pair = tuple[FastAPI, dict[int, TestClient], Engine]


def _first_session(engine: Engine, user: int) -> int:
    """The id of the first session in ``user``'s cycle, as their own bound session sees it."""
    with make_session_factory(engine, user_id=user)() as bound:
        found = bound.scalars(select(SessionTemplate.id).order_by(SessionTemplate.position))
        return found.first() or 0


@pytest.fixture
def pair(engine: Engine) -> Iterator[Pair]:
    """The owner (user 1) and a member (user 2), both on the plan's starting rows and each
    signed in on their own browser."""
    with time_machine.travel(NOW, tick=False):
        with session_scope(make_session_factory(engine)) as s:
            # The migration made the owner on the real clock, after NOW: a month back instead.
            s.get_one(User, 1).created_at = NOW - timedelta(days=30)
            s.add(User(id=2))
            s.flush()
            seed.apply_seed(s, seed.bundled_plan())
        settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
        app = create_app(settings)
        with TestClient(app, base_url=ORIGIN) as first:
            clients = {1: first, 2: TestClient(app, base_url=ORIGIN)}
            for user, client in clients.items():
                with make_session_factory(engine, user_id=user)() as bound:
                    token = auth.create_link(bound, NOW)
                    bound.commit()
                assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
            yield app, clients, engine


def _readable(response: Response) -> bytes:
    """The body; an export's data less the export events each export adds (its photos are
    the canary's)."""
    if response.headers.get("content-type") != "application/zip":
        return response.content
    with zipfile.ZipFile(io.BytesIO(response.content)) as zipped:
        data = json.loads(zipped.read("data.json"))
    events = data["tables"]["events"]
    data["tables"]["events"] = [e for e in events if e["kind"] != "account.exported"]
    return json.dumps(data).encode()


def _reads(app: FastAPI, client: TestClient, engine: Engine, user: int) -> dict[str, bytes]:
    """Every signed-in GET route without a path parameter (those are the canary's), and the
    summary an AI reads over MCP."""
    queries = {
        "/api/log/plan": {"day": TODAY.isoformat(), "template_id": _first_session(engine, user)},
        "/api/equipment/unlocks": {"add": "kettlebell:16"},
    }
    answers: dict[str, bytes] = {}
    for path, route in api_routes(app):
        calls = {dependency.call for dependency in route.dependant.dependencies}
        if "GET" not in (route.methods or set()) or owner not in calls or "{" in path:
            continue
        response = client.get(path, params=queries.get(path))
        assert response.status_code == 200, f"{path}: {response.status_code}"
        answers[path] = _readable(response)
    with make_session_factory(engine, user_id=user)() as bound:
        everything = ai_summary.Options(weeks=None)
        answers["mcp get_summary"] = ai_summary.summary(bound, TODAY, everything).encode()
    return answers


def _today(client: TestClient) -> object:
    return client.get("/api/session/today").json()["session"]


def _move_through_the_plan(client: TestClient, engine: Engine, user: int) -> None:
    """Log yesterday's planned session at its targets, push today's, change a level."""
    yesterday = TODAY - timedelta(days=1)
    first = _first_session(engine, user)
    plan = client.get(
        "/api/log/plan", params={"day": yesterday.isoformat(), "template_id": first}
    ).json()
    sets = [
        {"item": i, "set_no": n + 1, "left": target}
        for i, item in enumerate(plan["items"])
        for n, target in enumerate(item["targets"])
    ]
    body = {
        "token": "ab" * 16,
        "day": yesterday.isoformat(),
        "what": "session",
        "template_id": first,
        "sets": sets,
    }
    assert client.post("/api/log", json=body).status_code == 200
    shown = _today(client)
    assert isinstance(shown, dict)
    pushed = client.post("/api/today/push", json={"template_id": shown["template_id"]})
    assert pushed.status_code == 200
    standing = next(s for s in client.get("/api/progress").json()["standings"] if s["steps"] > 1)
    other_step = next(r["id"] for r in standing["ladder"] if r["id"] != standing["step_id"])
    moved = client.post(f"/api/progress/{standing['slug']}/level", json={"step_id": other_step})
    assert moved.status_code == 200


@pytest.mark.parametrize(("me", "other"), [(2, 1), (1, 2)], ids=["member", "owner"])
def test_the_others_progress_through_the_plan_changes_nothing_i_see(
    pair: Pair, me: int, other: int
) -> None:
    app, clients, engine = pair
    before = _reads(app, clients[me], engine, me)
    _move_through_the_plan(clients[other], engine, other)
    after = _reads(app, clients[me], engine, me)

    assert _today(clients[other]) is None  # their day moved on: pushed to tomorrow
    assert _today(clients[me]) is not None
    assert len(before) >= 30, sorted(before)
    changed = sorted(path for path in before if before[path] != after[path])
    assert not changed, f"the other person's progress changed what I see: {changed}"


def _edit_first_session(engine: Engine, user: int, name: str) -> None:
    """What step 6's editor will do, done by hand: rename a session and add sets to its first
    exercise, through a session bound to ``user``."""
    with session_scope(make_session_factory(engine, user_id=user)) as bound:
        template = bound.scalars(select(SessionTemplate).order_by(SessionTemplate.position)).first()
        assert template is not None
        template.name = name
        template.items[0].sets += 2


@STEP_5
def test_my_edit_to_my_sessions_leaves_the_others_plan_alone(pair: Pair) -> None:
    app, clients, engine = pair
    paths = ("/api/session/today", "/api/log", "/api/log/plan", "/api/plan", "/api/plan/coverage")
    before = {p: v for p, v in _reads(app, clients[1], engine, 1).items() if p in paths}
    _edit_first_session(engine, 2, "Bravoplan")
    after = {p: v for p, v in _reads(app, clients[1], engine, 1).items() if p in paths}
    assert before == after


@STEP_5
@pytest.mark.parametrize("path", ["/api/plan", "/api/plan/coverage"])
def test_the_plan_page_and_body_map_read_my_own_sessions(pair: Pair, path: str) -> None:
    """Both read plan.toml today (``api/plan.build_plan_view``, ``services/coverage``), so an
    edit in the database never shows there."""
    _, clients, engine = pair
    before = clients[2].get(path).content
    _edit_first_session(engine, 2, "Bravoplan")
    assert clients[2].get(path).content != before


@STEP_5
def test_a_session_and_its_items_belong_to_one_person(pair: Pair) -> None:
    _, _, engine = pair
    with make_session_factory(engine, user_id=1)() as bound:
        state = users.plan_state(bound)
        assert state is not None
        theirs = state.next_template_id
    with make_session_factory(engine, user_id=2)() as bound:
        assert bound.get(SessionTemplate, theirs) is None
        assert (
            bound.scalars(select(TemplateItem).where(TemplateItem.template_id == theirs)).all()
            == []
        )


@STEP_5
def test_a_plan_version_i_save_never_lands_on_the_others_workouts(pair: Pair) -> None:
    """A workout takes the version in force on its date in the INSERT itself (ADR-0034,
    ``models._plan_version``). Flush statements skip the run-time binding, so step 5 must
    scope that lookup to the workout's person by hand."""
    _, _, engine = pair
    with session_scope(make_session_factory(engine, user_id=2)) as bound:
        bound.add(PlanVersion(since=TODAY, name="Bravoversion"))
    with session_scope(make_session_factory(engine, user_id=1)) as bound:
        workout = Workout(local_date=TODAY, status=WorkoutStatus.REST)
        bound.add(workout)
        bound.flush()
        recorded = bound.get(PlanVersion, workout.plan_version_id)
        assert recorded is not None
        assert recorded.name != "Bravoversion"


@STEP_5
def test_the_seed_changes_nobodys_sessions(pair: Pair) -> None:
    """After the copy a starter change reaches only people who join later (ADR-0073)."""
    _, clients, engine = pair
    before = {user: _today(client) for user, client in clients.items()}
    plan = seed.bundled_plan()
    first = plan.sessions[0]
    more = first.items[0].model_copy(update={"sets": first.items[0].sets + 1})
    changed = first.model_copy(update={"items": [more, *first.items[1:]]})
    with session_scope(make_session_factory(engine)) as shared:
        seed.apply_seed(shared, plan.model_copy(update={"sessions": [changed, *plan.sessions[1:]]}))
    assert {user: _today(client) for user, client in clients.items()} == before
