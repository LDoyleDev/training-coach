"""Plan notices on Telegram (ADR-0087): told once, one that couldn't get through tries again."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine, select

from training_coach.bot.notices import NoticeHandlers, message
from training_coach.config import Settings
from training_coach.db.models import PlanNotice
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services.users import OWNER

CHAT = 4242
SETTINGS = Settings(environment="test", telegram_allowed_user_id=CHAT)


def _handlers(engine: Engine, outcome: str) -> tuple[NoticeHandlers, list[tuple[int, str]]]:
    sent: list[tuple[int, str]] = []

    async def send(_bot: Any, chat: int, text: str) -> str:
        sent.append((chat, text))
        return outcome

    return NoticeHandlers(SETTINGS, make_session_factory(engine, user_id=OWNER), send), sent


def _add(engine: Engine, *texts: str) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        bound.add_all(PlanNotice(text=text) for text in texts)


def _told(engine: Engine) -> list[bool]:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        return [n.told_at is not None for n in bound.scalars(select(PlanNotice))]


def test_the_message_lists_them() -> None:
    assert message(["One.", "Two."]) == "Something changed in your plan:\n- One.\n- Two."


@pytest.mark.parametrize("outcome", ["sent", "refused"])
async def test_they_are_told_once_in_one_message(engine: Engine, outcome: str) -> None:
    _add(engine, "One.", "Two.")
    handlers, sent = _handlers(engine, outcome)
    await handlers.tell(MagicMock())
    await handlers.tell(MagicMock())
    assert sent == [(CHAT, message(["One.", "Two."]))]
    assert _told(engine) == [True, True]


async def test_unreachable_tries_again_next_time(engine: Engine) -> None:
    _add(engine, "One.")
    handlers, sent = _handlers(engine, "unreachable")
    await handlers.tell(MagicMock())
    assert _told(engine) == [False]
    await handlers.tell(MagicMock())
    assert len(sent) == 2


async def test_nothing_to_tell_sends_nothing(engine: Engine) -> None:
    handlers, sent = _handlers(engine, "sent")
    await handlers.tell(MagicMock())
    assert sent == []
