from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, STRANGER, button_data, press, run, text_message, texts
from training_coach.bot import logging_flow
from training_coach.bot.messages import (
    LOG_CANCELLED,
    LOG_EDIT,
    LOG_EXPIRED,
    LOG_SAVED_BEFORE,
    LOG_STALE,
    log_text,
)
from training_coach.db.models import PlanState, SessionTemplate, SetLog, Workout
from training_coach.domain.enums import ExerciseKind, Side
from training_coach.domain.parser import Entry
from training_coach.services import queue_actions
from training_coach.services.workout_log import Draft

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]
LOG = "pull ups 8 8 7, dips 12 11"


def _count(sessions: Sessions, model: type) -> int:
    with sessions() as session:
        return session.scalar(select(func.count()).select_from(model)) or 0


def _pointer(sessions: Sessions) -> int | None:
    with sessions() as session:
        state = session.get(PlanState, 1)
        assert state is not None
        return state.next_template_id


def _token(calls: dict[str, list[dict[str, str]]]) -> str:
    data = button_data(calls["sendMessage"][0])
    assert [d.split(":")[1] for d in data] == ["save", "edit", "cancel"]
    return data[0].split(":")[2]


# ------------------------------------------------------------------ parsing and text


@pytest.mark.parametrize(
    ("data", "ok"),
    [
        ("l:save:" + "a" * 32, True),
        ("l:cancel:" + "0f" * 16, True),
        ("l:save:" + "a" * 31, False),
        ("l:save:" + "A" * 32, False),
        ("l:dance:" + "a" * 32, False),
        ("q:save:" + "a" * 32, False),
        (None, False),
    ],
)
def test_parse(data: str | None, ok: bool) -> None:
    assert (logging_flow.parse(data) is not None) is ok


def test_log_text_shows_sides_units_and_problems() -> None:
    draft = Draft(
        token="t" * 32,
        on=date(2026, 10, 6),
        template_id=1,
        session_name="Legs",
        entries=(
            Entry(
                "squat",
                ((1, Side.LEFT, 10), (1, Side.RIGHT, 10), (2, Side.LEFT, 9), (2, Side.RIGHT, 9)),
            ),
            Entry("lunge", ((1, Side.LEFT, 8), (1, Side.RIGHT, 7))),
            Entry("plank", ((1, Side.BOTH, 45),)),
        ),
        problems=("I don't know the exercise 'burpees'",),
    )
    names = {
        "squat": ("Split squat", ExerciseKind.REPS),
        "lunge": ("Lunge", ExerciseKind.REPS),
        "plank": ("Plank", ExerciseKind.SECONDS),
    }
    assert log_text(draft, names).splitlines() == [
        "Log for Legs:",
        "",
        "- Split squat: 10 / 9 each side",
        "- Lunge: left 8, right 7",
        "- Plank: 45s",
        "",
        "Not understood:",
        "- I don't know the exercise 'burpees'",
        "",
        "Save the part I understood?",
    ]


# ------------------------------------------------------------------ through the bot


async def test_a_log_is_shown_before_anything_is_saved(application: App, seeded: Sessions) -> None:
    calls = await run(application, text_message(LOG, OWNER))
    (reply,) = texts(calls)
    assert reply.startswith("Log for ")
    assert "- Pull-up: 8 / 8 / 7" in reply
    _token(calls)
    assert _count(seeded, Workout) == 0  # ADR-0007: nothing saved without Save


async def test_strangers_logs_and_presses_do_nothing(application: App, seeded: Sessions) -> None:
    assert await run(application, text_message(LOG, STRANGER)) == {}
    token = _token(await run(application, text_message(LOG, OWNER)))
    for action in ("save", "edit", "cancel"):
        assert await run(application, press(f"l:{action}:{token}", STRANGER)) == {}
    assert _count(seeded, Workout) == 0


