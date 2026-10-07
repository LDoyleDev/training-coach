from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import (
    OWNER,
    SETTINGS,
    STRANGER,
    button_data,
    command,
    press,
    run,
    text_message,
    texts,
)
from training_coach.bot import settings as settings_ui
from training_coach.bot.app import MORNING_JOB, NUDGE_JOB, REVIEW_JOB, Handlers
from training_coach.bot.messages import NUDGE, SOMETHING_WENT_WRONG
from training_coach.db.models import Workout
from training_coach.db.session import make_session_factory
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import user_settings
from training_coach.services.user_settings import Prefs

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]


def _prefs(sessions: Sessions) -> Prefs:
    with sessions() as session:
        return user_settings.load(session)


def _set(sessions: Sessions, **changes: object) -> None:
    with sessions() as session:
        user_settings.update(session, **changes)  # type: ignore[arg-type]
        session.commit()


def _next_run(application: App, name: str) -> datetime:
    assert application.job_queue is not None
    (job,) = application.job_queue.get_jobs_by_name(name)
    fire: datetime = job.job.trigger.get_next_fire_time(None, datetime(2026, 10, 6, 12, tzinfo=UTC))
    return fire.astimezone(UTC)


# ------------------------------------------------------------------ parsing and layout


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("s:morning:0645", settings_ui.Press("morning", time(6, 45))),
        ("s:nudge:2100", settings_ui.Press("nudge", time(21, 0))),
        ("s:ask-morning", settings_ui.Press("ask-morning")),
        ("s:review:2000", settings_ui.Press("review", time(20, 0))),
        ("s:ask-review", settings_ui.Press("ask-review")),
        ("s:nudges:off", settings_ui.Press("nudges", on=False)),
        ("s:pause:on", settings_ui.Press("pause", on=True)),
        ("s:pause", None),
        ("s:pause:maybe", None),
        ("s:morning:2560", None),
        ("s:morning:645", None),
        ("s:morning", None),
        ("s:dance", None),
        ("q:rest:1", None),
        (None, None),
    ],
)
def test_parse(data: str | None, expected: settings_ui.Press | None) -> None:
    assert settings_ui.parse(data) == expected


def test_text_and_keyboard_show_the_current_values() -> None:
    prefs = Prefs(morning_time=time(7, 0), nudges_enabled=False, paused=True)
    assert settings_ui.text(prefs).splitlines()[2:] == [
        "Morning message: 07:00",
        "Evening nudge: 20:00 (off)",
        "Weekly review: Sundays 19:00",
        "Paused: yes, no messages until you resume",
    ]
    labels = [b.text for row in settings_ui.keyboard(prefs).inline_keyboard for b in row]
    assert "• 07:00" in labels
    assert "• 20:00" in labels
    assert "Review • 19:00" in labels
    assert "Review: other time…" in labels
    assert "Turn nudges on" in labels
    assert "Resume" in labels


# ------------------------------------------------------------------ through the bot


@pytest.mark.parametrize(("sender", "replies"), [(OWNER, 1), (STRANGER, 0)])
async def test_settings_command_is_owner_only(application: App, sender: int, replies: int) -> None:
    calls = await run(application, command("/settings", sender))
    assert len(texts(calls)) == replies
    if replies:
        assert "s:pause:on" in button_data(calls["sendMessage"][0])


@pytest.mark.parametrize(
    "data", ["s:morning:0645", "s:pause:on", "s:nudges:off", "s:ask-morning", "s:x"]
)
async def test_strangers_settings_presses_do_nothing(
    application: App, seeded: Sessions, data: str
) -> None:
    assert await run(application, press(data, STRANGER)) == {}
    assert _prefs(seeded) == Prefs()


async def test_morning_preset_saves_and_reschedules(application: App, seeded: Sessions) -> None:
    calls = await run(application, press("s:morning:0645", OWNER))
    assert _prefs(seeded).morning_time == time(6, 45)
    assert "Morning message: 06:45" in calls["editMessageText"][0]["text"]
    assert _next_run(application, MORNING_JOB) == datetime(2026, 10, 7, 4, 45, tzinfo=UTC)


