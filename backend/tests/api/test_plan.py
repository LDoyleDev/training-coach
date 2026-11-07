from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import SessionProgress, SessionTemplate, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import auth, plan_import
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    """Signed in: the plan is private like every page (ADR-0041)."""
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as signed_in:
        with make_session_factory(engine, user_id=OWNER)() as bound:
            token = auth.create_link(bound, datetime.now(UTC))
            bound.commit()
        assert signed_in.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield signed_in


def test_the_import_lists_nothing_while_the_plan_matches_the_file(client: TestClient) -> None:
    assert client.get("/api/plan/import").json() == {
        "changes": [],
        "blocked": None,
        "version": None,
    }
    assert client.post("/api/plan/import").json()["changes"] == []


def _edited_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """plan.toml as it would be after a release: its first session one set longer."""
    plan = load_plan()
    first = plan.sessions[0]
    more = first.items[0].model_copy(update={"sets": first.items[0].sets + 1})
    changed = first.model_copy(update={"items": [more, *first.items[1:]]})
    edited = plan.model_copy(update={"sessions": [changed, *plan.sessions[1:]]})
    monkeypatch.setattr("training_coach.api.plan.bundled_plan", lambda: edited)


def test_the_import_saves_what_it_listed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _edited_file(monkeypatch)
    listed = client.get("/api/plan/import").json()
    assert len(listed["changes"]) == 1
    assert client.post("/api/plan/import").json()["changes"] == listed["changes"]
    assert client.get("/api/plan/import").json()["changes"] == []


