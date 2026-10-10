"""The weekly AI comment from the person's own Groq key (ADR-0047 B)."""

import json
from datetime import date

import httpx
import pytest
import respx
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import ai_comment, ai_key
from training_coach.services.secret_box import SecretBox
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

CHAT = "https://api.groq.com/openai/v1/chat/completions"
SECRETS = Fernet.generate_key().decode()
SETTINGS = Settings(environment="test", secrets_key=SecretStr(SECRETS))
KEY = SecretStr("gsk_" + "a" * 48 + "4f2a")
TODAY = date(2026, 10, 11)


def _reply(content: object) -> dict[str, object]:
    return {"choices": [{"message": {"content": content}}]}


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    return make_session_factory(engine, user_id=OWNER)


@pytest.fixture
def keyed(sessions: sessionmaker[Session]) -> sessionmaker[Session]:
    with session_scope(sessions) as session:
        ai_key.store(session, SecretBox(SecretStr(SECRETS)), KEY)
    return sessions


def _failed(sessions: sessionmaker[Session]) -> bool:
    with session_scope(sessions) as session:
        return ai_key.status(session).failed


@respx.mock
async def test_the_comment_comes_from_the_persons_key_and_is_labelled(
    keyed: sessionmaker[Session],
) -> None:
    groq = respx.post(CHAT).respond(json=_reply("Good week.\n- More sleep."))
    text = await ai_comment.weekly(keyed, SETTINGS, TODAY)
    assert text == f"{ai_comment.LABEL}\n\nGood week.\n- More sleep."
    request = groq.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {KEY.get_secret_value()}"
    body = json.loads(request.content)
    assert body["model"] == SETTINGS.groq_comment_model
    user = body["messages"][1]["content"]
    assert user.startswith("<summary>\n# My training")
    assert "## Body" not in user  # health data only when ticked


@respx.mock
async def test_health_data_goes_only_when_ticked(keyed: sessionmaker[Session]) -> None:
    with session_scope(keyed) as session:
        ai_key.options(session, enabled=True, body=True, readiness=True)
    groq = respx.post(CHAT).respond(json=_reply("ok"))
    await ai_comment.weekly(keyed, SETTINGS, TODAY)
    user = json.loads(groq.calls.last.request.content)["messages"][1]["content"]
    assert "Readiness" in user


@respx.mock
async def test_nothing_without_a_key_when_off_or_without_secrets(
    sessions: sessionmaker[Session],
) -> None:
    groq = respx.post(CHAT).respond(json=_reply("x"))
    assert await ai_comment.weekly(sessions, SETTINGS, TODAY) is None
    with session_scope(sessions) as session:
        ai_key.store(session, SecretBox(SecretStr(SECRETS)), KEY)
        ai_key.options(session, enabled=False, body=False, readiness=False)
    assert await ai_comment.weekly(sessions, SETTINGS, TODAY) is None
    assert await ai_comment.weekly(sessions, Settings(environment="test"), TODAY) is None
    assert not groq.called


@respx.mock
async def test_a_refused_key_is_told_once(keyed: sessionmaker[Session]) -> None:
    respx.post(CHAT).respond(401)
    assert await ai_comment.weekly(keyed, SETTINGS, TODAY) == ai_comment.KEY_FAILED
    assert _failed(keyed)
    assert await ai_comment.weekly(keyed, SETTINGS, TODAY) is None  # told once; no more calls


@respx.mock
@pytest.mark.parametrize(
    "answer", [httpx.Response(500), httpx.Response(429), httpx.Response(200, json={})]
)
async def test_other_failures_skip_quietly(
    keyed: sessionmaker[Session], answer: httpx.Response
) -> None:
    respx.post(CHAT).mock(return_value=answer)
    assert await ai_comment.weekly(keyed, SETTINGS, TODAY) is None
    assert not _failed(keyed)


@respx.mock
async def test_an_unreadable_key_is_told_once(keyed: sessionmaker[Session]) -> None:
    groq = respx.post(CHAT).respond(json=_reply("x"))
    other = Settings(environment="test", secrets_key=SecretStr(Fernet.generate_key().decode()))
    assert await ai_comment.weekly(keyed, other, TODAY) == ai_comment.KEY_FAILED
    assert await ai_comment.weekly(keyed, other, TODAY) is None
    assert not groq.called


@respx.mock
@pytest.mark.parametrize("content", ["", "   ", None, ["not", "text"]])
async def test_empty_or_odd_answers_send_nothing(
    keyed: sessionmaker[Session], content: object
) -> None:
    respx.post(CHAT).respond(json=_reply(content))
    assert await ai_comment.weekly(keyed, SETTINGS, TODAY) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Fine.\n\n\n\n- Rest more. ", "Fine.\n\n- Rest more."),
        ("See https://evil.example/x now", "See [link removed] now"),
        ("www.example.com", "[link removed]"),
        ("bell\x07 and \u202eRTL", "bell and RTL"),
        ("\uff46\uff55\uff4c\uff4c width", "full width"),
    ],
)
def test_clean(raw: str, expected: str) -> None:
    assert ai_comment.clean(raw) == expected


def test_clean_caps_the_length_at_a_word() -> None:
    text = ai_comment.clean("word " * 1000)
    assert len(text) <= ai_comment.LIMIT + 2
    assert text.endswith("word …")
