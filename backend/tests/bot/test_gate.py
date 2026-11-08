"""The sender gate (ADR-0089): only a message or a button press, in a private chat, from someone
linked gets past it; a member only while TC_MULTI_USER is on; and it fails closed."""

from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker
from telegram import Update
from telegram.ext import Application, ApplicationHandlerStop

from tests.bot.fakes import (
    BOT_USER,
    DATE,
    OWNER,
    SETTINGS,
    STRANGER,
    command,
    press,
    run,
    text_message,
    texts,
    voice,
)
from training_coach.bot.app import ALLOWED_UPDATES, build_bot
from training_coach.bot.gate import Gate
from training_coach.db.models import Event, User
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.services import users

MEMBER_TELEGRAM = 77


def _message(chat: dict[str, Any], sender: int = OWNER, text: str = "/today") -> dict[str, Any]:
    return {
        "message_id": 5,
        "date": DATE,
        "chat": chat,
        "from": {"id": sender, "is_bot": False, "first_name": "Someone"},
        "text": text,
        "entities": [{"type": "bot_command", "offset": 0, "length": len(text)}],
    }


PRIVATE = {"id": OWNER, "type": "private"}
# Every other kind of update the owner could be part of: none gets past the gate.
OTHER_KINDS: dict[str, dict[str, Any]] = {
    "edited message": {"update_id": 11, "edited_message": _message(PRIVATE) | {"edit_date": DATE}},
    "business message": {
        "update_id": 12,
        "business_message": _message(PRIVATE) | {"business_connection_id": "bc1"},
    },
    "channel post": {
        "update_id": 13,
        "channel_post": {
            "message_id": 5,
            "date": DATE,
            "chat": {"id": -100, "type": "channel", "title": "News"},
            "text": "/today",
        },
    },
    "group message": {
        "update_id": 14,
        "message": _message({"id": -5, "type": "group", "title": "Family"}),
    },
    "a chat that isn't the sender's": {
        "update_id": 15,
        "message": _message({"id": STRANGER, "type": "private"}),
    },
    "inline button with no message": {
        "update_id": 16,
        "callback_query": {
            "id": "cb2",
            "from": {"id": OWNER, "is_bot": False, "first_name": "Someone"},
            "chat_instance": "ci",
            "inline_message_id": "im1",
            "data": "q:rest:1",
        },
    },
    "membership change": {
        "update_id": 17,
        "my_chat_member": {
            "chat": PRIVATE,
            "from": {"id": OWNER, "is_bot": False, "first_name": "Someone"},
            "date": DATE,
            "old_chat_member": {"status": "member", "user": BOT_USER},
            "new_chat_member": {"status": "kicked", "user": BOT_USER, "until_date": 0},
        },
    },
}


def _events(engine: Engine) -> int:
    with session_scope(make_session_factory(engine)) as shared:
        return len(shared.scalars(select(Event.id), execution_options={ALL_USERS: True}).all())


@pytest.mark.parametrize(
    "update",
    [
        command("/today", STRANGER),
        command("/recover", STRANGER),
        command("/start abc", STRANGER),
        text_message("pull-ups 8 8 7", STRANGER),
        voice(STRANGER),
        press("q:rest:1", STRANGER),
    ],
)
async def test_a_stranger_gets_nothing_and_changes_nothing(
    application: Application,  # type: ignore[type-arg]  # see build_bot
    engine: Engine,
    update: dict[str, Any],
) -> None:
    before = _events(engine)
    assert await run(application, update) == {}  # not a reply, not a button answer
    assert _events(engine) == before


@pytest.mark.parametrize("update", OTHER_KINDS.values(), ids=OTHER_KINDS.keys())
async def test_only_private_messages_and_presses_get_through(
    application: Application,  # type: ignore[type-arg]  # see build_bot
    update: dict[str, Any],
) -> None:
    assert await run(application, update) == {}


def test_the_bot_asks_telegram_for_nothing_else() -> None:
    assert ALLOWED_UPDATES == ("message", "callback_query")


def _member(engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2, role=users.MEMBER, telegram_user_id=MEMBER_TELEGRAM))


async def test_a_member_gets_nothing_while_the_switch_is_off(
    application: Application,  # type: ignore[type-arg]  # see build_bot
    engine: Engine,
) -> None:
    _member(engine)
    for update in (command("/today", MEMBER_TELEGRAM), press("q:rest:1", MEMBER_TELEGRAM)):
        assert await run(application, update) == {}


async def _check(gate: Gate, update: dict[str, Any]) -> bool:
    """Whether the gate lets ``update`` through (it has no bot to reply with here)."""
    parsed = Update.de_json(update, None)
    assert parsed is not None
    try:
        await gate.check(parsed, None)  # type: ignore[arg-type]  # the gate reads no context
    except ApplicationHandlerStop:
        return False
    return True


async def test_with_the_switch_on_a_member_is_let_through_as_themselves(engine: Engine) -> None:
    _member(engine)
    gate = Gate(SETTINGS.model_copy(update={"multi_user": True}), make_session_factory(engine))
    update = command("/today", MEMBER_TELEGRAM)
    assert await _check(gate, update)
    person = gate.person(Update.de_json(update, None))
    assert person is not None
    assert (person.user_id, person.chat, person.owner, person.health) == (
        2,
        MEMBER_TELEGRAM,
        False,
        False,
    )
    owner = command("/today", OWNER) | {"update_id": 20}
    with session_scope(make_session_factory(engine)) as shared:
        users.link_owner(shared, OWNER)
    assert await _check(gate, owner)
    found = gate.person(Update.de_json(owner, None))
    assert found is not None
    assert (found.owner, found.health) == (True, True)


async def test_a_crash_in_the_gate_lets_nothing_through(
    application: Application,  # type: ignore[type-arg]  # see build_bot
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*_a: object) -> int:
        raise RuntimeError("a bug")

    monkeypatch.setattr(users, "by_telegram", broken)
    assert await run(application, command("/today", OWNER)) == {}
    assert await run(application, press("q:rest:1", OWNER)) == {}


@pytest.mark.parametrize(("sender", "told"), [(OWNER, 1), (STRANGER, 0)])
async def test_a_database_error_is_told_to_the_owner_never_to_a_stranger(
    broken: sessionmaker[Session], sender: int, told: int
) -> None:
    application = build_bot(SETTINGS, broken)
    assert len(texts(await run(application, command("/today", sender)))) == told


async def test_the_gate_remembers_only_the_latest_updates(engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        users.link_owner(shared, OWNER)
    gate = Gate(SETTINGS, make_session_factory(engine))
    for update_id in range(300):
        assert await _check(gate, command("/today", OWNER) | {"update_id": update_id})
    assert len(gate.found) == 256
    assert gate.person(Update.de_json(command("/today", OWNER) | {"update_id": 0}, None)) is None
