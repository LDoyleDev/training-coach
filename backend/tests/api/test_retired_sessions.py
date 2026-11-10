"""A retired session (ADR-0093): no route offers it, and its old days keep its name.

Nothing in the app retires a session yet, so the test does it as the cycle edit will: the day it
went, its items deleted, parked at position 10_000 + id, the cycle closed up behind it. The queue
is left naming it in ``queued``, as an old swap could."""

import io
import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from tests import factories
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import (
    Exercise,
    LadderStep,
    PlanState,
    SessionTemplate,
    SetLog,
    Workout,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import WorkoutStatus
from training_coach.domain.queue import local_date
from training_coach.services import ai_summary, auth, erase, export, today, workout_log
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

NAME = "High intensity"  # the owner's fifth session
TZ = ZoneInfo("Europe/Berlin")
# Every page that offers the cycle's sessions, or counts them.
OFFERED = [
    "/api/today/choices",  # the pick menu
    "/api/log",  # the Log page's sessions
    "/api/plan",
    "/api/plan/edit",
    "/api/progress/times",
]
ALSO_CLEAN = ["/api/session/today", "/api/plan/coverage", "/api/progress"]


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


def _today() -> datetime:
    return datetime.now(UTC)


def _done_two_days_ago(engine: Engine) -> int:
    """The session done, timed, two days ago; the queue back at the first session. Its id."""
    now = _today()
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        hiit = mine.scalars(select(SessionTemplate).where(SessionTemplate.name == NAME)).one()
        workout = Workout(
            local_date=local_date(now, TZ) - timedelta(days=2),
            template_id=hiit.id,
            status=WorkoutStatus.DONE,
        )
        mine.add(workout)
        mine.flush()
        exercise = mine.scalars(select(Exercise).order_by(Exercise.id)).first()
        assert exercise is not None
        step = mine.scalars(
            select(LadderStep.id).where(LadderStep.exercise_id == exercise.id)
        ).first()
        assert step is not None
        started = now - timedelta(days=2)
        mine.add(
            SetLog(
                workout_id=workout.id,
                exercise_id=exercise.id,
                ladder_step_id=step,
                set_no=1,
                value=10,
                started_at=started,
                done_at=started + timedelta(minutes=20),
            )
        )
        first = mine.scalars(select(SessionTemplate).order_by(SessionTemplate.position)).first()
        assert first is not None
        state = mine.scalars(select(PlanState)).one()
        state.next_template_id, state.queued = first.id, [hiit.id]
        return hiit.id


def _retire(engine: Engine, hiit_id: int) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        on = local_date(_today(), TZ) - timedelta(days=1)
        factories.retire(mine, mine.get_one(SessionTemplate, hiit_id), on)


def _week(engine: Engine) -> list[str]:
    with make_session_factory(engine, user_id=OWNER)() as mine:
        found = today.week(mine, local_date(_today(), TZ), days=7)
        assert found is not None
        return [d.session for d in found]


def _typed(engine: Engine, text: str) -> workout_log.Draft:
    with make_session_factory(engine, user_id=OWNER)() as mine:
        return workout_log.draft(mine, text, local_date(_today(), TZ), TZ)


def _summary(engine: Engine) -> str:
    with make_session_factory(engine, user_id=OWNER)() as mine:
        everything = ai_summary.Options(weeks=None)
        return ai_summary.summary(mine, local_date(_today(), TZ), everything)


def _planned(client: TestClient) -> int:
    return int(client.get("/api/review").json()["planned"])


def test_a_retired_session_is_offered_nowhere_and_its_old_days_keep_its_name(
    client: TestClient, engine: Engine
) -> None:
    hiit = _done_two_days_ago(engine)
    for path in OFFERED:  # offered before it goes
        assert NAME in client.get(path).text, path
    assert NAME in _week(engine)
    assert _typed(engine, f"{NAME}\npull-ups 8").template_id == hiit
    assert _planned(client) == 7

    _retire(engine, hiit)

    for path in OFFERED + ALSO_CLEAN:
        answer = client.get(path)
        assert answer.status_code == 200, path
        assert NAME not in answer.text, path
    assert NAME not in _week(engine)  # and the old swap naming it is dropped
    assert _typed(engine, f"{NAME}\npull-ups 8").template_id != hiit
    assert _typed(engine, f"today {NAME}\npull-ups 8").template_id != hiit
    assert _planned(client) == 6
    summary = _summary(engine)
    assert "Next session: Legs." in summary

    # Its old day still says what it was.
    two_days_ago = (local_date(_today(), TZ) - timedelta(days=2)).isoformat()
    assert NAME in client.get("/api/day", params={"on": two_days_ago}).text
    assert NAME in json.dumps(client.get("/api/home").json()["recent"])
    assert f"{NAME}" in summary.split("## Sessions")[1]


def test_a_retired_session_is_exported_and_erased_with_the_rest(
    client: TestClient, engine: Engine
) -> None:
    hiit = _done_two_days_ago(engine)
    _retire(engine, hiit)
    with make_session_factory(engine, user_id=OWNER)() as mine:
        zipped = zipfile.ZipFile(io.BytesIO(export.archive(mine, _today())))
    sessions = json.loads(zipped.read("data.json"))["tables"]["sessions"]
    retired = next(s for s in sessions if s["id"] == hiit)
    assert retired["name"] == NAME
    assert retired["retired_on"] == (local_date(_today(), TZ) - timedelta(days=1)).isoformat()

    with session_scope(make_session_factory(engine)) as shared:
        assert erase.erase(shared, OWNER, load_plan())
    with make_session_factory(engine, user_id=OWNER)() as mine:  # a fresh start, all in the cycle
        rows = list(mine.scalars(select(SessionTemplate)))
    assert [t.retired_on for t in rows] == [None] * 7
    assert NAME in [t.name for t in rows]
