"""/login: a one-time web sign-in link, for the owner only (ADR-0036)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, SETTINGS, STRANGER, command, run, texts
from training_coach.bot.app import LOGIN_OFF, LOGIN_TEXT, build_bot
from training_coach.config import Settings
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


def test_plain_http_is_refused() -> None:
    with pytest.raises(ValueError, match="https"):
        Settings(public_url="http://coach.example.com")
