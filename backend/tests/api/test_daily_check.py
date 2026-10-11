"""/api/daily-check and Today's daily-check line (ADR-0053)."""

import io
import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import DailyCheck
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.daily_check import Answers, Energy, Sleep, Soreness
from training_coach.domain.queue import local_date
from training_coach.services import auth, daily_check
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
LIGHTER = {"sleep": "ok", "soreness": "some", "energy": "high"}
REST = {"sleep": "poor", "soreness": "a_lot", "energy": "normal"}


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


def _today() -> date:
    return local_date(datetime.now(UTC), Settings().tz)


def test_unanswered_lists_the_questions_without_advice(signed_in: TestClient) -> None:
    view = signed_in.get("/api/daily-check").json()
    assert view["day"] == _today().isoformat()
    assert [q["key"] for q in view["questions"]] == ["sleep", "soreness", "energy"]
    assert [o["value"] for o in view["questions"][1]["options"]] == ["none", "some", "a_lot"]
    assert (view["answers"], view["advice"]) == (None, None)


def test_answering_gives_the_advice_and_is_kept_for_the_day(signed_in: TestClient) -> None:
    saved = signed_in.put("/api/daily-check", json=LIGHTER).json()
    assert saved["answers"] == LIGHTER
    assert saved["advice"]["kind"] == "lighter"
    assert saved["advice"]["title"] == "Go lighter today"
    assert signed_in.get("/api/daily-check").json() == saved


def test_answering_again_the_same_day_replaces_the_answers(
    signed_in: TestClient, engine: Engine
) -> None:
    signed_in.put("/api/daily-check", json=LIGHTER)
    again = signed_in.put("/api/daily-check", json=REST).json()
    assert again["advice"]["kind"] == "rest"
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        (row,) = mine.scalars(select(DailyCheck)).all()
        assert (row.local_date, row.sleep) == (_today(), "poor")


def test_an_unknown_answer_is_refused(signed_in: TestClient) -> None:
    answer = signed_in.put("/api/daily-check", json={**LIGHTER, "sleep": "great"})
    assert answer.status_code == 422
    assert signed_in.get("/api/daily-check").json()["answers"] is None


def test_today_shows_the_answers_and_advice_once_answered(signed_in: TestClient) -> None:
    assert signed_in.get("/api/session/today").json()["daily_check"] is None
    signed_in.put("/api/daily-check", json=REST)
    line = signed_in.get("/api/session/today").json()["daily_check"]
    assert line == "Slept poorly, very sore, normal energy: take a rest day"


def test_yesterdays_answers_dont_count_today(signed_in: TestClient, engine: Engine) -> None:
    yesterday = _today() - timedelta(days=1)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        mine.add(
            DailyCheck(
                local_date=yesterday,
                sleep="poor",
                soreness="a_lot",
                energy="low",
                answered_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
    assert signed_in.get("/api/daily-check").json()["answers"] is None


def test_the_answers_are_in_the_export(signed_in: TestClient) -> None:
    signed_in.put("/api/daily-check", json=LIGHTER)
    exported = signed_in.get("/api/account/export")  # this client signed in just now
    zipped = zipfile.ZipFile(io.BytesIO(exported.content))
    (row,) = json.loads(zipped.read("data.json"))["tables"]["daily_checks"]
    assert (row["local_date"], row["sleep"], row["soreness"]) == (
        _today().isoformat(),
        "ok",
        "some",
    )


def test_the_daily_check_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/daily-check").status_code == 401
        assert stranger.put("/api/daily-check", json=LIGHTER).status_code == 401


def test_answers_older_than_a_year_are_dropped_as_new_ones_come_in(
    signed_in: TestClient, engine: Engine
) -> None:
    good = Answers(Sleep.GOOD, Soreness.NONE, Energy.HIGH)
    day = date(2026, 10, 11)
    now = datetime(2026, 10, 11, 6, tzinfo=UTC)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        daily_check.save(mine, day - daily_check.KEEP - timedelta(days=1), good, now)
        daily_check.save(mine, day - daily_check.KEEP, good, now)
        daily_check.save(mine, day, good, now)
        kept = sorted(row.local_date for row in mine.scalars(select(DailyCheck)))
        assert kept == [day - daily_check.KEEP, day]
        assert daily_check.on(mine, day) == good
        assert daily_check.on(mine, day - timedelta(days=1)) is None


def test_two_saves_racing_on_a_new_day_keep_the_last_answers(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both saves saw no row; the second one's insert hits the unique key and updates instead."""
    good = Answers(Sleep.GOOD, Soreness.NONE, Energy.HIGH)
    poor = Answers(Sleep.POOR, Soreness.A_LOT, Energy.LOW)
    day = date(2026, 10, 11)
    now = datetime(2026, 10, 11, 6, tzinfo=UTC)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        daily_check.save(mine, day, good, now)
        mine.flush()
        real = mine.scalar
        missed: list[bool] = []

        def first_miss(statement: object) -> object:
            if not missed:  # the racing request's look-up ran before the first insert landed
                missed.append(True)
                return None
            return real(statement)  # type: ignore[call-overload]  # passes the statement on

        monkeypatch.setattr(mine, "scalar", first_miss)
        daily_check.save(mine, day, poor, now)
        monkeypatch.undo()
        assert daily_check.on(mine, day) == poor
        assert len(mine.scalars(select(DailyCheck)).all()) == 1
