"""The weekly AI comment from the person's own Groq key (ADR-0047 B)."""

import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from training_coach.config import Settings
from training_coach.db.models import AiComment
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
        ("Join t.me/x today", "Join [link removed] today"),
        ("open tg://resolve?domain=x", "open [link removed]"),
        ("see evil.example and EVIL.EXAMPLE/path?q=1", "see [link removed] and [link removed]"),
        ("ask @someone_bot", "ask [mention removed]"),
        ("send /undo now", "send undo now"),
        ("3/week, 1.5 min, e.g. rest, 8/10, a@b", "3/week, 1.5 min, e.g. rest, 8/10, a@b"),
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


# ------------------------------------------- kept 7 days for the web review (ADR-0056)

MONDAY = date(2026, 10, 5)  # TODAY's week
NOW = datetime(2026, 10, 11, 18, 0, tzinfo=UTC)


def _kept(sessions: sessionmaker[Session]) -> list[tuple[date, str]]:
    with session_scope(sessions) as session:
        return [(c.week, c.text) for c in session.scalars(select(AiComment))]


@respx.mock
async def test_the_comment_is_kept_with_its_week_without_the_label(
    keyed: sessionmaker[Session],
) -> None:
    respx.post(CHAT).respond(json=_reply("Good week. See https://evil.example"))
    await ai_comment.weekly(keyed, SETTINGS, TODAY)
    assert _kept(keyed) == [(MONDAY, "Good week. See [link removed]")]


@respx.mock
async def test_a_second_comment_for_the_week_replaces_the_first(
    keyed: sessionmaker[Session],
) -> None:
    respx.post(CHAT).mock(
        side_effect=[httpx.Response(200, json=_reply(t)) for t in ("First.", "Second.")]
    )
    await ai_comment.weekly(keyed, SETTINGS, TODAY)
    await ai_comment.weekly(keyed, SETTINGS, TODAY)
    assert _kept(keyed) == [(MONDAY, "Second.")]


@respx.mock
@pytest.mark.parametrize(
    "answer",
    [httpx.Response(401), httpx.Response(500), httpx.Response(200, json=_reply("  "))],
)
async def test_nothing_is_kept_without_a_comment(
    keyed: sessionmaker[Session], answer: httpx.Response
) -> None:
    respx.post(CHAT).mock(return_value=answer)
    await ai_comment.weekly(keyed, SETTINGS, TODAY)
    assert _kept(keyed) == []


def test_storing_sweeps_comments_older_than_7_days(sessions: sessionmaker[Session]) -> None:
    with session_scope(sessions) as session:
        ai_comment.store(session, MONDAY - timedelta(days=14), "Old.", NOW - timedelta(days=14))
        ai_comment.store(session, MONDAY - timedelta(days=7), "Last.", NOW - timedelta(days=6))
        ai_comment.store(session, MONDAY, "This.", NOW)
    assert _kept(sessions) == [(MONDAY - timedelta(days=7), "Last."), (MONDAY, "This.")]


@respx.mock
async def test_the_weekly_review_sweeps_even_with_comments_off(
    sessions: sessionmaker[Session],
) -> None:
    with session_scope(sessions) as session:
        ai_comment.store(session, MONDAY - timedelta(days=7), "Last.", NOW - timedelta(days=8))
    await ai_comment.weekly(sessions, Settings(environment="test"), TODAY)
    assert _kept(sessions) == []


def test_a_kept_comment_is_read_only_within_its_7_days(sessions: sessionmaker[Session]) -> None:
    with session_scope(sessions) as session:
        ai_comment.store(session, MONDAY, "This.", NOW)
        assert ai_comment.stored(session, MONDAY, NOW + timedelta(days=6, hours=23)) == "This."
        assert ai_comment.stored(session, MONDAY, NOW + timedelta(days=7, seconds=1)) is None
        assert ai_comment.stored(session, MONDAY - timedelta(days=7), NOW) is None


def test_the_longest_clean_comment_fits_and_nothing_longer_or_empty_does(
    sessions: sessionmaker[Session],
) -> None:
    longest = ai_comment.clean("x" * 5000)  # one word: cut at LIMIT, plus " …"
    assert len(longest) == ai_comment.LIMIT + 2
    with session_scope(sessions) as session:
        ai_comment.store(session, MONDAY, longest, NOW)
    for text in ("", longest + "x"):
        with pytest.raises(IntegrityError), session_scope(sessions) as session:
            session.add(AiComment(week=MONDAY + timedelta(days=7), text=text, created_at=NOW))
