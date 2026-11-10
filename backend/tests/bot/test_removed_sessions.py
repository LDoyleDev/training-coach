"""Morning buttons naming a session removed since they were sent (ADR-0093 Decided 12): Start
and a pick from a menu left open say so in words; Rest, Push and Do the next one first were
already stale, as they need the pointer."""

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests import factories
from tests.bot.fakes import OWNER, press, run, texts
from training_coach.bot.messages import SESSION_GONE, STALE
from training_coach.db.models import Event, PlanState, SessionTemplate, Workout

Sessions = sessionmaker[Session]
HOW = ["retired", "deleted"]


def _remove_last(sessions: Sessions, how: str) -> tuple[int, int]:
    """Take the cycle's last session out, as the cycle edit does: the pointer and its id."""
    with sessions() as session:
        last = session.scalars(
            select(SessionTemplate).order_by(SessionTemplate.position.desc())
        ).first()
        assert last is not None
        gone = last.id
        if how == "retired":
            factories.retire(session, last, date(2026, 11, 10))
        else:
            session.delete(last)
        pointer = session.scalars(select(PlanState)).one().next_template_id
        assert pointer is not None
        assert pointer != gone
        session.commit()
    return pointer, gone


def _nothing_changed(sessions: Sessions, pointer: int) -> bool:
    with sessions() as session:
        state = session.scalars(select(PlanState)).one()
        queue = session.scalars(select(Event.id).where(Event.kind.startswith("queue."))).first()
        workout = session.scalars(select(Workout.id)).first()
        return (state.next_template_id, queue, workout) == (pointer, None, None)


@pytest.mark.parametrize("how", HOW)
async def test_start_on_a_removed_session_says_it_is_gone(
    application: Application,  # type: ignore[type-arg]
    seeded: Sessions,
    how: str,
) -> None:
    pointer, gone = _remove_last(seeded, how)
    assert texts(await run(application, press(f"q:start:{gone}", OWNER))) == [SESSION_GONE]
    assert _nothing_changed(seeded, pointer)


@pytest.mark.parametrize("how", HOW)
async def test_a_pick_from_a_menu_left_open_says_it_is_gone(
    application: Application,  # type: ignore[type-arg]
    seeded: Sessions,
    how: str,
) -> None:
    pointer, gone = _remove_last(seeded, how)
    pressed = press(f"q:pick:{pointer}:{gone}", OWNER)
    assert texts(await run(application, pressed)) == [SESSION_GONE]
    assert _nothing_changed(seeded, pointer)


@pytest.mark.parametrize("how", HOW)
@pytest.mark.parametrize("action", ["rest", "push", "next"])
async def test_rest_push_and_swap_on_a_removed_session_stay_stale(
    application: Application,  # type: ignore[type-arg]
    seeded: Sessions,
    how: str,
    action: str,
) -> None:
    pointer, gone = _remove_last(seeded, how)
    assert texts(await run(application, press(f"q:{action}:{gone}", OWNER))) == [STALE]
    assert _nothing_changed(seeded, pointer)
