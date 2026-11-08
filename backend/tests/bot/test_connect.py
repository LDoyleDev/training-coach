"""A stranger's ``/start <token>`` (ADR-0089): with TC_MULTI_USER on, the one thing a stranger
reaches. It records a claim and replies with a code, connecting nothing; it is rate limited and
silent over the limits; nothing else from a stranger gets an answer. And a button on a message
older than the person's link does nothing."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from structlog.testing import capture_logs
from telegram.ext import Application

from tests.bot.fakes import (
    DATE,
    MULTI,
    SETTINGS,
    STRANGER,
    command,
    press,
    run,
    text_message,
    texts,
)
from tests.bot.fakes import MEMBER as TELEGRAM_MEMBER
from training_coach.bot.app import build_bot
from training_coach.bot.connect import EXPIRED_TEXT, OVERALL, PER_SENDER, Connect
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import telegram_link, users

UNKNOWN = "ab" * 20  # looks like a token, isn't one
CODE = re.compile(r"Your code: (\d{6})\n")


@pytest.fixture
def joiner(seeded: sessionmaker[Session]) -> tuple[sessionmaker[Session], str]:
    """A member with no Telegram yet, who has just made a connect link: their sessions and the
    link's token."""
    engine = seeded.kw["bind"]
    with session_scope(make_session_factory(engine)) as shared:
        person = User(role=users.MEMBER)
        shared.add(person)
        shared.flush()
        person_id = person.id
    theirs = make_session_factory(engine, user_id=person_id)
    with session_scope(theirs) as session:
        token = telegram_link.make(session, datetime.now(UTC))
    return theirs, token


def start(token: str, sender: int) -> dict[str, Any]:
    """``/start <token>`` as a t.me link sends it: the command entity covers ``/start`` only."""
    update = command(f"/start {token}", sender)
    update["message"]["entities"][0]["length"] = len("/start")
    return update


def _claims(theirs: sessionmaker[Session]) -> int:
    with session_scope(theirs) as session:
        found = telegram_link.status(session, theirs.kw["info"]["user_id"], datetime.now(UTC))
    return found.pending.claims if found.pending is not None else 0


async def test_opening_the_link_gives_a_code_and_connects_nothing(
    seeded: sessionmaker[Session], joiner: tuple[sessionmaker[Session], str]
) -> None:
    theirs, token = joiner
    application = build_bot(MULTI, seeded)
    (reply,) = texts(await run(application, start(token, STRANGER)))
    found = CODE.match(reply)
    assert found is not None
    assert _claims(theirs) == 1
    with session_scope(theirs) as session:
        assert telegram_link.check(session, found.group(1), datetime.now(UTC)) == (
            telegram_link.Match("Someone")
        )
        assert users.by_telegram(session, STRANGER) is None  # confirmed on Account, not here


async def test_nothing_while_the_switch_is_off(
    seeded: sessionmaker[Session], joiner: tuple[sessionmaker[Session], str]
) -> None:
    theirs, token = joiner
    assert await run(build_bot(SETTINGS, seeded), start(token, STRANGER)) == {}
    assert _claims(theirs) == 0


async def test_a_dead_link_says_so(seeded: sessionmaker[Session]) -> None:
    calls = await run(build_bot(MULTI, seeded), start(UNKNOWN, STRANGER))
    assert texts(calls) == [EXPIRED_TEXT]


@pytest.mark.parametrize(
    "update",
    [
        command("/start", STRANGER),
        command("/start short", STRANGER),
        command(f"/start {UNKNOWN} more", STRANGER),
        command(f"/start@coach_bot {UNKNOWN}", STRANGER),
        command(f"/today {UNKNOWN}", STRANGER),
        command("/recover", STRANGER),
        command("/login", STRANGER),
        text_message("pull-ups 8 8 7", STRANGER),
        press(f"/start {UNKNOWN}", STRANGER),
        press("q:rest:1", STRANGER),
    ],
)
async def test_everything_else_from_a_stranger_is_still_silent(
    seeded: sessionmaker[Session], update: dict[str, Any]
) -> None:
    assert await run(build_bot(MULTI, seeded), update) == {}


async def test_a_linked_person_s_start_is_just_start(
    both: Application,  # type: ignore[type-arg]  # see build_bot
    joiner: tuple[sessionmaker[Session], str],
) -> None:
    theirs, token = joiner
    (reply,) = texts(await run(both, start(token, TELEGRAM_MEMBER)))
    assert not CODE.match(reply)
    assert _claims(theirs) == 0


async def test_over_the_limit_a_sender_hears_nothing(seeded: sessionmaker[Session]) -> None:
    application = build_bot(MULTI, seeded)
    for _ in range(PER_SENDER):
        calls = await run(application, start(UNKNOWN, STRANGER))
        assert texts(calls) == [EXPIRED_TEXT]
    assert await run(application, start(UNKNOWN, STRANGER)) == {}


def test_the_limits_per_sender_and_overall(engine: Engine) -> None:
    connect = Connect(MULTI, make_session_factory(engine))
    assert [connect.claim(1, "A", UNKNOWN) for _ in range(PER_SENDER + 1)][-1] is None
    answered = [connect.claim(100 + n, "A", UNKNOWN) for n in range(OVERALL)]
    assert answered.count(EXPIRED_TEXT) == OVERALL - PER_SENDER  # the first sender's count too
    assert connect.claim(999, "A", UNKNOWN) is None


async def test_no_token_code_or_telegram_id_is_logged(
    seeded: sessionmaker[Session], joiner: tuple[sessionmaker[Session], str]
) -> None:
    _theirs, token = joiner
    with capture_logs() as logs:
        (reply,) = texts(await run(build_bot(MULTI, seeded), start(token, STRANGER)))
    found = CODE.match(reply)
    assert found is not None
    written = repr(logs)
    for secret in (token, found.group(1), str(STRANGER)):
        assert secret not in written


def _linked_at(member: sessionmaker[Session], at: datetime) -> None:
    with session_scope(make_session_factory(member.kw["bind"])) as shared:
        person = shared.get_one(User, member.kw["info"]["user_id"])
        person.telegram_linked_at = at


async def test_a_button_older_than_the_link_does_nothing(
    both: Application,  # type: ignore[type-arg]  # see build_bot
    member: sessionmaker[Session],
) -> None:
    sent = datetime.fromtimestamp(DATE, UTC)
    _linked_at(member, sent + timedelta(seconds=1))
    assert await run(both, press("q:rest:1", TELEGRAM_MEMBER)) == {}
    _linked_at(member, sent + timedelta(microseconds=500_000))  # within the message's second
    assert await run(both, press("q:rest:1", TELEGRAM_MEMBER)) != {}
    assert await run(both, command("/today", TELEGRAM_MEMBER)) != {}  # messages aren't buttons
