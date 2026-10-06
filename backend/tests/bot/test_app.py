import warnings
from datetime import UTC, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs

import pytest
import respx
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from telegram import Bot, Update
from telegram.error import Forbidden, NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, CommandHandler
from telegram.warnings import PTBDeprecationWarning

from training_coach.bot.app import (
    MORNING_JOB,
    Handlers,
    build_bot,
    owner_only,
    schedule_morning,
    send_with_retry,
)
from training_coach.bot.messages import NO_PLAN, SOMETHING_WENT_WRONG
from training_coach.config import Settings
from training_coach.db.models import UserSettings
from training_coach.db.session import make_session_factory
from training_coach.services.seed import apply_seed, load_plan

TELEGRAM = r"https://api\.telegram\.org/bot[^/]+/"
BOT_USER = {"id": 1, "is_bot": True, "first_name": "Coach", "username": "coach_bot"}
OWNER, STRANGER = 42, 99
SETTINGS = Settings(
    environment="test",
    telegram_bot_token=SecretStr("123456:TEST-TOKEN"),
    telegram_allowed_user_id=OWNER,
)


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


@pytest.fixture
def seeded(sessions: sessionmaker[Session]) -> sessionmaker[Session]:
    with sessions() as session:
        apply_seed(session, load_plan())
        session.commit()
    return sessions


@pytest.fixture
def application(seeded: sessionmaker[Session]) -> Application:  # type: ignore[type-arg]  # see build_bot
    return build_bot(SETTINGS, seeded)


def test_owner_only_requires_configured_user() -> None:
    with pytest.raises(ValueError, match="ALLOWED_USER_ID"):
        owner_only(Settings(environment="test"))


def test_build_bot_requires_token(sessions: sessionmaker[Session]) -> None:
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        build_bot(Settings(environment="test", telegram_allowed_user_id=1), sessions)


def test_every_handler_is_restricted_to_owner(application: Application) -> None:  # type: ignore[type-arg]
    handlers = [h for group in application.handlers.values() for h in group]
    assert {c for h in handlers if isinstance(h, CommandHandler) for c in h.commands} == {
        "start",
        "help",
        "today",
        "week",
    }
    for handler in handlers:
        assert isinstance(handler, CommandHandler)
        assert OWNER in handler.filters.user_ids  # type: ignore[union-attr]  # BaseFilter has no user_ids; this one is filters.User


def _command(text: str, user_id: int, bot: Bot) -> Update:
    update = Update.de_json(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1_790_000_000,
                "chat": {"id": user_id, "type": "private"},
                "from": {"id": user_id, "is_bot": False, "first_name": "Someone"},
                "text": text,
                "entities": [{"type": "bot_command", "offset": 0, "length": len(text)}],
            },
        },
        bot,
    )
    assert update is not None
    return update


async def _replies(application: Application, text: str, sender: int) -> list[str]:  # type: ignore[type-arg]
    """Run one command through the real dispatcher with Telegram faked; return replies sent."""
    with respx.mock(assert_all_called=False) as telegram:
        telegram.post(url__regex=TELEGRAM + "getMe$").respond(json={"ok": True, "result": BOT_USER})
        send = telegram.post(url__regex=TELEGRAM + "sendMessage$").respond(
            json={
                "ok": True,
                "result": {
                    "message_id": 2,
                    "date": 1_790_000_000,
                    "chat": {"id": sender, "type": "private"},
                    "text": "ok",
                },
            }
        )
        await application.initialize()
        try:
            await application.process_update(_command(text, sender, application.bot))
        finally:
            await application.shutdown()
    return [parse_qs(call.request.content.decode())["text"][0] for call in send.calls]


@pytest.mark.parametrize("command", ["/help", "/today", "/week"])
@pytest.mark.parametrize(("sender", "replies"), [(OWNER, 1), (STRANGER, 0)])
async def test_only_the_owner_gets_a_reply(
    application: Application,  # type: ignore[type-arg]
    command: str,
    sender: int,
    replies: int,
) -> None:
    """Threat model T1: a real update from a stranger reaches no handler and sends nothing."""
    assert len(await _replies(application, command, sender)) == replies


async def test_today_shows_the_first_session(application: Application) -> None:  # type: ignore[type-arg]
    (text,) = await _replies(application, "/today", OWNER)
    assert text.startswith("Today: ")
    assert " / " in text


async def test_week_lists_seven_days(application: Application) -> None:  # type: ignore[type-arg]
    (text,) = await _replies(application, "/week", OWNER)
    assert len(text.splitlines()) == 2 + 7


async def test_today_without_a_plan_says_so(sessions: sessionmaker[Session]) -> None:
    (text,) = await _replies(build_bot(SETTINGS, sessions), "/today", OWNER)
    assert text == NO_PLAN


# ------------------------------------------------------------------ morning job


