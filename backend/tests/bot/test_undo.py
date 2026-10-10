"""/undo through the bot (ADR-0048): the confirm step, owner-only."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, STRANGER, button_data, command, press, run, texts
from training_coach.bot import undo as undo_ui
from training_coach.db.models import Event, PlanState, Workout

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]


def _pointer(sessions: Sessions) -> int:
    with sessions() as session:
        pointer = session.scalars(select(PlanState.next_template_id)).one()
        assert pointer is not None
        return pointer


def _workouts(sessions: Sessions) -> int:
    with sessions() as session:
        return len(list(session.scalars(select(Workout.id))))


def _last_event(sessions: Sessions) -> int:
    with sessions() as session:
        return session.scalars(select(Event.id).order_by(Event.id.desc())).first() or 0


@pytest.mark.parametrize(
    ("data", "expected"),
    [("u:12", 12), ("u:keep", 0), ("u:0", None), ("u:+1", None), ("q:12", None), (None, None)],
)
def test_parse(data: str | None, expected: int | None) -> None:
    assert undo_ui.parse(data) == expected


async def test_nothing_to_undo(application: App, seeded: Sessions) -> None:
    calls = await run(application, command("/undo", OWNER))
    assert texts(calls) == [undo_ui.REFUSED["nothing"]]


async def test_rest_then_undo_puts_the_session_back(application: App, seeded: Sessions) -> None:
    tid = _pointer(seeded)
    await run(application, press(f"q:rest:{tid}", OWNER))
    assert _workouts(seeded) == 1
    asked = await run(application, command("/undo", OWNER))
    (question,) = texts(asked)
    assert question.startswith("Undo the rest day for ")
    event = _last_event(seeded)
    assert button_data(asked["sendMessage"][0]) == [f"u:{event}", "u:keep"]
    calls = await run(application, press(f"u:{event}", OWNER))
    (reply,) = texts(calls)
    assert reply.startswith("Undone: the rest day for ")
    assert _workouts(seeded) == 0
    assert _pointer(seeded) == tid
    # The same button again finds nothing left to undo.
    again = await run(application, press(f"u:{event}", OWNER))
    assert texts(again) == [undo_ui.REFUSED["nothing"]]


async def test_keep_changes_nothing(application: App, seeded: Sessions) -> None:
    tid = _pointer(seeded)
    await run(application, press(f"q:rest:{tid}", OWNER))
    calls = await run(application, press("u:keep", OWNER))
    assert texts(calls) == [undo_ui.KEPT]
    assert _workouts(seeded) == 1


@pytest.mark.parametrize("data", ["u:keep", "u:1", "junk"])
async def test_strangers_get_nothing(application: App, seeded: Sessions, data: str) -> None:
    tid = _pointer(seeded)
    await run(application, press(f"q:rest:{tid}", OWNER))
    assert await run(application, command("/undo", STRANGER)) == {}
    event = _last_event(seeded)
    assert await run(application, press(data.replace("1", str(event)), STRANGER)) == {}
    assert _workouts(seeded) == 1