async def test_save_writes_the_workout_and_moves_the_queue(
    application: App, seeded: Sessions
) -> None:
    first = _pointer(seeded)
    token = _token(await run(application, text_message(LOG, OWNER)))
    calls = await run(application, press(f"l:save:{token}", OWNER))
    (reply,) = texts(calls)
    assert reply.startswith("Saved ")
    assert "Next up: " in reply
    assert button_data(calls["editMessageReplyMarkup"][0]) == []  # buttons retired
    assert _count(seeded, Workout) == 1
    assert _count(seeded, SetLog) == 5
    assert _pointer(seeded) != first


async def test_a_second_save_tap_changes_nothing(application: App, seeded: Sessions) -> None:
    token = _token(await run(application, text_message(LOG, OWNER)))
    await run(application, press(f"l:save:{token}", OWNER))
    pointer = _pointer(seeded)
    again = texts(await run(application, press(f"l:save:{token}", OWNER)))
    assert again == [LOG_SAVED_BEFORE]  # not "expired": that would invite a duplicate
    assert _count(seeded, Workout) == 1
    assert _pointer(seeded) == pointer


async def test_a_draft_overtaken_by_a_swap_is_stale(application: App, seeded: Sessions) -> None:
    token = _token(await run(application, text_message(LOG, OWNER)))
    with seeded() as session:
        state = session.get(PlanState, 1)
        assert state is not None
        assert state.next_template_id is not None
        queue_actions.swap_next(session, state.next_template_id)
        session.commit()
    assert texts(await run(application, press(f"l:save:{token}", OWNER))) == [LOG_STALE]
    assert _count(seeded, Workout) == 0


@pytest.mark.parametrize(("action", "reply"), [("cancel", LOG_CANCELLED), ("edit", LOG_EDIT)])
async def test_cancel_and_edit_discard_the_draft(
    application: App, seeded: Sessions, action: str, reply: str
) -> None:
    token = _token(await run(application, text_message(LOG, OWNER)))
    assert texts(await run(application, press(f"l:{action}:{token}", OWNER))) == [reply]
    assert texts(await run(application, press(f"l:save:{token}", OWNER))) == [LOG_EXPIRED]
    assert _count(seeded, Workout) == 0


async def test_an_unknown_token_has_expired(application: App, seeded: Sessions) -> None:
    assert texts(await run(application, press("l:save:" + "b" * 32, OWNER))) == [LOG_EXPIRED]


async def test_a_log_with_nothing_readable_gets_no_buttons(application: App) -> None:
    calls = await run(application, text_message("burpees 10, star jumps 20", OWNER))
    (reply,) = texts(calls)
    assert reply.startswith("I couldn't read that log:")
    assert button_data(calls["sendMessage"][0]) == []


async def test_only_the_latest_drafts_are_kept(application: App, seeded: Sessions) -> None:
    oldest = _token(await run(application, text_message(LOG, OWNER)))
    for _ in range(logging_flow.MAX_DRAFTS):
        await run(application, text_message(LOG, OWNER))
    assert texts(await run(application, press(f"l:save:{oldest}", OWNER))) == [LOG_EXPIRED]


async def test_a_pending_settings_question_wins_over_logging(
    application: App, seeded: Sessions
) -> None:
    await run(application, press("s:ask-morning", OWNER))
    reply = texts(await run(application, text_message("06:45", OWNER)))
    assert "Morning message: 06:45" in reply[0]
    assert _count(seeded, Workout) == 0


async def test_logging_an_extra_session_after_the_planned_one(
    application: App, seeded: Sessions
) -> None:
    token = _token(await run(application, text_message(LOG, OWNER)))
    await run(application, press(f"l:save:{token}", OWNER))
    pointer = _pointer(seeded)
    calls = await run(application, text_message("dips 10", OWNER))
    assert texts(calls)[0].startswith("Log for Extra session:")
    await run(application, press(f"l:save:{_token(calls)}", OWNER))
    with seeded() as session:
        templates = [w.template_id for w in session.scalars(select(Workout).order_by(Workout.id))]
        assert templates[1] is None
        assert session.get(SessionTemplate, pointer) is not None
    assert _pointer(seeded) == pointer  # extras never move the queue
