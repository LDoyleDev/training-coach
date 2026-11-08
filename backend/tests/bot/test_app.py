import warnings
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker
from telegram.error import Forbidden, NetworkError, RetryAfter, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)
from telegram.warnings import PTBDeprecationWarning

from tests.bot.fakes import OWNER, SETTINGS, STRANGER, command, run, scheduled, texts
from training_coach.bot.app import (
    RESCHEDULE,
    Handlers,
    build_bot,
    send_outcome,
    send_with_retry,
)
from training_coach.bot.messages import NO_PLAN, SOMETHING_WENT_WRONG
from training_coach.bot.schedules import MORNING, name
from training_coach.config import Settings
from training_coach.db.models import ReplacedWorkout, UserSettings
from training_coach.services import user_settings
from training_coach.services.users import OWNER as OWNER_ID


def test_build_bot_requires_the_owners_account(sessions: sessionmaker[Session]) -> None:
    with pytest.raises(ValueError, match="ALLOWED_USER_ID"):
        build_bot(
            Settings(environment="test", telegram_bot_token=SETTINGS.telegram_bot_token), sessions
        )


def test_build_bot_requires_token(sessions: sessionmaker[Session]) -> None:
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        build_bot(Settings(environment="test", telegram_allowed_user_id=1), sessions)


def _served(callback: object) -> bool:
    return hasattr(callback, "__wrapped__")  # registered through gate.served (ADR-0089)


def test_every_handler_is_served_per_person(
    application: Application,  # type: ignore[type-arg]  # see build_bot
) -> None:
    handlers = [h for group in application.handlers.values() for h in group]
    commands = [h for h in handlers if isinstance(h, CommandHandler)]
    assert {c for h in commands for c in h.commands} == {
        "start",
        "help",
        "today",
        "week",
        "login",
        "recover",
        "progress",
        "review",
        "habits",
        "settings",
        "undo",
        "share",
    }
    for handler in commands:
        # The person the gate found, and only in a private chat (ADR-0040).
        assert _served(handler.callback)
        assert handler.filters == filters.ChatType.PRIVATE
    messages = [h for h in handlers if isinstance(h, MessageHandler)]
    assert len(messages) == 2  # text and voice
    assert all(_served(h.callback) for h in messages)
    # Button presses can't carry a filter: the gate is their check, and test_two_people.py
    # proves strangers are ignored by behaviour.
    presses = [h for h in handlers if isinstance(h, CallbackQueryHandler)]
    assert len(presses) == 10
    assert all(_served(h.callback) for h in presses)
    # Nothing else is registered, so nothing else can run without a person.
    assert len(handlers) == len(commands) + len(messages) + len(presses) + 1
    # The sender gate sees every update first: test_gate.py.
    assert [type(h) for h in application.handlers[-1]] == [TypeHandler]


async def _replies(application: Application, text: str, sender: int) -> list[str]:  # type: ignore[type-arg]
    return texts(await run(application, command(text, sender)))


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
    (job,) = application.job_queue.get_jobs_by_name(name(MORNING, OWNER_ID))
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

    with seeded() as session:
        user_settings.update(session, morning_time=time(8, 0))
        session.commit()
    application.bot_data[RESCHEDULE](OWNER_ID)
    assert _next_run(application, after) == datetime(2026, 10, 7, 6, 0, tzinfo=UTC)


def test_the_settings_page_moves_the_jobs_through_bot_data(
    sessions: sessionmaker[Session],
) -> None:
    """The route saves the times first; the bot reads them back for that person."""
    application = build_bot(SETTINGS, sessions)
    with sessions() as session:
        user_settings.update(session, morning_time=time(9, 0))
        session.commit()
    application.bot_data[RESCHEDULE](OWNER_ID)
    after = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
    assert _next_run(application, after) == datetime(2026, 10, 7, 7, 0, tzinfo=UTC)


def _context() -> SimpleNamespace:
    return SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))


async def test_morning_sends_today_to_the_owner(seeded: sessionmaker[Session]) -> None:
    context = _context()
    await Handlers(SETTINGS).morning(context, scheduled(seeded))  # type: ignore[arg-type]  # fake context
    context.bot.send_message.assert_awaited_once()
    kwargs = context.bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == OWNER
    assert kwargs["text"].startswith("Today: ")


async def test_morning_forgets_replaced_workouts_past_the_undo_window(
    seeded: sessionmaker[Session],
) -> None:
    """Review of #240: kept for /undo for 24 hours (ADR-0060), then gone even with no save."""
    with seeded() as session:
        session.add(
            ReplacedWorkout(
                local_date=date(2026, 10, 1),
                data={"sets": []},
                created_at=datetime.now(UTC) - timedelta(days=2),
            )
        )
        session.commit()
    await Handlers(SETTINGS).morning(_context(), scheduled(seeded))  # type: ignore[arg-type]
    with seeded() as session:
        assert session.scalars(select(ReplacedWorkout)).all() == []


async def test_morning_without_a_plan_says_so(sessions: sessionmaker[Session]) -> None:
    context = _context()
    await Handlers(SETTINGS).morning(context, scheduled(sessions))  # type: ignore[arg-type]
    assert context.bot.send_message.await_args.kwargs["text"] == NO_PLAN


async def test_morning_is_skipped_while_paused(seeded: sessionmaker[Session]) -> None:
    with seeded() as session:
        prefs = session.get(UserSettings, 1)
        assert prefs is not None
        prefs.paused = True
        session.commit()
    context = _context()
    await Handlers(SETTINGS).morning(context, scheduled(seeded))  # type: ignore[arg-type]
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


async def test_send_outcome_tells_refused_from_unreachable() -> None:
    blocked = SimpleNamespace(send_message=AsyncMock(side_effect=Forbidden("blocked")))
    assert await send_outcome(blocked, OWNER, "hi", backoff=0) == "refused"  # type: ignore[arg-type]
    down = SimpleNamespace(send_message=AsyncMock(side_effect=NetworkError("down")))
    assert await send_outcome(down, OWNER, "hi", attempts=2, backoff=0) == "unreachable"  # type: ignore[arg-type]
    fine = SimpleNamespace(send_message=AsyncMock(return_value=None))
    assert await send_outcome(fine, OWNER, "hi") == "sent"  # type: ignore[arg-type]


async def test_morning_survives_a_database_error(
    engine: Engine, broken: sessionmaker[Session]
) -> None:
    """No tables: the read fails, nothing is sent and the job does not raise."""
    context = _context()
    await Handlers(SETTINGS).morning(context, scheduled(broken))  # type: ignore[arg-type]
    context.bot.send_message.assert_not_awaited()


@pytest.mark.parametrize(("sender", "replies"), [(OWNER, 1), (STRANGER, 0)])
async def test_a_failing_command_gets_a_fixed_reply_for_the_owner_only(
    sender: int, replies: int, broken: sessionmaker[Session]
) -> None:
    application = build_bot(SETTINGS, broken)
    sent = await _replies(application, "/today", sender)
    assert sent == [SOMETHING_WENT_WRONG] * replies
