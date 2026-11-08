"""A member connecting their Telegram on Account (ADR-0089): a link, a claim from Telegram with
a code, the code typed on Account, Confirm; and disconnecting. The claim is made here the way
the bot's ``/start <token>`` makes it."""

import io
import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from tests.alerts import capture, forgotten
from training_coach.api.app import create_app
from training_coach.api.telegram_link import CONNECTED, DISCONNECTED
from training_coach.config import Settings
from training_coach.db.models import Event, TelegramClaim, TelegramLink, User
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.services import auth, telegram_link, users

BASE = "https://testserver"
MEMBER, OTHER = 2, 3
CONFIGURED = 4242  # the owner's account, set on the server
THEIRS, STRANGER = 7001, 7002  # Telegram accounts
BOT = "tc_test_bot"


@pytest.fixture
def settings(engine: Engine) -> Settings:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add_all([User(id=MEMBER, role=users.MEMBER), User(id=OTHER, role=users.MEMBER)])
    return Settings(
        environment="test",
        database_url=str(engine.url),
        multi_user=True,
        telegram_allowed_user_id=CONFIGURED,
    )


def _signed_in(settings: Settings, engine: Engine, user: int) -> TestClient:
    client = TestClient(create_app(settings), base_url=BASE)
    client.__enter__()
    client.app.state.bot_username = BOT  # type: ignore[attr-defined]  # a FastAPI app
    with make_session_factory(engine, user_id=user)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
    return client


@pytest.fixture
def member(settings: Settings, engine: Engine) -> Iterator[TestClient]:
    client = _signed_in(settings, engine, MEMBER)
    yield client
    client.__exit__(None, None, None)


@pytest.fixture
def other(settings: Settings, engine: Engine) -> Iterator[TestClient]:
    client = _signed_in(settings, engine, OTHER)
    yield client
    client.__exit__(None, None, None)


def _token(client: TestClient) -> str:
    answer = client.post("/api/account/telegram/link")
    assert answer.status_code == 200
    url: str = answer.json()["url"]
    prefix = f"https://t.me/{BOT}?start="
    assert url.startswith(prefix)
    return url.removeprefix(prefix)


def _claim(engine: Engine, token: str, sender: int = THEIRS, name: str = "Mum") -> str | None:
    """What the bot's /start <token> does for a sender who isn't anyone yet."""
    with session_scope(make_session_factory(engine)) as shared:
        found = telegram_link.claim(
            shared, token, sender, name, datetime.now(UTC), configured=CONFIGURED
        )
    return found.code if found is not None else None


def _status(client: TestClient) -> dict[str, Any]:
    answer = client.get("/api/account/telegram")
    assert answer.status_code == 200
    found: dict[str, Any] = answer.json()
    return found


def _linked(engine: Engine, user: int) -> int | None:
    with session_scope(make_session_factory(engine)) as shared:
        return users.telegram_chat(shared, user)


def _rows(engine: Engine, model: type) -> int:
    with session_scope(make_session_factory(engine)) as shared:
        return len(shared.scalars(select(model), execution_options={ALL_USERS: True}).all())


def _unused_code(code: str) -> str:
    return f"{(int(code) + 1) % 10**6:06d}"


def test_a_member_connects_with_the_code_their_telegram_got(
    member: TestClient, engine: Engine
) -> None:
    told = capture(member, users.OWNER, chat=CONFIGURED)  # any other chat shows as "to <chat>"
    token = _token(member)
    assert _status(member)["pending"]["claims"] == 0
    code = _claim(engine, token)
    assert code is not None
    assert len(code) == 6
    assert code.isdigit()
    assert _status(member)["pending"]["claims"] == 1
    assert member.post("/api/account/telegram/code", json={"code": code}).json() == {"name": "Mum"}
    assert _linked(engine, MEMBER) is None  # the name is a check: Confirm still to come
    assert member.post("/api/account/telegram/confirm", json={"code": code}).status_code == 204
    assert _linked(engine, MEMBER) == THEIRS
    status = _status(member)
    assert status["connected"] is True
    assert status["name"] == "Mum"
    assert status["since"] is not None
    assert status["pending"] is None
    assert status["set_on_server"] is False
    assert told == [f"to {THEIRS}: {CONNECTED}"]
    assert _rows(engine, TelegramLink) == 0  # used up, with its claims
    assert _rows(engine, TelegramClaim) == 0
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as mine:
        assert mine.scalar(select(Event.kind).where(Event.kind == telegram_link.LINKED))


