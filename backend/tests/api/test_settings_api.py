"""/api/settings (ux-flow-plan C6): the bot's /settings on the web, same rules, owner-only."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.load import Increments, LoadKit
from training_coach.domain.queue import local_date
from training_coach.services import auth, user_settings
from training_coach.services.user_settings import Prefs
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
OTHER = 2  # a second person, as invites will add


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


@pytest.fixture
def moved(signed_in: TestClient) -> list[Prefs]:
    """The settings the bot's jobs were moved to, as the lifespan's hook would."""
    calls: list[Prefs] = []

    def reschedule(user: int, prefs: Prefs) -> None:
        assert user == OWNER  # whoever is signed in: here the owner
        calls.append(prefs)

    signed_in.app.state.reschedule = reschedule  # type: ignore[attr-defined]  # Starlette app
    return calls


def _today() -> date:
    return local_date(datetime.now(UTC), Settings().tz)


def _stored(engine: Engine) -> Prefs:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        return user_settings.load(mine)


def test_the_defaults_before_anything_is_changed(signed_in: TestClient) -> None:
    assert signed_in.get("/api/settings").json() == {
        "morning_time": "07:30",
        "nudge_time": "20:00",
        "nudges_enabled": True,
        "review_time": "19:00",
        "habits_enabled": True,
        "protein_g": None,
        "blocks_since": None,
        "pace": "standard",
        "sound": "ring",
        "extra_cardio_min": 0,
        "places": "home",
        "increments": {"barbell": 2.5, "dumbbells": 2.0, "machine": 5.0, "backpack": 1.0},
        "default_increments": {"barbell": 2.5, "dumbbells": 2.0, "machine": 5.0, "backpack": 1.0},
        "talk_test": False,
        "stop_signs_seen": False,
        "paused": False,
        "timezone": "Europe/Berlin",
    }


def test_a_new_time_is_saved_and_moves_the_bots_jobs(
    signed_in: TestClient, moved: list[Prefs], engine: Engine
) -> None:
    view = signed_in.patch("/api/settings", json={"morning_time": "6.45"}).json()
    assert view["morning_time"] == "06:45"
    assert view["nudge_time"] == "20:00"  # untouched
    (prefs,) = moved
    assert prefs.morning_time.isoformat() == "06:45:00"
    assert _stored(engine).morning_time == prefs.morning_time


def test_a_switch_leaves_the_jobs_where_they_are(
    signed_in: TestClient, moved: list[Prefs], engine: Engine
) -> None:
    view = signed_in.patch("/api/settings", json={"nudges_enabled": False, "paused": True}).json()
    assert (view["nudges_enabled"], view["paused"]) == (False, True)
    assert moved == []  # the jobs read these when they run
    assert _stored(engine).paused is True
    resumed = signed_in.patch("/api/settings", json={"paused": False}).json()
    assert resumed["paused"] is False


def test_a_second_persons_new_time_moves_only_their_own_jobs(engine: Engine) -> None:
    """Before, the web moved the bot's jobs (the owner's) whoever changed their times."""
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=OTHER))
    with session_scope(make_session_factory(engine, user_id=OTHER)) as bound:
        token = auth.create_link(bound, datetime.now(UTC))
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as other:
        assert other.post("/api/auth/redeem", json={"token": token}).status_code == 204
        calls: list[tuple[int, Prefs]] = []
        other.app.state.reschedule = lambda user, prefs: calls.append((user, prefs))  # type: ignore[attr-defined]  # Starlette app
        assert other.patch("/api/settings", json={"morning_time": "05:00"}).status_code == 200
    ((user, prefs),) = calls
    assert (user, prefs.morning_time) == (OTHER, time(5))
    assert _stored(engine).morning_time == time(7, 30)  # the owner's is untouched


@pytest.mark.parametrize("bad", ["7:5", "24:00", "07:60", "seven", ""])
def test_a_time_the_bot_would_refuse_is_refused(
    signed_in: TestClient, moved: list[Prefs], bad: str
) -> None:
    assert signed_in.patch("/api/settings", json={"nudge_time": bad}).status_code == 422
    assert moved == []


def test_the_protein_target_is_set_checked_and_cleared(signed_in: TestClient) -> None:
    assert signed_in.patch("/api/settings", json={"protein_g": 165}).json()["protein_g"] == 165
    for bad in (39, 401, -1):
        assert signed_in.patch("/api/settings", json={"protein_g": bad}).status_code == 422
    assert signed_in.get("/api/settings").json()["protein_g"] == 165
    assert signed_in.patch("/api/settings", json={"protein_g": 0}).json()["protein_g"] is None


def test_training_blocks_start_today_and_a_repeat_never_restarts_them(
    signed_in: TestClient, engine: Engine
) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        user_settings.update(mine, blocks=True, today=date(2026, 9, 1))
    again = signed_in.patch("/api/settings", json={"blocks": True}).json()
    assert again["blocks_since"] == "2026-09-01"
    assert signed_in.patch("/api/settings", json={"blocks": False}).json()["blocks_since"] is None
    started = signed_in.patch("/api/settings", json={"blocks": True}).json()
    assert started["blocks_since"] == _today().isoformat()


def test_habit_buttons_can_be_switched_off(signed_in: TestClient) -> None:
    assert (
        signed_in.patch("/api/settings", json={"habits_enabled": False}).json()["habits_enabled"]
        is False
    )


def test_the_pace_is_one_of_three(signed_in: TestClient, engine: Engine) -> None:
    assert signed_in.patch("/api/settings", json={"pace": "fast"}).json()["pace"] == "fast"
    assert _stored(engine).pace == "fast"
    assert signed_in.patch("/api/settings", json={"pace": "turbo"}).status_code == 422
    assert signed_in.get("/api/settings").json()["pace"] == "fast"


def test_the_timer_sound_is_one_of_six(signed_in: TestClient, engine: Engine) -> None:
    assert signed_in.patch("/api/settings", json={"sound": "wood"}).json()["sound"] == "wood"
    assert _stored(engine).sound == "wood"
    assert signed_in.patch("/api/settings", json={"sound": "ring"}).json()["sound"] == "ring"
    assert signed_in.patch("/api/settings", json={"sound": "gong"}).status_code == 422
    assert signed_in.patch("/api/settings", json={"sound": "none"}).json()["sound"] == "none"


def test_extra_cardio_a_week_adds_to_the_cardio_targets(
    signed_in: TestClient, engine: Engine
) -> None:
    """Walks or rides outside the sessions (ADR-0079): 0 to 600 minutes a week."""
    assert signed_in.patch("/api/settings", json={"extra_cardio_min": 60}).status_code == 200
    assert _stored(engine).extra_cardio_min == 60
    week = signed_in.get("/api/cardio").json()["week"]
    assert (week["zone2_target"], week["total_target"]) == ([60, 60], [60, 60])  # no plan here
    for refused in (-1, 601):
        assert (
            signed_in.patch("/api/settings", json={"extra_cardio_min": refused}).status_code == 422
        )
    assert (
        signed_in.patch("/api/settings", json={"extra_cardio_min": 0}).json()["extra_cardio_min"]
        == 0
    )


def test_where_you_train_is_home_gym_or_both(signed_in: TestClient, engine: Engine) -> None:
    """Places (ADR-0071): home until the person says otherwise, and only one of the three."""
    assert signed_in.patch("/api/settings", json={"places": "both"}).json()["places"] == "both"
    assert _stored(engine).places == "both"
    assert signed_in.patch("/api/settings", json={"places": "away"}).status_code == 422
    assert signed_in.patch("/api/settings", json={"places": "gym"}).json()["places"] == "gym"


def test_a_persons_own_weight_steps_replace_the_defaults(
    signed_in: TestClient, engine: Engine
) -> None:
    """ADR-0072: each person can change theirs; only the kits sent change, and setting the
    default back keeps no step of their own."""
    changed = signed_in.patch("/api/settings", json={"increments": {"barbell": 1.25}}).json()
    assert changed["increments"] == {
        "barbell": 1.25,
        "dumbbells": 2.0,
        "machine": 5.0,
        "backpack": 1.0,
    }
    assert changed["default_increments"]["barbell"] == 2.5
    signed_in.patch("/api/settings", json={"increments": {"machine": 2.5, "backpack": 0.5}})
    assert _stored(engine).increments == Increments(barbell=1.25, machine=2.5, backpack=0.5)
    for bad in (0, 0.1, 1.3, 25):
        body = {"increments": {"dumbbells": bad}}
        assert signed_in.patch("/api/settings", json=body).status_code == 422
    signed_in.patch("/api/settings", json={"increments": {"barbell": 2.5, "backpack": 1}})
    assert _stored(engine).increments == Increments(machine=2.5)


def test_a_second_persons_weight_steps_are_their_own(engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=OTHER))
    with session_scope(make_session_factory(engine, user_id=OTHER)) as theirs:
        user_settings.update(theirs, increments={LoadKit.DUMBBELLS: 1.0})
    with session_scope(make_session_factory(engine, user_id=OTHER)) as theirs:
        assert user_settings.load(theirs).increments == Increments(dumbbells=1.0)
    assert _stored(engine).increments == Increments()  # the owner's are untouched


def test_the_talk_test_is_a_switch_asked_without_a_reason(
    signed_in: TestClient, engine: Engine
) -> None:
    """ADR-0083: a preference, not medical: only the switch is stored, no why."""
    assert signed_in.patch("/api/settings", json={"talk_test": True}).json()["talk_test"] is True
    assert _stored(engine).talk_test is True
    assert signed_in.patch("/api/settings", json={"talk_test": "yes, AF"}).status_code == 422
    assert signed_in.patch("/api/settings", json={"talk_test": False}).json()["talk_test"] is False


def test_the_stop_signs_are_remembered_as_seen_per_person(engine: Engine) -> None:
    """Spec B7: shown once before the first guided session, kept on the server for each
    person, not in one browser."""
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=OTHER))
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert user_settings.update(mine, stop_signs_seen=True).stop_signs_seen is True
    assert _stored(engine).stop_signs_seen is True
    with session_scope(make_session_factory(engine, user_id=OTHER)) as theirs:
        assert user_settings.load(theirs).stop_signs_seen is False


def test_the_seen_flag_is_saved_through_the_api(signed_in: TestClient, engine: Engine) -> None:
    view = signed_in.patch("/api/settings", json={"stop_signs_seen": True}).json()
    assert view["stop_signs_seen"] is True
    assert signed_in.get("/api/settings").json()["stop_signs_seen"] is True


def test_signed_out_gets_nothing(client: TestClient) -> None:
    assert client.get("/api/settings").status_code == 401
    assert client.patch("/api/settings", json={"paused": True}).status_code == 401
    for change in ({"talk_test": True}, {"stop_signs_seen": True}):  # owner-only (spec B7)
        assert client.patch("/api/settings", json=change).status_code == 401
