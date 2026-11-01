"""The bot pauses 30 days after its person's last visit from the EU or EEA (ADR-0085): one line
for anything sent, nothing scheduled, but /login and /recover still answered."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session, sessionmaker
from telegram import CallbackQuery
from telegram.error import BadRequest
from telegram.ext import Application

from tests.bot.fakes import OWNER, SETTINGS, STRANGER, command, press, run, text_message, texts
from training_coach.bot.app import AWAY_TEXT, LOGIN_OFF, Handlers
from training_coach.db.models import User
from training_coach.services import users


def _last_seen(sessions: sessionmaker[Session], days_ago: float) -> None:
    with sessions() as session:
        user = session.get(User, users.OWNER)
        assert user is not None
        user.last_seen_in_europe = datetime.now(UTC) - timedelta(days=days_ago)
        session.commit()


@pytest.mark.parametrize(
    "update",
    [command("/today", OWNER), text_message("pull-ups 8 8 7", OWNER), press("q:rest:1", OWNER)],
)
async def test_after_30_days_away_the_owner_gets_one_line(
    application: Application,  # type: ignore[type-arg]
    seeded: sessionmaker[Session],
    update: dict[str, object],
) -> None:
    _last_seen(seeded, 31)
    calls = await run(application, update)
    assert texts(calls) == [AWAY_TEXT]
    assert len(calls.get("answerCallbackQuery", [])) == ("callback_query" in update)


async def test_within_30_days_the_bot_answers_as_usual(
    application: Application,  # type: ignore[type-arg]
    seeded: sessionmaker[Session],
) -> None:
    _last_seen(seeded, 29.9)
    (text,) = texts(await run(application, command("/today", OWNER)))
    assert text.startswith("Today: ")


@pytest.mark.parametrize("name", ["/login", "/recover"])
async def test_signing_in_still_works_while_paused(
    application: Application,  # type: ignore[type-arg]
    seeded: sessionmaker[Session],
    name: str,
) -> None:
    """The website is the way back: a visit from Europe there turns the bot on again."""
    _last_seen(seeded, 90)
    assert texts(await run(application, command(name, OWNER))) == [LOGIN_OFF]


async def test_strangers_get_nothing_even_while_paused(
    application: Application,  # type: ignore[type-arg]
    seeded: sessionmaker[Session],
) -> None:
    _last_seen(seeded, 31)
    assert texts(await run(application, command("/today", STRANGER))) == []
    assert texts(await run(application, text_message("hi", STRANGER))) == []


async def test_scheduled_messages_are_skipped_while_paused(
    seeded: sessionmaker[Session],
) -> None:
    job = AsyncMock(return_value=None)
    paused = Handlers(SETTINGS, seeded).unless_away(job)
    _last_seen(seeded, 31)
    await paused(AsyncMock())
    job.assert_not_awaited()
    _last_seen(seeded, 0)
    await paused(AsyncMock())
    job.assert_awaited_once()


async def test_a_failed_reply_still_stops_the_update(
    application: Application,  # type: ignore[type-arg]
    seeded: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale button can't be answered: the press must still not reach its handler."""
    monkeypatch.setattr(CallbackQuery, "answer", AsyncMock(side_effect=BadRequest("too old")))
    _last_seen(seeded, 31)
    calls = await run(application, press("q:rest:1", OWNER))
    assert texts(calls) == []
    assert not {"editMessageText", "editMessageReplyMarkup"} & set(calls)


async def test_every_scheduled_job_is_paused(
    application: Application,  # type: ignore[type-arg]
    seeded: sessionmaker[Session],
) -> None:
    """Daily messages and the band and proposal checks alike."""
    _last_seen(seeded, 31)
    jobs = application.job_queue.jobs() if application.job_queue else ()
    assert len(jobs) >= 6
    context = AsyncMock()
    for job in jobs:
        await job.callback(context)
    assert not context.bot.mock_calls
