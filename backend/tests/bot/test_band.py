"""Band workouts offered in Telegram (ADR-0055): Count it / Not this one, owner-only."""

from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, SETTINGS, STRANGER, press, run, texts
from training_coach.bot import band as band_ui
from training_coach.db.models import ImportedWorkout, UserSettings, Workout
from training_coach.domain.queue import local_date

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]


def _walk(sessions: Sessions, days_ago: int = 0, hour: int = 7) -> int:
    on = local_date(datetime.now(UTC), SETTINGS.tz) - timedelta(days=days_ago)
    start = datetime.combine(on, time(hour, 0), tzinfo=SETTINGS.tz).astimezone(UTC)
    with sessions() as session:
        row = ImportedWorkout(
            source="com.mi.health",
            start_at=start,
            end_at=start + timedelta(minutes=46),
            local_date=on,
            exercise_type=79,
            activity="walk",
            minutes=46,
            zone1_min=8,
            zone2_min=38,
            zone3_min=0,
            zone4_min=0,
            zone5_min=0,
        )
        session.add(row)
        session.commit()
        return row.id


def _workouts(sessions: Sessions) -> int:
    with sessions() as session:
        return len(list(session.scalars(select(Workout.id))))


@pytest.mark.parametrize(
    ("data", "expected"),
    [("bc:12", ("bc", 12)), ("bx:3", ("bx", 3)), ("bc:0", None), ("bc:x", None), (None, None)],
)
def test_parse(data: str | None, expected: tuple[str, int] | None) -> None:
    assert band_ui.parse(data) == expected


async def test_each_new_offer_is_sent_once(seeded: Sessions) -> None:
    walk = _walk(seeded)
    sent: list[tuple[int, str, Any]] = []

    async def send(_bot: object, chat: int, text: str, **kwargs: Any) -> bool:
        sent.append((chat, text, kwargs["reply_markup"]))
        return True

    handlers = band_ui.BandHandlers(SETTINGS, seeded, send)
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    await handlers.announce(context)  # type: ignore[arg-type]  # fake context
    await handlers.announce(context)  # type: ignore[arg-type]
    ((chat, text, markup),) = sent
    assert (chat, text) == (OWNER, "Walk, 46 min, 38 in zone 2 - count it?")
    buttons = [b.callback_data for b in markup.inline_keyboard[0]]
    assert buttons == [f"bc:{walk}", f"bx:{walk}"]


async def test_a_failed_send_is_tried_again_next_run(seeded: Sessions) -> None:
    # Review of #226: offers were marked sent before sending, so a failed send lost them.
    walk = _walk(seeded)
    results = [False, True]
    sent: list[str] = []

    async def send(_bot: object, _chat: int, text: str, **_kwargs: Any) -> bool:
        sent.append(text)
        return results.pop(0)

    handlers = band_ui.BandHandlers(SETTINGS, seeded, send)
    context = SimpleNamespace(bot=None)
    await handlers.announce(context)  # type: ignore[arg-type]  # fake context
    with seeded() as session:
        assert session.get(ImportedWorkout, walk).announced_at is None  # type: ignore[union-attr]
    await handlers.announce(context)  # type: ignore[arg-type]
    await handlers.announce(context)  # type: ignore[arg-type]
    assert len(sent) == 2  # failed, then sent; not again after that
    with seeded() as session:
        assert session.get(ImportedWorkout, walk).announced_at is not None  # type: ignore[union-attr]


async def test_a_backlog_is_sent_a_few_at_a_time_and_only_recent(seeded: Sessions) -> None:
    # Review of #226: the first run after a gap could send a week of offers at once.
    _walk(seeded, days_ago=4)  # stays on Today in the app, never sent to Telegram
    for hour in range(6, 6 + band_ui.band_cardio.ANNOUNCE_AT_ONCE + 1):
        _walk(seeded, days_ago=1, hour=hour)
    send = AsyncMock(return_value=True)
    handlers = band_ui.BandHandlers(SETTINGS, seeded, send)
    await handlers.announce(SimpleNamespace(bot=None))  # type: ignore[arg-type]  # fake context
    assert send.await_count == band_ui.band_cardio.ANNOUNCE_AT_ONCE
    await handlers.announce(SimpleNamespace(bot=None))  # type: ignore[arg-type]
    await handlers.announce(SimpleNamespace(bot=None))  # type: ignore[arg-type]
    assert send.await_count == band_ui.band_cardio.ANNOUNCE_AT_ONCE + 1


async def test_nothing_is_sent_while_paused(seeded: Sessions) -> None:
    _walk(seeded)
    with seeded() as session:
        session.scalars(select(UserSettings)).one().paused = True
        session.commit()
    send = AsyncMock()
    await band_ui.BandHandlers(SETTINGS, seeded, send).announce(SimpleNamespace(bot=None))  # type: ignore[arg-type]
    send.assert_not_awaited()


async def test_count_it(application: App, seeded: Sessions) -> None:
    walk = _walk(seeded)
    calls = await run(application, press(f"bc:{walk}", OWNER))
    (reply,) = texts(calls)
    assert reply.startswith("Counted. Zone 2 this week: 38 of 180-200 min.")
    assert _workouts(seeded) == 1
    again = await run(application, press(f"bc:{walk}", OWNER))
    assert texts(again)[0].startswith("Counted.")
    assert _workouts(seeded) == 1


async def test_not_this_one(application: App, seeded: Sessions) -> None:
    walk = _walk(seeded)
    calls = await run(application, press(f"bx:{walk}", OWNER))
    assert texts(calls) == [band_ui.SKIPPED]
    later = await run(application, press(f"bc:{walk}", OWNER))
    assert texts(later) == [band_ui.GONE]
    assert _workouts(seeded) == 0


@pytest.mark.parametrize("action", ["bc", "bx"])
async def test_strangers_get_nothing(application: App, seeded: Sessions, action: str) -> None:
    walk = _walk(seeded)
    assert await run(application, press(f"{action}:{walk}", STRANGER)) == {}
    assert _workouts(seeded) == 0
    with seeded() as session:
        assert session.get_one(ImportedWorkout, walk).status == "new"


def test_counted_text_without_a_target() -> None:
    week = band_ui.cardio.Week(zone2=40, moderate=0, zone2_target=None)
    assert band_ui.counted_text(week, planned=True) == (
        "Counted, and today's session is done. Zone 2 this week: 40 min. /undo takes it back."
    )
