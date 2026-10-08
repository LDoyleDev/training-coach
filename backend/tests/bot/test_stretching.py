"""Stretching buttons after a saved resistance log (#98)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, STRANGER, button_data, press, run, text_message, texts
from training_coach.bot import stretching as stretching_ui
from training_coach.db.models import Exercise, SetLog, Workout

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]
LOG = "pull ups 8 8 7, dips 12 11"  # saved against Legs, the first session in the queue


async def _saved(application: App, seeded: Sessions) -> tuple[int, list[str]]:
    drafted = await run(application, text_message(LOG, OWNER))
    token = button_data(drafted["sendMessage"][0])[0].split(":")[2]
    saved = await run(application, press(f"l:save:{token}", OWNER))
    with seeded() as session:
        workout_id = session.scalars(select(Workout.id)).one()
    return workout_id, button_data(saved["sendMessage"][0])


def _stretching(sessions: Sessions) -> list[int]:
    with sessions() as session:
        mobility = session.scalars(select(Exercise.id).where(Exercise.slug == "mobility")).one()
        return list(session.scalars(select(SetLog.value).where(SetLog.exercise_id == mobility)))


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("st:5:10", stretching_ui.Press(5, 10)),
        ("st:done:5:30", stretching_ui.Press(5, 30, done=True)),
        ("st:5:15", None),
        ("st:0:10", None),
        ("st:x:10", None),
        ("st:done:5", None),
        ("st:undo:5:10", None),
        ("q:5:10", None),
        (None, None),
    ],
)
def test_parse(data: str | None, expected: stretching_ui.Press | None) -> None:
    assert stretching_ui.parse(data) == expected


async def test_saving_a_resistance_log_offers_stretching(
    application: App, seeded: Sessions
) -> None:
    workout_id, data = await _saved(application, seeded)
    assert data[-3:] == [f"st:{workout_id}:{m}" for m in (10, 20, 30)]


async def test_a_choice_shows_the_routine_with_done(application: App, seeded: Sessions) -> None:
    workout_id, _ = await _saved(application, seeded)
    calls = await run(application, press(f"st:{workout_id}:10", OWNER))
    (text,) = texts(calls)
    assert text.startswith("Stretching after Legs, about 10 min.")
    assert "\n1. " in text
    assert button_data(calls["sendMessage"][0]) == [f"st:done:{workout_id}:10"]
    assert _stretching(seeded) == []  # nothing logged until Done


async def test_done_logs_once_and_retires_its_button(application: App, seeded: Sessions) -> None:
    workout_id, _ = await _saved(application, seeded)
    calls = await run(application, press(f"st:done:{workout_id}:20", OWNER))
    assert texts(calls) == ["Added 20 min of stretching. Nice work."]
    assert button_data(calls["editMessageReplyMarkup"][0]) == []
    again = await run(application, press(f"st:done:{workout_id}:20", OWNER))
    assert texts(again) == [stretching_ui.ALREADY]
    assert _stretching(seeded) == [20]


@pytest.mark.parametrize("data", ["st:999999:10", "st:done:999999:10"])
async def test_a_missing_workout_says_so(application: App, seeded: Sessions, data: str) -> None:
    assert texts(await run(application, press(data, OWNER))) == [stretching_ui.GONE]


async def test_strangers_presses_do_nothing(application: App, seeded: Sessions) -> None:
    workout_id, _ = await _saved(application, seeded)
    for data in (f"st:{workout_id}:10", f"st:done:{workout_id}:10"):
        assert await run(application, press(data, STRANGER)) == {}
    assert _stretching(seeded) == []


async def test_a_malformed_press_is_only_acknowledged(application: App, seeded: Sessions) -> None:
    calls = await run(application, press("st:junk", OWNER))
    assert set(calls) == {"answerCallbackQuery"}
    with seeded() as session:
        assert session.scalar(select(func.count()).select_from(SetLog)) == 0