def test_the_import_answers_a_conflict_with_a_session_in_progress(
    client: TestClient, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _edited_file(monkeypatch)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        template = bound.scalars(select(SessionTemplate).order_by(SessionTemplate.position)).first()
        assert template is not None
        today = local_date(datetime.now(UTC), Settings().tz)
        kept = [{"item": 0, "set_no": 1, "left": 8}]
        bound.add(
            SessionProgress(local_date=today, template_id=template.id, token="ab" * 16, sets=kept)
        )
    assert client.get("/api/plan/import").json()["blocked"] == plan_import.IN_PROGRESS
    assert client.post("/api/plan/import").status_code == 409


def test_anyone_else_is_refused_the_import(engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
        shared.flush()
        apply_seed(shared, load_plan())
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as member:
        with make_session_factory(engine, user_id=2)() as bound:
            token = auth.create_link(bound, datetime.now(UTC))
            bound.commit()
        assert member.post("/api/auth/redeem", json={"token": token}).status_code == 204
        assert member.get("/api/plan/import").json()["changes"] == []
        assert member.post("/api/plan/import").status_code == 403


def _draft(client: TestClient, sets: int) -> dict[str, object]:
    edit = client.get("/api/plan/edit").json()
    first = edit["sessions"][0]
    items = [
        {k: i[k] for k in ("exercise", "sets", "rep_min", "rep_max", "per_side", "pair")}
        for i in first["home"]
    ]
    items[0]["sets"] = sets
    return {
        "revision": edit["revision"],
        "note": "One more set",
        "versions": [{"slug": first["slug"], "place": "home", "items": items}],
    }


def test_the_editor_gets_every_version_and_the_catalogue(client: TestClient) -> None:
    edit = client.get("/api/plan/edit").json()
    plan = load_plan()
    assert [s["slug"] for s in edit["sessions"]] == [s.slug for s in plan.sessions]
    assert any(s["away"] for s in edit["sessions"])
    slugs = {e["slug"] for e in edit["catalogue"]}
    assert slugs == {e.slug for e in plan.exercises if not e.retired}
    assert all("gym" in e["places"] for e in edit["catalogue"])


def test_saving_a_draft_shows_on_the_plan_and_makes_a_version(client: TestClient) -> None:
    body = _draft(client, 9)
    saved = client.post("/api/plan/changes", json=body)
    assert saved.status_code == 200
    assert saved.json()["version"] == "One more set"
    assert saved.json()["revision"] == client.get("/api/plan/edit").json()["revision"]
    assert client.get("/api/plan").json()["sessions"][0]["exercises"][0]["sets"] == 9


def test_a_stale_draft_is_a_conflict(client: TestClient) -> None:
    body = _draft(client, 9)
    assert client.post("/api/plan/changes", json=body).status_code == 200
    late = client.post("/api/plan/changes", json={**body, "note": "Late"})
    assert late.status_code == 409
    assert late.json()["detail"] == "stale"


def test_a_session_in_progress_is_a_conflict(client: TestClient, engine: Engine) -> None:
    body = _draft(client, 9)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        template = bound.scalars(select(SessionTemplate).order_by(SessionTemplate.position)).first()
        assert template is not None
        today = local_date(datetime.now(UTC), Settings().tz)
        kept = [{"item": 0, "set_no": 1, "left": 8}]
        bound.add(
            SessionProgress(local_date=today, template_id=template.id, token="ab" * 16, sets=kept)
        )
    late = client.post("/api/plan/changes", json=body)
    assert late.status_code == 409
    assert late.json()["detail"] == "in-progress"


def test_what_the_app_couldnt_run_is_refused_with_the_reason(client: TestClient) -> None:
    body = _draft(client, 9)
    versions = body["versions"]
    assert isinstance(versions, list)
    versions[0]["items"][0]["exercise"] = "no-such"
    refused = client.post("/api/plan/changes", json=body)
    assert refused.status_code == 422
    assert "catalogue" in refused.json()["detail"]


@pytest.mark.parametrize(
    "change",
    [{"note": ""}, {"versions": []}],
    ids=["no-note", "nothing-to-save"],
)
def test_a_draft_needs_a_note_and_something_in_it(
    client: TestClient, change: dict[str, object]
) -> None:
    body = {**_draft(client, 9), **change}
    assert client.post("/api/plan/changes", json=body).status_code == 422


def test_the_map_follows_a_draft_and_saves_nothing(client: TestClient) -> None:
    before = client.get("/api/plan/coverage", params={"place": "home"}).json()
    draft = _draft(client, 20)
    versions = draft["versions"]
    assert isinstance(versions, list)
    body = {
        "place": "home",
        "versions": [
            {
                "slug": v["slug"],
                "place": v["place"],
                "items": [
                    {k: i[k] for k in ("exercise", "sets", "rep_min", "rep_max", "per_side")}
                    for i in v["items"]
                ],
            }
            for v in versions
        ],
    }
    drafted = client.post("/api/plan/coverage/draft", json=body)
    assert drafted.status_code == 200
    sets = lambda view: sum(m["sets"] for m in view["muscles"])  # noqa: E731 - one use
    assert sets(drafted.json()) > sets(before)
    assert client.get("/api/plan/coverage", params={"place": "home"}).json() == before


def test_an_empty_draft_is_the_plan_as_it_stands(client: TestClient) -> None:
    before = client.get("/api/plan/coverage", params={"place": "home"}).json()
    drafted = client.post("/api/plan/coverage/draft", json={"place": "home", "versions": []})
    assert drafted.json() == before


def _sessions(view: dict[str, Any]) -> dict[str, Any]:
    return {s["slug"]: s for s in view["sessions"]}


def test_the_bundled_plan_raises_neither_week_warning(client: TestClient) -> None:
    for place in ("home", "gym"):
        view = client.get("/api/plan/coverage", params={"place": place}).json()
        assert view["push_sets"] > 0
        assert view["pull_sets"] > 0
        assert not view["pushing_without_pulling"]
        assert not any(s["over_an_hour"] for s in view["sessions"]), place


def test_the_map_flags_a_draft_over_an_hour(client: TestClient) -> None:
    slug = client.get("/api/plan/edit").json()["sessions"][0]["slug"]
    item = {"exercise": "push-up", "sets": 20, "rep_min": 5, "rep_max": 10}
    body = {
        "place": "home",
        "versions": [{"slug": slug, "place": "home", "items": [item, {**item, "sets": 20}]}],
    }
    view = client.post("/api/plan/coverage/draft", json=body).json()
    assert _sessions(view)[slug]["minutes"] > 60
    assert _sessions(view)[slug]["over_an_hour"]
    assert view["push_sets"] >= 40


def test_a_pair_in_a_draft_makes_it_shorter(client: TestClient) -> None:
    slug = client.get("/api/plan/edit").json()["sessions"][0]["slug"]
    first = {"exercise": "push-up", "sets": 4, "rep_min": 5, "rep_max": 10}
    second = {"exercise": "doorway-row", "sets": 4, "rep_min": 5, "rep_max": 10}

    def minutes(pair: int | None) -> int:
        items = [{**first, "pair": pair}, {**second, "pair": pair}]
        body = {"place": "home", "versions": [{"slug": slug, "place": "home", "items": items}]}
        view = client.post("/api/plan/coverage/draft", json=body).json()
        minutes: int = _sessions(view)[slug]["minutes"]
        return minutes

    assert minutes(1) < minutes(None)


def test_the_catalogue_says_who_an_exercise_is_for_and_what_it_needs(client: TestClient) -> None:
    catalogue = {e["slug"]: e for e in client.get("/api/plan/edit").json()["catalogue"]}
    assert catalogue["push-up"]["first_step"] == "Hands on a wall"
    assert catalogue["push-up"]["levels"] == [1, 6]
    assert catalogue["push-up"]["needs"] == []
    assert catalogue["band-row"]["needs"] == ["a light band"]
    assert catalogue["seated-leg-curl"]["lengthened"]
    assert not catalogue["push-up"]["lengthened"]


def test_a_muscle_names_what_would_add_to_it_where_it_can_be_done(client: TestClient) -> None:
    for place in ("home", "gym"):
        view = client.get("/api/plan/coverage", params={"place": place}).json()
        names = {e["name"]: e for e in client.get("/api/plan/edit").json()["catalogue"]}
        for m in view["muscles"]:
            counted = {s["exercise"] for s in m["sources"]}
            assert len(m["adds"]) <= 4
            for name in m["adds"]:
                assert place in names[name]["places"], (place, name)
                assert names[name]["muscles"].get(m["muscle"]) == 1
                assert name not in counted


def test_a_lengthened_pick_comes_first_in_what_would_add(client: TestClient) -> None:
    view = client.get("/api/plan/coverage", params={"place": "gym"}).json()
    lengthened = {
        e["name"] for e in client.get("/api/plan/edit").json()["catalogue"] if e["lengthened"]
    }
    for m in view["muscles"]:
        flags = [name in lengthened for name in m["adds"]]
        assert flags == sorted(flags, reverse=True), m["muscle"]


def _draft_of(slug: str, exercise: str) -> dict[str, object]:
    item = {"exercise": exercise, "sets": 20, "rep_min": 5, "rep_max": 10}
    return {"place": "home", "versions": [{"slug": slug, "place": "home", "items": [item]}]}


def test_a_draft_session_i_dont_have_is_ignored(client: TestClient) -> None:
    """The map draws what it can of a draft; saving is where a bad one is refused."""
    before = client.get("/api/plan/coverage", params={"place": "home"}).json()
    drafted = client.post("/api/plan/coverage/draft", json=_draft_of("no-such", "pull-up"))
    assert drafted.status_code == 200
    assert drafted.json() == before


def test_a_draft_exercise_the_catalogue_doesnt_know_counts_for_nothing(client: TestClient) -> None:
    slug = client.get("/api/plan/edit").json()["sessions"][0]["slug"]
    drafted = client.post("/api/plan/coverage/draft", json=_draft_of(slug, "no-such"))
    assert drafted.status_code == 200
    without = client.post("/api/plan/coverage/draft", json={"place": "home", "versions": []})
    assert sum(m["sets"] for m in drafted.json()["muscles"]) < sum(
        m["sets"] for m in without.json()["muscles"]
    )


@pytest.mark.parametrize(
    "body",
    [
        {"place": "home", "versions": [{"slug": "x", "place": "home", "items": []}] * 31},
        {
            "place": "home",
            "versions": [
                {
                    "slug": "x",
                    "place": "home",
                    "items": [{"exercise": "a", "sets": 1, "rep_min": 1, "rep_max": 2}] * 41,
                }
            ],
        },
        {
            "place": "home",
            "versions": [
                {
                    "slug": "x",
                    "place": "home",
                    "items": [{"exercise": "a", "sets": 21, "rep_min": 1, "rep_max": 2}],
                }
            ],
        },
    ],
    ids=["too-many-versions", "too-many-items", "too-many-sets"],
)
def test_a_draft_past_its_limits_is_refused(client: TestClient, body: dict[str, object]) -> None:
    assert client.post("/api/plan/coverage/draft", json=body).status_code == 422


def test_the_plan_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as stranger:
        assert stranger.get("/api/plan").status_code == 401
        empty = {"place": "home", "versions": []}
        assert stranger.post("/api/plan/coverage/draft", json=empty).status_code == 401


def test_plan_endpoint_returns_the_week_in_queue_order(client: TestClient) -> None:
    body = client.get("/api/plan").json()
    plan = load_plan()
    assert [s["slug"] for s in body["sessions"]] == [s.slug for s in plan.sessions]
    assert [s["position"] for s in body["sessions"]] == list(range(len(plan.sessions)))
    assert {s["type"] for s in body["sessions"]} == {"strength", "conditioning", "recovery"}


def test_plan_endpoint_exercise_details(client: TestClient) -> None:
    torso = next(s for s in client.get("/api/plan").json()["sessions"] if s["slug"] == "torso")
    pull_up = next(e for e in torso["exercises"] if e["slug"] == "pull-up")
    assert pull_up["ladder"][pull_up["start_step"]] == "Strict pull-up"
    assert torso["total_sets"] == sum(e["sets"] for e in torso["exercises"])


def test_each_session_lists_its_gym_version(client: TestClient) -> None:
    by_slug = {s["slug"]: s for s in client.get("/api/plan").json()["sessions"]}
    gym = {s.slug: [i.exercise for i in s.gym] for s in load_plan().sessions}
    assert {slug: [e["slug"] for e in s["gym"]] for slug, s in by_slug.items()} == gym
    legs = by_slug["legs"]
    assert "hip-thrust" in [e["slug"] for e in legs["gym"]]
    assert "hip-thrust" not in [e["slug"] for e in legs["exercises"]]  # still the home version
    assert legs["total_sets"] == sum(e["sets"] for e in legs["exercises"])
    assert by_slug["recovery"]["gym"] == []  # done the same way at the gym


def test_plan_endpoint_volume_excludes_qualities(client: TestClient) -> None:
    body = client.get("/api/plan").json()
    groups = {v["group"] for v in body["volume"]}
    assert "quads" in groups
    assert not groups & {"conditioning", "mobility", "power", "posture"}
    assert (body["volume_target_min"], body["volume_target_max"]) == (10, 20)


def test_plan_endpoint_has_security_headers(client: TestClient) -> None:
    response = client.get("/api/plan")
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_plan_endpoint_exposes_only_static_plan_fields(client: TestClient) -> None:
    """ADR-0019: /api/plan was public, so its shape is locked (owner-only since ADR-0041).
    Adding a field (above all any
    per-user progress, log or measurement) must be a deliberate change to this test and the ADR.
    """
    body = client.get("/api/plan").json()
    assert set(body) == {"sessions", "volume", "volume_target_min", "volume_target_max"}
    assert {k for s in body["sessions"] for k in s} == {
        "position",
        "slug",
        "name",
        "focus",
        "type",
        "optional",
        "total_sets",
        "exercises",
        "gym",
    }
    listed = [e for s in body["sessions"] for e in (*s["exercises"], *s["gym"])]
    assert {k for e in listed for k in e} == {
        "slug",
        "name",
        "kind",
        "sets",
        "rep_min",
        "rep_max",
        "per_side",
        "muscles",
        "qualities",
        "pattern",
        "ladder",
        "start_step",
    }
    assert {k for v in body["volume"] for k in v} == {"group", "sets"}