async def test_nudge_preset_reschedules_the_nudge(application: App, seeded: Sessions) -> None:
    assert _next_run(application, NUDGE_JOB) == datetime(2026, 10, 6, 18, 0, tzinfo=UTC)
    await run(application, press("s:nudge:2100", OWNER))
    assert _prefs(seeded).nudge_time == time(21, 0)
    assert _next_run(application, NUDGE_JOB) == datetime(2026, 10, 6, 19, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("data", "field", "value"),
    [
        ("s:pause:on", "paused", True),
        ("s:pause:off", "paused", False),
        ("s:nudges:off", "nudges_enabled", False),
        ("s:nudges:on", "nudges_enabled", True),
    ],
)
async def test_toggles_set_their_value(
    application: App, seeded: Sessions, data: str, field: str, value: bool
) -> None:
    """A button on an old /settings message sets what it says, never the opposite."""
    await run(application, press(data, OWNER))
    assert getattr(_prefs(seeded), field) is value
    await run(application, press(data, OWNER))
    assert getattr(_prefs(seeded), field) is value


async def test_typed_time_after_other(application: App, seeded: Sessions) -> None:
    asked = await run(application, press("s:ask-nudge", OWNER))
    assert texts(asked) == ["Send the nudge time as HH:MM, for example 07:15."]
    bad = await run(application, text_message("7:3", OWNER))
    assert texts(bad) == [settings_ui.BAD_TIME]
    good = await run(application, text_message("20:30", OWNER))
    assert "Evening nudge: 20:30 (on)" in texts(good)[0]
    assert _prefs(seeded).nudge_time == time(20, 30)
    assert _next_run(application, NUDGE_JOB) == datetime(2026, 10, 6, 18, 30, tzinfo=UTC)
    # The question is answered: the next plain text is a workout log, not a time.
    reply = texts(await run(application, text_message("21:00", OWNER)))
    assert reply[0].startswith("I couldn't read that log")
    assert _prefs(seeded).nudge_time == time(20, 30)


async def test_settings_command_cancels_a_pending_question(
    application: App, seeded: Sessions
) -> None:
    await run(application, press("s:ask-morning", OWNER))
    await run(application, command("/settings", OWNER))
    reply = texts(await run(application, text_message("06:00", OWNER)))
    assert reply[0].startswith("I couldn't read that log")
    assert _prefs(seeded).morning_time == time(7, 30)


async def test_text_without_a_question_is_a_log(application: App, seeded: Sessions) -> None:
    reply = texts(await run(application, text_message("07:00", OWNER)))
    assert reply[0].startswith("I couldn't read that log")
    assert _prefs(seeded) == Prefs()


async def test_strangers_text_is_ignored_even_mid_question(
    application: App, seeded: Sessions
) -> None:
    await run(application, press("s:ask-morning", OWNER))
    assert await run(application, text_message("05:00", STRANGER)) == {}
    assert _prefs(seeded).morning_time == time(7, 30)


# ------------------------------------------------------------------ evening nudge


def _context() -> object:
    return type("Ctx", (), {"bot": AsyncMock()})()


async def test_nudge_when_nothing_is_logged(seeded: Sessions) -> None:
    context = _context()
    await Handlers(SETTINGS, seeded).nudge(context)  # type: ignore[arg-type]
    kwargs = context.bot.send_message.await_args.kwargs  # type: ignore[attr-defined]
    assert kwargs["chat_id"] == OWNER
    assert kwargs["text"].startswith("Nothing logged today yet.")
    assert NUDGE.split("{")[0] in kwargs["text"]
    assert kwargs["reply_markup"] is not None


@pytest.mark.parametrize(
    "setup",
    [
        {"paused": True},
        {"nudges_enabled": False},
    ],
)
async def test_nudge_respects_settings(seeded: Sessions, setup: dict[str, bool]) -> None:
    _set(seeded, **setup)
    context = _context()
    await Handlers(SETTINGS, seeded).nudge(context)  # type: ignore[arg-type]
    context.bot.send_message.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.parametrize("status", list(WorkoutStatus))
async def test_any_workout_today_silences_the_nudge(
    seeded: Sessions, status: WorkoutStatus
) -> None:
    handlers = Handlers(SETTINGS, seeded)
    with seeded() as session:
        session.add(Workout(local_date=handlers._local_today(), template_id=None, status=status))
        session.commit()
    context = _context()
    await handlers.nudge(context)  # type: ignore[arg-type]
    context.bot.send_message.assert_not_awaited()  # type: ignore[attr-defined]


