from datetime import UTC, date, datetime, time
from unittest.mock import AsyncMock

import pytest
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
from training_coach.bot.app import MORNING_JOB, NUDGE_JOB, Handlers
from training_coach.bot.messages import NUDGE
from training_coach.db.models import Workout
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
        "Paused: yes, no messages until you resume",
    ]
    labels = [b.text for row in settings_ui.keyboard(prefs).inline_keyboard for b in row]
    assert "• 07:00" in labels
    assert "• 20:00" in labels
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
    bad = await run(application, text_message("half eight", OWNER))
    assert texts(bad) == [settings_ui.BAD_TIME]
    good = await run(application, text_message("20:30", OWNER))
    assert "Evening nudge: 20:30 (on)" in texts(good)[0]
    assert _prefs(seeded).nudge_time == time(20, 30)
    assert _next_run(application, NUDGE_JOB) == datetime(2026, 10, 6, 18, 30, tzinfo=UTC)
    # The question is answered: the next plain text is no longer read as a time.
    assert await run(application, text_message("21:00", OWNER)) == {}


async def test_settings_command_cancels_a_pending_question(
    application: App, seeded: Sessions
) -> None:
    await run(application, press("s:ask-morning", OWNER))
    await run(application, command("/settings", OWNER))
    assert await run(application, text_message("06:00", OWNER)) == {}
    assert _prefs(seeded).morning_time == time(7, 30)


async def test_text_is_ignored_unless_asked(application: App) -> None:
    assert await run(application, text_message("07:00", OWNER)) == {}


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
