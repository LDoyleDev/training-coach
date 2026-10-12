"""Sign-in alerts go to the person they're about (multi-user plan, step 3): never to the owner
for someone else's sign-in, and nowhere for someone with no Telegram linked."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
OWNER_CHAT = 4242
OTHER, OTHER_CHAT = 2, 777  # a second person, as invites will add


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=OTHER))
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as test_client:
        yield test_client


@pytest.fixture
def sent(client: TestClient, engine: Engine) -> list[tuple[int | str, str]]:
    """Every message, by where it went: a chat id, or "ops" for the owner's ops channel (a
    failed backup). The owner's chat is OWNER_CHAT."""
    with session_scope(make_session_factory(engine)) as shared:
        shared.get_one(User, OWNER).telegram_user_id = OWNER_CHAT
    messages: list[tuple[int | str, str]] = []

    async def send(chat: int, text: str) -> None:
        messages.append((chat, text))

    async def notify(text: str) -> None:
        messages.append(("ops", text))

    client.app.state.send = send  # type: ignore[attr-defined]  # a FastAPI app
    client.app.state.notify = notify  # type: ignore[attr-defined]  # a FastAPI app
    return messages


def _link_telegram(engine: Engine, user: int, chat: int) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.get_one(User, user).telegram_user_id = chat


def _sign_in(client: TestClient, engine: Engine, user: int) -> None:
    with session_scope(make_session_factory(engine, user_id=user)) as bound:
        token = auth.create_link(bound, datetime.now(UTC))
    assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204


def test_a_second_persons_sign_in_is_told_to_them_not_the_owner(
    client: TestClient, engine: Engine, sent: list[tuple[int | str, str]]
) -> None:
    _link_telegram(engine, OTHER, OTHER_CHAT)
    _sign_in(client, engine, OTHER)
    ((where, text),) = sent
    assert where == OTHER_CHAT
    assert text.startswith("New sign-in to Training Coach with a link from the bot")


def test_someone_without_telegram_gets_no_alert_and_the_owner_none_either(
    client: TestClient, engine: Engine, sent: list[tuple[int | str, str]]
) -> None:
    _sign_in(client, engine, OTHER)  # OTHER has no Telegram linked
    assert sent == []


def test_the_owners_own_sign_in_still_reaches_them(
    client: TestClient, engine: Engine, sent: list[tuple[int | str, str]]
) -> None:
    _sign_in(client, engine, OWNER)
    ((where, text),) = sent
    assert where == OWNER_CHAT
    assert text.startswith("New sign-in to Training Coach")