async def test_yesterdays_workout_does_not_silence_the_nudge(seeded: Sessions) -> None:
    with seeded() as session:
        session.add(
            Workout(local_date=date(2000, 1, 1), template_id=None, status=WorkoutStatus.DONE)
        )
        session.commit()
    context = _context()
    await Handlers(SETTINGS, seeded).nudge(context)  # type: ignore[arg-type]
    context.bot.send_message.assert_awaited_once()  # type: ignore[attr-defined]


async def test_no_nudge_without_a_plan(sessions: Sessions) -> None:
    context = _context()
    await Handlers(SETTINGS, sessions).nudge(context)  # type: ignore[arg-type]
    context.bot.send_message.assert_not_awaited()  # type: ignore[attr-defined]


async def test_pressing_a_toggle_on_an_unchanged_message_is_not_an_error(
    application: App, seeded: Sessions
) -> None:
    calls = await run(application, press("s:pause:on", OWNER), unmodified=True)
    assert SOMETHING_WENT_WRONG not in texts(calls)
    assert _prefs(seeded).paused


# ------------------------------------------------------------------ weekly review (#73)


def _review_run(application: App, after: datetime) -> datetime:
    assert application.job_queue is not None
    (job,) = application.job_queue.get_jobs_by_name(REVIEW_JOB)
    fire: datetime = job.job.trigger.get_next_fire_time(None, after)
    return fire.astimezone(UTC)


@pytest.mark.parametrize(
    ("after", "expected"),
    [
        pytest.param(
            datetime(2026, 10, 6, 12, tzinfo=UTC),  # a Tuesday
            datetime(2026, 10, 11, 17, 0, tzinfo=UTC),  # Sunday 19:00 CEST
            id="next-sunday",
        ),
        pytest.param(
            datetime(2026, 10, 24, 12, tzinfo=UTC),
            datetime(2026, 10, 25, 18, 0, tzinfo=UTC),  # clocks went back that morning: CET
            id="fall-back-sunday",
        ),
        pytest.param(
            datetime(2027, 3, 27, 12, tzinfo=UTC),
            datetime(2027, 3, 28, 17, 0, tzinfo=UTC),  # clocks went forward that morning: CEST
            id="spring-forward-sunday",
        ),
    ],
)
def test_the_review_goes_out_on_sundays_at_seven_local(
    application: App, after: datetime, expected: datetime
) -> None:
    assert _review_run(application, after) == expected


async def test_review_preset_saves_and_reschedules(application: App, seeded: Sessions) -> None:
    calls = await run(application, press("s:review:2000", OWNER))
    assert _prefs(seeded).review_time == time(20, 0)
    assert "Weekly review: Sundays 20:00" in calls["editMessageText"][0]["text"]
    assert _review_run(application, datetime(2026, 10, 6, 12, tzinfo=UTC)) == datetime(
        2026, 10, 11, 18, 0, tzinfo=UTC
    )


async def test_typed_review_time_after_other(application: App, seeded: Sessions) -> None:
    asked = await run(application, press("s:ask-review", OWNER))
    assert texts(asked) == ["Send the review time as HH:MM, for example 07:15."]
    await run(application, text_message("17:45", OWNER))
    assert _prefs(seeded).review_time == time(17, 45)
    assert _review_run(application, datetime(2026, 10, 6, 12, tzinfo=UTC)) == datetime(
        2026, 10, 11, 15, 45, tzinfo=UTC
    )


async def test_the_review_is_sent_to_the_owner(seeded: Sessions) -> None:
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    await Handlers(SETTINGS, seeded).weekly_review(context)  # type: ignore[arg-type]  # fake
    context.bot.send_message.assert_awaited_once()
    kwargs = context.bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == OWNER
    assert kwargs["text"].startswith("Week of ")


async def test_the_review_is_skipped_while_paused(seeded: Sessions) -> None:
    _set(seeded, paused=True)
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    await Handlers(SETTINGS, seeded).weekly_review(context)  # type: ignore[arg-type]  # fake
    context.bot.send_message.assert_not_awaited()


async def test_the_review_survives_a_database_error() -> None:
    broken = make_session_factory(create_engine("sqlite://"), user_id=1)
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    await Handlers(SETTINGS, broken).weekly_review(context)  # type: ignore[arg-type]  # fake
    context.bot.send_message.assert_not_awaited()
