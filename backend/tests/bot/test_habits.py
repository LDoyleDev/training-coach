"""Habit buttons and /habits (#91)."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, SETTINGS, STRANGER, button_data, command, press, run, texts
from training_coach.bot import habits as habits_ui
from training_coach.db.models import HabitCheck
from training_coach.domain.habits import Habit
from training_coach.domain.queue import local_date

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]


def _today() -> date:
    return local_date(datetime.now(UTC), SETTINGS.tz)


def _data(day: date, habit: str) -> str:
    return f"h:{day:%Y%m%d}:{habit}"


def _checks(sessions: Sessions) -> list[tuple[date, str]]:
    with sessions() as session:
        rows = session.execute(select(HabitCheck.local_date, HabitCheck.habit))
        return [(day, habit) for day, habit in rows]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("h:20261007:protein", (date(2026, 10, 7), Habit.PROTEIN)),
        ("h:20261007:wind_down", (date(2026, 10, 7), Habit.WIND_DOWN)),
        ("h:20261332:protein", None),  # no such date
        ("h:2026107:protein", None),
        ("h:2026100" + chr(0xFF17) + ":protein", None),  # a full-width 7
        ("h:20261007:caffeine", None),
        ("h:20261007", None),
        ("h:20261007:protein:x", None),
        ("q:20261007:protein", None),
        (None, None),
    ],
)
def test_parse(data: str | None, expected: tuple[date, Habit] | None) -> None:
    assert habits_ui.parse(data) == expected


def test_rows_mark_what_is_ticked() -> None:
    labels = [row[0].text for row in habits_ui.rows(date(2026, 10, 7), frozenset({Habit.PROTEIN}))]
    assert labels == ["Morning light", "✓ Protein target", "Wind-down"]


@pytest.mark.parametrize(("sender", "replies"), [(OWNER, 1), (STRANGER, 0)])
async def test_habits_command_is_owner_only(application: App, sender: int, replies: int) -> None:
    calls = await run(application, command("/habits", sender))
    assert len(texts(calls)) == replies
    if replies:
        assert texts(calls)[0].startswith(f"Habits for {_today():%a %d %b}")
        assert button_data(calls["sendMessage"][0]) == [
            _data(_today(), h) for h in ("morning_light", "protein", "wind_down")
        ]


async def test_a_tap_ticks_and_shows_it(application: App, seeded: Sessions) -> None:
    calls = await run(application, press(_data(_today(), "protein"), OWNER))
    assert _checks(seeded) == [(_today(), "protein")]
    (edit,) = calls["editMessageReplyMarkup"]
    labels = [b["text"] for row in json.loads(edit["reply_markup"])["inline_keyboard"] for b in row]
    assert "✓ Protein target" in labels


async def test_a_second_tap_unticks(application: App, seeded: Sessions) -> None:
    await run(application, press(_data(_today(), "protein"), OWNER))
    await run(application, press(_data(_today(), "protein"), OWNER))
    assert _checks(seeded) == []


async def test_yesterdays_button_ticks_yesterday(application: App, seeded: Sessions) -> None:
    yesterday = _today() - timedelta(days=1)
    await run(application, press(_data(yesterday, "wind_down"), OWNER))
    assert _checks(seeded) == [(yesterday, "wind_down")]


async def test_an_old_button_says_it_is_too_late(application: App, seeded: Sessions) -> None:
    calls = await run(application, press(_data(_today() - timedelta(days=3), "protein"), OWNER))
    assert calls["answerCallbackQuery"][0]["text"] == habits_ui.TOO_LATE
    assert "editMessageReplyMarkup" not in calls
    assert _checks(seeded) == []


async def test_habit_buttons_keep_the_morning_buttons(application: App, seeded: Sessions) -> None:
    today = _data(_today(), "protein")
    calls = await run(application, press(today, OWNER, [["q:start:1", "q:rest:1"], [today]]))
    assert button_data(calls["editMessageReplyMarkup"][0]) == [
        "q:start:1",
        "q:rest:1",
        *(_data(_today(), h) for h in ("morning_light", "protein", "wind_down")),
    ]


@pytest.mark.parametrize("data", [_data(date(2026, 10, 7), "protein"), "h:junk"])
async def test_strangers_taps_do_nothing(application: App, seeded: Sessions, data: str) -> None:
    assert await run(application, press(data, STRANGER)) == {}
    assert _checks(seeded) == []


async def test_a_malformed_tap_is_only_acknowledged(application: App, seeded: Sessions) -> None:
    calls = await run(application, press("h:junk", OWNER))
    assert set(calls) == {"answerCallbackQuery"}
