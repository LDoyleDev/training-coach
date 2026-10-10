"""Test days in the bot (#95, ADR-0038): the morning message and the evening nudge."""

from datetime import timedelta
from unittest.mock import AsyncMock

from sqlalchemy.orm import Session, sessionmaker

from tests.bot.fakes import SETTINGS
from training_coach.bot.app import Handlers
from training_coach.db.models import FitnessTestDay
from training_coach.services import user_settings

Sessions = sessionmaker[Session]
WITH_URL = SETTINGS.model_copy(update={"public_url": "https://coach.example.com"})


def _tested(sessions: Sessions, days_ago: int, day: int, handlers: Handlers) -> None:
    with sessions() as session:
        session.add(
            FitnessTestDay(
                local_date=handlers._local_today() - timedelta(days=days_ago),
                day=day,
                time_of_day="morning",
                fed=True,
                slept_well=True,
                results=[],
                token=f"bot-{days_ago}-{day}".ljust(20, "x"),
            )
        )
        session.commit()


def _context() -> object:
    return type("Ctx", (), {"bot": AsyncMock()})()


def _buttons(kwargs: dict[str, object]) -> list[tuple[str, str]]:
    markup = kwargs["reply_markup"]
    return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row]  # type: ignore[attr-defined]


async def test_a_test_day_morning_names_the_tests_and_where_to_enter_them(
    seeded: Sessions,
) -> None:
    handlers = Handlers(WITH_URL, seeded)
    _, before = handlers._today()
    assert before is not None
    session_id = before.inline_keyboard[0][0].callback_data
    _tested(seeded, 1, 1, handlers)
    context = _context()
    await handlers.morning(context)  # type: ignore[arg-type]
    kwargs = context.bot.send_message.await_args.kwargs  # type: ignore[attr-defined]
    text = kwargs["text"]
    assert text.startswith("Today: Baseline tests, day 2\n")
    assert "Bulgarian split squat" in text
    assert "Enter the results in the app: https://coach.example.com/tests" in text
    assert "The plan waits:" in text
    (button,) = _buttons(kwargs)
    assert button[0].startswith("Train ")
    assert button[0].endswith(" instead")
    assert button[1] == session_id  # Start on the waiting session


async def test_without_a_public_url_the_tests_page_is_named(seeded: Sessions) -> None:
    handlers = Handlers(SETTINGS, seeded)
    _tested(seeded, 1, 1, handlers)
    text, _ = handlers._today()
    assert "Enter the results in the app: the Tests page of the web app" in text


async def test_the_nudge_on_a_test_day_points_to_the_tests(seeded: Sessions) -> None:
    handlers = Handlers(WITH_URL, seeded)
    _tested(seeded, 1, 1, handlers)
    with seeded() as session:
        user_settings.update(session, habits_enabled=False)
        session.commit()
    context = _context()
    await handlers.nudge(context)  # type: ignore[arg-type]
    kwargs = context.bot.send_message.await_args.kwargs  # type: ignore[attr-defined]
    assert kwargs["text"] == (
        "Nothing logged today yet. Baseline tests, day 2 is still waiting: "
        "https://coach.example.com/tests."
    )
    assert len(_buttons(kwargs)) == 1


async def test_a_test_day_saved_today_silences_the_nudge(seeded: Sessions) -> None:
    handlers = Handlers(WITH_URL, seeded)
    _tested(seeded, 0, 1, handlers)
    with seeded() as session:
        user_settings.update(session, habits_enabled=False)
        session.commit()
    context = _context()
    await handlers.nudge(context)  # type: ignore[arg-type]
    context.bot.send_message.assert_not_awaited()  # type: ignore[attr-defined]