def _next_run(application: Application, after: datetime) -> datetime:  # type: ignore[type-arg]
    assert application.job_queue is not None
    (job,) = application.job_queue.get_jobs_by_name(MORNING_JOB)
    fire: datetime = job.job.trigger.get_next_fire_time(None, after)
    return fire.astimezone(UTC)


@pytest.mark.parametrize(
    ("after", "expected_utc"),
    [
        # Spring forward (29 Mar 2026): 07:30 is CEST, UTC+2.
        (datetime(2026, 3, 28, 12, 0, tzinfo=UTC), datetime(2026, 3, 29, 5, 30, tzinfo=UTC)),
        # Fall back (25 Oct 2026): 07:30 is CET, UTC+1.
        (datetime(2026, 10, 24, 12, 0, tzinfo=UTC), datetime(2026, 10, 25, 6, 30, tzinfo=UTC)),
    ],
)
def test_morning_follows_local_time_across_dst(
    application: Application,  # type: ignore[type-arg]
    after: datetime,
    expected_utc: datetime,
) -> None:
    assert _next_run(application, after) == expected_utc


def test_morning_uses_the_saved_time_and_reschedules(
    seeded: sessionmaker[Session],
) -> None:
    with seeded() as session:
        prefs = session.get(UserSettings, 1)
        assert prefs is not None
        prefs.morning_time = time(6, 15)
        session.commit()
    application = build_bot(SETTINGS, seeded)
    after = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
    assert _next_run(application, after) == datetime(2026, 10, 7, 4, 15, tzinfo=UTC)

    schedule_morning(application, Handlers(SETTINGS, seeded), time(8, 0))
    assert _next_run(application, after) == datetime(2026, 10, 7, 6, 0, tzinfo=UTC)


def _context() -> SimpleNamespace:
    return SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))


async def test_morning_sends_today_to_the_owner(seeded: sessionmaker[Session]) -> None:
    context = _context()
    await Handlers(SETTINGS, seeded).morning(context)  # type: ignore[arg-type]  # fake context
    context.bot.send_message.assert_awaited_once()
    kwargs = context.bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == OWNER
    assert kwargs["text"].startswith("Today: ")


async def test_morning_without_a_plan_says_so(sessions: sessionmaker[Session]) -> None:
    context = _context()
    await Handlers(SETTINGS, sessions).morning(context)  # type: ignore[arg-type]
    assert context.bot.send_message.await_args.kwargs["text"] == NO_PLAN


async def test_morning_is_skipped_while_paused(seeded: sessionmaker[Session]) -> None:
    with seeded() as session:
        prefs = session.get(UserSettings, 1)
        assert prefs is not None
        prefs.paused = True
        session.commit()
    context = _context()
    await Handlers(SETTINGS, seeded).morning(context)  # type: ignore[arg-type]
    context.bot.send_message.assert_not_awaited()


async def test_send_retries_network_errors() -> None:
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=[TimedOut(), NetworkError("x"), None]))
    assert await send_with_retry(bot, OWNER, "hi", backoff=0)  # type: ignore[arg-type]
    assert bot.send_message.await_count == 3


async def test_send_gives_up_after_the_last_attempt() -> None:
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=NetworkError("down")))
    assert not await send_with_retry(bot, OWNER, "hi", attempts=2, backoff=0)  # type: ignore[arg-type]
    assert bot.send_message.await_count == 2


async def test_send_waits_out_flood_control() -> None:
    with warnings.catch_warnings():  # PTB's own __init__ reads its deprecated int property
        warnings.simplefilter("ignore", PTBDeprecationWarning)
        flood = RetryAfter(0)
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=[flood, None]))
    assert await send_with_retry(bot, OWNER, "hi", backoff=0)  # type: ignore[arg-type]
    assert bot.send_message.await_count == 2


async def test_send_gives_up_on_other_telegram_errors() -> None:
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=Forbidden("blocked")))
    assert not await send_with_retry(bot, OWNER, "hi", backoff=0)  # type: ignore[arg-type]
    assert bot.send_message.await_count == 1


async def test_morning_survives_a_database_error(engine: Engine) -> None:
    """No tables: the read fails, nothing is sent and the job does not raise."""
    broken = make_session_factory(create_engine("sqlite://"))
    context = _context()
    await Handlers(SETTINGS, broken).morning(context)  # type: ignore[arg-type]
    context.bot.send_message.assert_not_awaited()


@pytest.mark.parametrize(("sender", "replies"), [(OWNER, 1), (STRANGER, 0)])
async def test_a_failing_command_gets_a_fixed_reply_for_the_owner_only(
    sender: int, replies: int
) -> None:
    broken = make_session_factory(create_engine("sqlite://"))
    application = build_bot(SETTINGS, broken)
    sent = await _replies(application, "/today", sender)
    assert sent == [SOMETHING_WENT_WRONG] * replies
