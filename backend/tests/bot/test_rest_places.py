"""Rest places in the bot (ADR-0091): the morning message says it's a rest day and offers no
buttons, and the evening nudge stays quiet, unless a session was picked for the day."""

from datetime import timedelta
from unittest.mock import AsyncMock

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tests.bot.fakes import SETTINGS, scheduled
from training_coach.bot.app import Handlers
from training_coach.db.models import PlanState, SessionTemplate, Workout
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import queue_actions, user_settings

Sessions = sessionmaker[Session]
WITH_URL = SETTINGS.model_copy(update={"public_url": "https://coach.example.com"})


def _rest_today(sessions: Sessions, handlers: Handlers) -> str:
    """The first session done yesterday, with a rest place after it. The next one's name."""
    with sessions() as session:
        first, second = session.scalars(
            select(SessionTemplate).order_by(SessionTemplate.position).limit(2)
        )
        first.rest_after = 1
        session.add(
            Workout(
                local_date=handlers._local_today() - timedelta(days=1),
                template_id=first.id,
                status=WorkoutStatus.DONE,
            )
        )
        session.scalars(select(PlanState)).one().next_template_id = second.id
        user_settings.update(session, habits_enabled=False)
        session.commit()
        return second.name


async def test_the_morning_of_a_rest_day_says_so(seeded: Sessions) -> None:
    handlers = Handlers(WITH_URL)
    upcoming = _rest_today(seeded, handlers)
    text, markup = handlers._today(seeded)
    assert text == f"Today: rest day. No session planned.\nNext: {upcoming}."
    assert markup is not None
    rows = [(b.text, b.url) for row in markup.inline_keyboard for b in row]
    assert rows == [("Open in app", "https://coach.example.com/session")]  # no Start or Rest


async def test_no_nudge_on_a_rest_day(seeded: Sessions) -> None:
    handlers = Handlers(WITH_URL)
    _rest_today(seeded, handlers)
    context = type("Ctx", (), {"bot": AsyncMock()})()
    await handlers.nudge(context, scheduled(seeded))  # type: ignore[arg-type]
    context.bot.send_message.assert_not_awaited()  # type: ignore[attr-defined]


async def test_a_pick_on_a_rest_day_makes_it_a_training_day(seeded: Sessions) -> None:
    """Train today instead, in the app (a pick): the bot offers the session, as the app does."""
    handlers = Handlers(WITH_URL)
    upcoming = _rest_today(seeded, handlers)
    with seeded() as session:
        pointer = session.scalars(select(PlanState)).one().next_template_id
        assert pointer is not None
        queue_actions.pick(session, pointer, pointer)
        session.commit()
    text, _ = handlers._today(seeded)
    assert text.startswith(f"Today: {upcoming}\n")
    context = type("Ctx", (), {"bot": AsyncMock()})()
    await handlers.nudge(context, scheduled(seeded))  # type: ignore[arg-type]
    context.bot.send_message.assert_awaited_once()  # type: ignore[attr-defined]
