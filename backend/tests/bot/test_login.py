"""/login: a one-time web sign-in link, for the owner only (ADR-0036)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, SETTINGS, STRANGER, command, run, texts
from training_coach.bot.app import LOGIN_OFF, LOGIN_TEXT, RECOVER_TEXT, build_bot
from training_coach.config import Settings
from training_coach.db.models import Passkey
from training_coach.services import auth

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]
URL = "https://coach.example.com"


@pytest.fixture
def with_url(seeded: Sessions) -> App:
    return build_bot(SETTINGS.model_copy(update={"public_url": URL}), seeded)


async def test_login_sends_a_link_that_signs_in_once(with_url: App, sessions: Sessions) -> None:
    (reply,) = texts(await run(with_url, command("/login", OWNER)))
    first, link = reply.split("\n")
    assert first == LOGIN_TEXT
    assert link.startswith(f"{URL}/signin#")
    token = link.split("#", 1)[1]
    shared = sessionmaker(bind=sessions.kw["bind"])  # unbound, as the web routes use
    with shared() as session:
        assert auth.redeem_link(session, token, datetime.now(UTC), "test") is not None


async def test_strangers_get_no_link(with_url: App) -> None:
    assert await run(with_url, command("/login", STRANGER)) == {}


async def test_without_a_public_url_login_says_it_is_off(application: App) -> None:
    assert texts(await run(application, command("/login", OWNER))) == [LOGIN_OFF]


@pytest.mark.parametrize(
    ("given", "kept"),
    [
        ("https://coach.example.com/", "https://coach.example.com"),
        ("http://localhost:5173", "http://localhost:5173"),
    ],
)
def test_public_url_must_be_https(given: str, kept: str) -> None:
    assert Settings(public_url=given).public_url == kept


@pytest.mark.parametrize(
    ("given", "problem"),
    [
        ("http://coach.example.com", "https"),
        ("http://localhost.evil.com", "https"),  # review of #122
        ("http://127.0.0.1.evil.com", "https"),
        ("https://", "https"),
        ("https://coach.example.com/app", "origin only"),
        ("https://coach.example.com/?next=x", "origin only"),
        ("https://user:pw@coach.example.com", "origin only"),
    ],
)
def test_anything_but_an_https_origin_is_refused(given: str, problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        Settings(public_url=given)


async def test_once_a_passkey_exists_login_points_to_the_fingerprint(
    with_url: App, sessions: Sessions
) -> None:
    with sessions() as session:
        session.add(Passkey(credential_id="mine", public_key=b"k", sign_count=0, name="Phone"))
        session.commit()
    (reply,) = texts(await run(with_url, command("/login", OWNER)))
    assert f"{URL}/signin\n" in reply
    assert "#" not in reply  # no link token
    assert "/recover" in reply


async def test_recover_sends_a_recovery_link(with_url: App, sessions: Sessions) -> None:
    (reply,) = texts(await run(with_url, command("/recover", OWNER)))
    first, link = reply.split("\n")
    assert first == RECOVER_TEXT
    token = link.split("#", 1)[1]
    shared = sessionmaker(bind=sessions.kw["bind"])
    with shared() as session:
        redeemed = auth.redeem_link(session, token, datetime.now(UTC), "test")
        assert isinstance(redeemed, auth.Redeemed)
        assert redeemed.recovered


async def test_strangers_get_no_recovery_link(with_url: App) -> None:
    assert await run(with_url, command("/recover", STRANGER)) == {}


async def test_the_owner_in_a_group_gets_no_link(with_url: App) -> None:
    for text in ("/login", "/recover"):
        update = command(text, OWNER)
        update["message"]["chat"] = {"id": -100123, "type": "supergroup", "title": "Gym"}
        assert await run(with_url, update) == {}


async def test_without_a_public_url_recover_says_it_is_off(application: App) -> None:
    assert texts(await run(application, command("/recover", OWNER))) == [LOGIN_OFF]
