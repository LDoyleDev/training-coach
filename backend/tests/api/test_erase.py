"""POST /api/account/erase: erasing everything stored about the signed-in person (ADR-0044)."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from tests.api.test_photos import CLEAN, JPEG
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.base import Base
from training_coach.db.models import (
    Event,
    Measurement,
    Owned,
    Passkey,
    PlanState,
    ProgressPhoto,
    User,
    UserSettings,
    WebSession,
)
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import auth
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
TELEGRAM = 4242
ERASE = {"confirm": "erase"}


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
        shared.get_one(User, OWNER).telegram_user_id = TELEGRAM
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


@pytest.fixture
def alerts(signed_in: TestClient) -> list[str]:
    sent: list[str] = []

    async def notify(text: str) -> None:
        sent.append(text)

    signed_in.app.state.notify = notify  # type: ignore[attr-defined]  # a FastAPI app
    return sent


def _count(engine: Engine, model: type[Base], user: int) -> int:
    with session_scope(make_session_factory(engine)) as shared:
        column = model.user_id  # type: ignore[attr-defined]  # every Owned model has it
        query = select(func.count()).select_from(model).where(column == user)
        return shared.scalar(query, execution_options={ALL_USERS: True}) or 0


def test_erasing_removes_my_data_and_keeps_everyone_elses(
    signed_in: TestClient, engine: Engine
) -> None:
    today = local_date(datetime.now(UTC), Settings().tz).isoformat()
    assert signed_in.put("/api/body", json={"values": {"bodyweight": 83.4}}).is_success
    assert signed_in.put(f"/api/photos/{today}/front", content=CLEAN, headers=JPEG).is_success
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        mine.add(Passkey(credential_id="cred", public_key=b"key", sign_count=0, name="Pixel"))
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        theirs.add(Measurement(local_date=date(2026, 10, 1), kind="waist", tenths=999))

    assert signed_in.post("/api/account/erase", json=ERASE).status_code == 204

    for model in (Measurement, ProgressPhoto, Passkey, WebSession):
        assert _count(engine, model, OWNER) == 0, model.__name__
    assert _count(engine, Measurement, 2) == 1  # someone else's
    with session_scope(make_session_factory(engine)) as shared:
        assert shared.get_one(User, OWNER).telegram_user_id == TELEGRAM  # the bot still knows me
    # A fresh start: the plan's first session and default settings, so everything still works.
    assert _count(engine, PlanState, OWNER) == 1
    assert _count(engine, UserSettings, OWNER) == 1
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        kinds = list(mine.scalars(select(Event.kind)))
    assert kinds == ["account.erased"]  # nothing about what was there


def test_erasing_signs_this_browser_out(signed_in: TestClient) -> None:
    assert signed_in.post("/api/account/erase", json=ERASE).status_code == 204
    assert signed_in.get("/api/account/sign-ins").status_code == 401


@pytest.mark.parametrize("body", [{}, {"confirm": "yes"}, {"confirm": "ERASE"}])
def test_erasing_needs_the_word_typed(
    signed_in: TestClient, engine: Engine, body: dict[str, str]
) -> None:
    signed_in.put("/api/body", json={"values": {"bodyweight": 83.4}})
    assert signed_in.post("/api/account/erase", json=body).status_code == 422
    assert _count(engine, Measurement, OWNER) == 1


def test_erasing_needs_a_recent_sign_in_and_is_alerted(
    signed_in: TestClient, alerts: list[str], engine: Engine
) -> None:
    signed_in.put("/api/body", json={"values": {"bodyweight": 83.4}})
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        assert signed_in.post("/api/account/erase", json=ERASE).status_code == 403
    assert _count(engine, Measurement, OWNER) == 1
    assert alerts == []
    assert signed_in.post("/api/account/erase", json=ERASE).status_code == 204
    assert alerts == ["All your Training Coach data was erased. Backups age out within 5 weeks."]


def test_erasing_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.post("/api/account/erase", json=ERASE).status_code == 401


def test_every_per_person_table_goes_with_its_person() -> None:
    """Erasing deletes the user row and relies on the cascade: a per-person table added later
    without it would keep its rows (or block the erase)."""
    owned = [m for m in Base.registry.mappers if issubclass(m.class_, Owned)]
    assert owned
    for mapper in owned:
        (column,) = (c for c in mapper.local_table.columns if c.name == "user_id")
        (key,) = column.foreign_keys
        assert key.column.table.name == "users", mapper.class_.__name__
        assert key.ondelete == "CASCADE", mapper.class_.__name__