def test_tokens_and_codes_are_stored_only_hashed(member: TestClient, engine: Engine) -> None:
    token = _token(member)
    code = _claim(engine, token)
    assert code is not None
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as mine:
        link = mine.scalars(select(TelegramLink)).one()
        assert link.token_hash == auth.hash_token(token)
        assert code not in link.claims[0].code_hash
        assert link.claims[0].code_hash != auth.hash_token(code)  # salted by the link


def test_a_connect_token_never_signs_in(member: TestClient, settings: Settings) -> None:
    """Kept apart from login_links: the sign-in redeem takes any purpose (ADR-0089)."""
    token = _token(member)
    with TestClient(create_app(settings), base_url=BASE) as stranger:
        assert stranger.post("/api/auth/redeem", json={"token": token}).status_code == 401
        assert stranger.get("/api/auth/me").status_code == 401


def test_five_wrong_codes_end_the_link(member: TestClient, engine: Engine) -> None:
    code = _claim(engine, _token(member))
    assert code is not None
    wrong = {"code": _unused_code(code)}
    for _ in range(telegram_link.MAX_WRONG - 1):
        assert member.post("/api/account/telegram/code", json=wrong).status_code == 400
    assert member.post("/api/account/telegram/confirm", json=wrong).status_code == 410
    assert member.post("/api/account/telegram/code", json={"code": code}).status_code == 404
    assert _status(member)["pending"] is None
    assert _linked(engine, MEMBER) is None


def test_a_second_claim_means_start_again(member: TestClient, engine: Engine) -> None:
    """Someone else used the link: neither code connects, so a leaked link fails closed."""
    token = _token(member)
    mine = _claim(engine, token)
    theirs = _claim(engine, token, sender=STRANGER, name="Mum")
    assert mine is not None
    assert theirs is not None
    assert mine != theirs
    assert _status(member)["pending"]["claims"] == 2
    for code in (mine, theirs):
        assert member.post("/api/account/telegram/code", json={"code": code}).status_code == 409
        answer = member.post("/api/account/telegram/confirm", json={"code": code})
        assert answer.status_code == 409
    assert _linked(engine, MEMBER) is None


def test_a_link_takes_three_claims_and_a_sender_again_gets_a_new_code(
    member: TestClient, engine: Engine
) -> None:
    token = _token(member)
    first = _claim(engine, token)
    again = _claim(engine, token)
    assert first is not None
    assert again is not None
    assert _status(member)["pending"]["claims"] == 1
    assert _claim(engine, token, sender=7003) is not None
    assert _claim(engine, token, sender=7004) is not None
    assert _claim(engine, token, sender=7005) is None  # full
    assert _status(member)["pending"]["claims"] == telegram_link.MAX_CLAIMS


def test_the_same_sender_s_old_code_stops_working(member: TestClient, engine: Engine) -> None:
    token = _token(member)
    first = _claim(engine, token)
    again = _claim(engine, token)
    assert first is not None
    assert again is not None
    if first != again:
        assert member.post("/api/account/telegram/code", json={"code": first}).status_code == 400
    assert member.post("/api/account/telegram/code", json={"code": again}).status_code == 200


def test_a_link_lasts_10_minutes_and_only_the_newest_works(
    member: TestClient, engine: Engine
) -> None:
    older = _token(member)
    newer = _token(member)
    assert _claim(engine, older) is None
    assert _claim(engine, newer) is not None
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        assert _claim(engine, newer, sender=STRANGER) is None
        assert _status(member)["pending"] is None
    assert _rows(engine, TelegramLink) == 0  # an expired link is cleared with its claims
    assert _rows(engine, TelegramClaim) == 0


def test_cancel_ends_the_link(member: TestClient, engine: Engine) -> None:
    token = _token(member)
    assert member.delete("/api/account/telegram/link").status_code == 204
    assert _status(member)["pending"] is None
    assert _claim(engine, token) is None


def test_making_and_confirming_need_a_recent_sign_in(member: TestClient, engine: Engine) -> None:
    signed_in = datetime.now(UTC)
    with time_machine.travel(signed_in + timedelta(minutes=9)):
        code = _claim(engine, _token(member))
    with time_machine.travel(signed_in + timedelta(minutes=11)):  # the link still lasts
        assert member.post("/api/account/telegram/link").status_code == 403
        answer = member.post("/api/account/telegram/confirm", json={"code": code})
        assert answer.status_code == 403
        assert member.post("/api/account/telegram/code", json={"code": code}).status_code == 200
    assert _linked(engine, MEMBER) is None


def test_one_member_s_code_does_nothing_for_another(
    member: TestClient, other: TestClient, engine: Engine
) -> None:
    code = _claim(engine, _token(member))
    assert code is not None
    assert _status(other)["pending"] is None
    assert other.post("/api/account/telegram/code", json={"code": code}).status_code == 404
    assert other.post("/api/account/telegram/confirm", json={"code": code}).status_code == 404
    assert member.post("/api/account/telegram/code", json={"code": code}).status_code == 200


