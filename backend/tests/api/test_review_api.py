"""/api/review (ux-flow-plan C4): the bot's weekly review on the web, owner-only."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
import time_machine
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Exercise, SetLog, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.habits import Habit
from training_coach.services import ai_comment, ai_key, auth, habits, users
from training_coach.services.secret_box import SecretBox
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
NOW = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)  # a Wednesday
MONDAY = date(2026, 10, 5)


SECRETS = Fernet.generate_key().decode()


def _client(engine: Engine, secrets_key: str | None) -> Iterator[TestClient]:
    with time_machine.travel(NOW, tick=False):
        with session_scope(make_session_factory(engine)) as shared:
            apply_seed(shared, load_plan())
        with make_session_factory(engine, user_id=OWNER)() as bound:
            token = auth.create_link(bound, datetime.now(UTC))
            bound.commit()
        settings = Settings(
            environment="test",
            database_url=str(engine.url),
            public_url=ORIGIN,
            secrets_key=SecretStr(secrets_key) if secrets_key else None,
        )
        with TestClient(create_app(settings), base_url=ORIGIN) as client:
            assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
            yield client


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    yield from _client(engine, None)


@pytest.fixture
def commented(engine: Engine) -> Iterator[TestClient]:
    """AI comments on (ADR-0047 B), with last week's and this week's comment kept."""
    for client in _client(engine, SECRETS):
        with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
            ai_key.store(mine, SecretBox(SecretStr(SECRETS)), SecretStr("gsk_" + "ab" * 16))
            ai_comment.store(mine, MONDAY - timedelta(days=7), "Last week.", NOW)
            ai_comment.store(mine, MONDAY, "Sleep more.\n<b>Not bold</b>", NOW)
        yield client


def _log(engine: Engine, slug: str, values: list[int], on: date) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        exercise = mine.scalars(select(Exercise).where(Exercise.slug == slug)).one()
        state = users.exercise_state(mine, exercise.id)
        assert state is not None
        workout = Workout(local_date=on, status=WorkoutStatus.DONE)
        workout.sets = [
            SetLog(
                exercise_id=exercise.id,
                ladder_step_id=state.ladder_step_id,
                set_no=n,
                side=Side.BOTH,
                value=v,
            )
            for n, v in enumerate(values, start=1)
        ]
        mine.add(workout)


def test_this_week_so_far_as_the_bot_counts_it(signed_in: TestClient, engine: Engine) -> None:
    _log(engine, "zone2", [45], date(2026, 10, 6))
    _log(engine, "zone2", [30], date(2026, 10, 4))  # last week's Sunday: not counted
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        habits.toggle(mine, MONDAY, Habit.WIND_DOWN, MONDAY)
    view = signed_in.get("/api/review").json()
    assert (view["start"], view["current"]) == ("2026-10-05", True)
    assert (view["previous"], view["next"]) == ("2026-09-28", None)
    assert (view["planned"], view["done"], view["extras"]) == (7, 0, 1)
    assert view["zone2_minutes"] == 45
    assert view["sets_target"] == [10, 20]
    assert {"label": "Wind-down", "done": 1, "days": 3} in view["habits"]
    assert view["ai_comments"] is False
    assert view["ai_comment"] is None


def test_the_kept_ai_comment_comes_with_its_week(commented: TestClient) -> None:
    view = commented.get("/api/review").json()
    assert view["ai_comments"] is True
    assert view["ai_comment"] == "Sleep more.\n<b>Not bold</b>"  # text as kept, for the page
    earlier = commented.get("/api/review", params={"week": "2026-09-30"}).json()
    assert earlier["ai_comment"] == "Last week."
    older = commented.get("/api/review", params={"week": "2026-09-21"}).json()
    assert older["ai_comment"] is None


def test_no_ai_comment_after_7_days(commented: TestClient) -> None:
    with time_machine.travel(NOW + timedelta(days=7, minutes=1), tick=False):
        view = commented.get("/api/review", params={"week": MONDAY.isoformat()}).json()
    assert view["ai_comment"] is None


def test_no_ai_comment_with_comments_off(commented: TestClient, engine: Engine) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        ai_key.options(mine, enabled=False, body=False, readiness=False)
    view = commented.get("/api/review").json()
    assert (view["ai_comments"], view["ai_comment"]) == (False, None)


def test_an_earlier_week_is_counted_to_its_sunday(signed_in: TestClient, engine: Engine) -> None:
    _log(engine, "zone2", [30], date(2026, 10, 4))
    view = signed_in.get("/api/review", params={"week": "2026-10-01"}).json()
    assert (view["start"], view["current"]) == ("2026-09-28", False)
    assert view["next"] == "2026-10-05"
    assert view["zone2_minutes"] == 30
    assert view["ready"] == []  # today's standing says nothing about that week


def test_a_step_down_suggested_this_week_links_to_the_plan(
    signed_in: TestClient, engine: Engine
) -> None:
    """ADR-0084: pull-ups out of reach twice after the baseline (4 sets of 5-12)."""
    for day in (5, 6, 7):
        _log(engine, "pull-up", [2, 2, 2, 2], date(2026, 10, day))
    view = signed_in.get("/api/review").json()
    assert view["step_down"] == [{"exercise": "Pull-up", "slug": "pull-up"}]
    earlier = signed_in.get("/api/review", params={"week": "2026-10-01"}).json()
    assert earlier["step_down"] == []


def test_a_week_that_has_not_started_is_refused(signed_in: TestClient) -> None:
    assert signed_in.get("/api/review", params={"week": "2026-10-12"}).status_code == 422
    assert signed_in.get("/api/review", params={"week": "soon"}).status_code == 422


def test_signed_out_gets_nothing(client: TestClient) -> None:
    assert client.get("/api/review").status_code == 401