def test_an_account_connected_to_someone_is_refused(
    member: TestClient, other: TestClient, engine: Engine
) -> None:
    code = _claim(engine, _token(member))
    assert member.post("/api/account/telegram/confirm", json={"code": code}).status_code == 204
    # The bot sends a linked sender to its own handlers, never to a claim; asked anyway:
    late = _claim(engine, _token(other), sender=THEIRS)
    assert late is not None
    answer = other.post("/api/account/telegram/confirm", json={"code": late})
    assert answer.status_code == 409
    assert _linked(engine, MEMBER) == THEIRS
    assert _linked(engine, OTHER) is None


def test_the_owner_s_configured_account_can_t_be_claimed(
    member: TestClient, engine: Engine
) -> None:
    assert _claim(engine, _token(member), sender=CONFIGURED) is None


def test_a_connected_member_unlinks_first(member: TestClient, engine: Engine) -> None:
    token = _token(member)
    code = _claim(engine, token)
    assert member.post("/api/account/telegram/confirm", json={"code": code}).status_code == 204
    assert member.post("/api/account/telegram/link").status_code == 409


def test_unlinking_tells_the_old_chat(member: TestClient, engine: Engine) -> None:
    code = _claim(engine, _token(member))
    assert member.post("/api/account/telegram/confirm", json={"code": code}).status_code == 204
    told = capture(member, users.OWNER, chat=CONFIGURED)
    forgot = forgotten(member)
    assert member.delete("/api/account/telegram").status_code == 204
    assert told == [f"to {THEIRS}: {DISCONNECTED}"]
    assert forgot == [MEMBER]  # what the bot kept for that chat goes (ADR-0089)
    assert _linked(engine, MEMBER) is None
    status = _status(member)
    assert (status["connected"], status["name"], status["since"]) == (False, None, None)
    assert member.delete("/api/account/telegram").status_code == 404
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as mine:
        assert mine.scalar(select(Event.kind).where(Event.kind == telegram_link.UNLINKED))


def test_the_owner_s_telegram_is_set_on_the_server(settings: Settings, engine: Engine) -> None:
    owner = _signed_in(settings, engine, users.OWNER)
    try:
        assert _status(owner)["set_on_server"] is True
        assert owner.post("/api/account/telegram/link").status_code == 403
        assert owner.delete("/api/account/telegram/link").status_code == 403
        assert owner.post("/api/account/telegram/code", json={"code": "123456"}).status_code == 403
        answer = owner.post("/api/account/telegram/confirm", json={"code": "123456"})
        assert answer.status_code == 403
        assert owner.delete("/api/account/telegram").status_code == 403
    finally:
        owner.__exit__(None, None, None)


def test_everything_is_closed_to_members_with_the_switch_off(
    settings: Settings, engine: Engine
) -> None:
    client = _signed_in(settings.model_copy(update={"multi_user": False}), engine, MEMBER)
    try:
        assert client.get("/api/account/telegram").status_code == 403
        assert client.post("/api/account/telegram/link").status_code == 403
        assert client.post("/api/account/telegram/code", json={"code": "123456"}).status_code == 403
        answer = client.post("/api/account/telegram/confirm", json={"code": "123456"})
        assert answer.status_code == 403
        assert client.delete("/api/account/telegram").status_code == 403
    finally:
        client.__exit__(None, None, None)


def test_no_link_while_the_bot_is_off(member: TestClient) -> None:
    member.app.state.bot_username = None  # type: ignore[attr-defined]  # a FastAPI app
    assert member.post("/api/account/telegram/link").status_code == 503


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", ""])
def test_a_code_is_six_digits(member: TestClient, code: str) -> None:
    assert member.post("/api/account/telegram/code", json={"code": code}).status_code == 422


def test_the_export_holds_the_name_but_no_link(member: TestClient, engine: Engine) -> None:
    """The name is theirs; links and claims are short-lived secrets, left out like sign-in
    links."""
    code = _claim(engine, _token(member))
    assert member.post("/api/account/telegram/confirm", json={"code": code}).status_code == 204
    answer = member.get("/api/account/export")
    assert answer.status_code == 200
    data = json.loads(zipfile.ZipFile(io.BytesIO(answer.content)).read("data.json"))
    assert data["account"]["telegram_name"] == "Mum"
    assert data["account"]["telegram_connected_at"] is not None
    assert not {"telegram_links", "telegram_claims"} & set(data["tables"])
