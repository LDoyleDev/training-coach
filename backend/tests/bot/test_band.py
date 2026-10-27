"""Band workouts offered in Telegram (ADR-0055): Count it / Not this one, owner-only."""

from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import time_machine
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, SETTINGS, STRANGER, press, run, texts
from training_coach.bot import band as band_ui
from training_coach.db.models import ImportedWorkout, UserSettings, Workout
from training_coach.domain.band_watch import Feed, FeedNotices, Notice
from training_coach.domain.queue import local_date
from training_coach.services import ingest_keys

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
    # All 46 minutes count; 38 of them were in zone 2 (ADR-0079).
    assert reply.startswith("Counted. Last 7 days: cardio 46 of 75-115 min, zone 2 38 of 45-75.")
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
        "Counted, and today's session is done. Last 7 days: cardio 0 min, zone 2 40. "
        "/undo takes it back."
    )


def _locked(*_args: object, **_kwargs: object) -> None:
    raise OperationalError("UPDATE", {}, Exception("database is locked"))


async def test_an_offer_sent_but_not_marked_stops_the_run(
    seeded: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Review of #226: a failed mark escaped the job and skipped the rest of the batch.
    _walk(seeded, hour=6)
    _walk(seeded, hour=7)
    monkeypatch.setattr(band_ui.band_cardio, "announced", _locked)
    send = AsyncMock(return_value=True)
    await band_ui.BandHandlers(SETTINGS, seeded, send).announce(SimpleNamespace(bot=None))  # type: ignore[arg-type]  # fake context
    assert send.await_count == 1  # stopped after the unmarked one, so nothing goes twice


@pytest.mark.parametrize("action", ["bc", "bx"])
async def test_a_failed_save_keeps_the_buttons_and_says_so(
    application: App, seeded: Sessions, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    # Review of #226: the buttons went before the save, so a failure left a dead end.
    walk = _walk(seeded)
    monkeypatch.setattr(band_ui.band_cardio, "count", _locked)
    monkeypatch.setattr(band_ui.band_cardio, "dismiss", _locked)
    calls = await run(application, press(f"{action}:{walk}", OWNER))
    assert texts(calls) == [band_ui.FAILED]
    assert "editMessageReplyMarkup" not in calls
    assert _workouts(seeded) == 0


# ------------------------------------------------------------- band data stopping (ADR-0055)

MADE = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)  # 10:00 in Berlin
HOUR = timedelta(hours=1)


def _secret(sessions: Sessions, at: datetime = MADE) -> None:
    with sessions() as session:
        ingest_keys.make(session, at)
        session.commit()


def _sync(sessions: Sessions, at: datetime, took: bool = True, app: str | None = None) -> None:
    with sessions() as session:
        ingest_keys.received(session, at, took, app_version=app)
        session.commit()


async def _watch(handlers: band_ui.BandHandlers, at: datetime) -> None:
    with time_machine.travel(at, tick=False):
        await handlers.watch(SimpleNamespace(bot=None))  # type: ignore[arg-type]  # fake context


def _sent(send: AsyncMock) -> list[str]:
    return [call.args[2] for call in send.await_args_list]


async def test_a_day_without_band_data_is_told_once_then_its_return(seeded: Sessions) -> None:
    _secret(seeded)
    _sync(seeded, MADE)
    send = AsyncMock(return_value=True)
    handlers = band_ui.BandHandlers(SETTINGS, seeded, send)
    await _watch(handlers, MADE + 23 * HOUR)
    await _watch(handlers, MADE + 25 * HOUR)
    await _watch(handlers, MADE + 26 * HOUR)
    assert _sent(send) == [band_ui.NOTICES[Notice.QUIET]]
    assert send.await_args_list[0].args[1] == OWNER
    _sync(seeded, MADE + 27 * HOUR)
    await _watch(handlers, MADE + 28 * HOUR)
    await _watch(handlers, MADE + 29 * HOUR)
    assert _sent(send)[1:] == ["Band data is arriving again."]
    await _watch(handlers, MADE + 52 * HOUR)  # a second gap is told again
    assert _sent(send)[2:] == [band_ui.NOTICES[Notice.QUIET]]


async def test_empty_syncs_get_the_empty_message(seeded: Sessions) -> None:
    _secret(seeded)
    _sync(seeded, MADE)
    _sync(seeded, MADE + 20 * HOUR, took=False)
    send = AsyncMock(return_value=True)
    await _watch(band_ui.BandHandlers(SETTINGS, seeded, send), MADE + 25 * HOUR)
    assert _sent(send) == [
        "The Coach reader is syncing, but nothing new has come from the band for a day. Open Mi "
        "Fitness to sync the band, and check that Mi Fitness still shares with Health Connect."
    ]


@pytest.mark.parametrize(
    ("app", "named"), [("tc-reader/0.0.5", "The Coach reader"), ("1.9.31", "HC Webhook")]
)
async def test_the_alert_names_the_app_that_sends(seeded: Sessions, app: str, named: str) -> None:
    # Step 4 of docs/specs/android-reader.md: the app named from its version string.
    _secret(seeded)
    _sync(seeded, MADE, app=app)
    _sync(seeded, MADE + 20 * HOUR, took=False, app=app)
    send = AsyncMock(return_value=True)
    await _watch(band_ui.BandHandlers(SETTINGS, seeded, send), MADE + 25 * HOUR)
    assert _sent(send)[0].startswith(f"{named} is syncing")


async def test_a_remade_secret_forgets_hc_webhook_until_a_versioned_sync(
    seeded: Sessions,
) -> None:
    # Review of #376: a new secret clears app_version, so the reader's wording comes back, as
    # meant: the runbook sets a phone up again with the reader. A versioned sync corrects it.
    _secret(seeded)
    _sync(seeded, MADE - 2 * HOUR, app="1.9.31")
    _secret(seeded, MADE - HOUR)
    _sync(seeded, MADE)
    _sync(seeded, MADE + 20 * HOUR, took=False)
    send = AsyncMock(return_value=True)
    await _watch(band_ui.BandHandlers(SETTINGS, seeded, send), MADE + 25 * HOUR)
    assert _sent(send)[0].startswith("The Coach reader is syncing")
    with seeded() as session:
        assert ingest_keys.status(session).app_version is None


def test_hc_webhook_is_told_apart_by_its_version() -> None:
    assert band_ui.webhook("1.9.22")
    assert not band_ui.webhook("tc-reader/0.0.6")
    assert not band_ui.webhook(None)  # no sync yet: the reader replaced HC Webhook


async def test_no_band_import_means_no_alert(seeded: Sessions) -> None:
    send = AsyncMock(return_value=True)
    await _watch(band_ui.BandHandlers(SETTINGS, seeded, send), MADE + 50 * HOUR)
    send.assert_not_awaited()


async def test_the_alert_waits_for_the_day_and_not_while_paused(seeded: Sessions) -> None:
    _secret(seeded)
    send = AsyncMock(return_value=True)
    handlers = band_ui.BandHandlers(SETTINGS, seeded, send)
    night = datetime(2026, 10, 14, 1, 0, tzinfo=UTC)  # 03:00 in Berlin
    await _watch(handlers, night)
    send.assert_not_awaited()
    with seeded() as session:
        session.scalars(select(UserSettings)).one().paused = True
        session.commit()
    await _watch(handlers, night + 8 * HOUR)
    send.assert_not_awaited()
    with seeded() as session:
        session.scalars(select(UserSettings)).one().paused = False
        session.commit()
    await _watch(handlers, night + 8 * HOUR)
    assert _sent(send) == [band_ui.NOTICES[Notice.QUIET]]


async def test_a_failed_alert_is_tried_again_next_run(seeded: Sessions) -> None:
    _secret(seeded)
    send = AsyncMock(side_effect=[False, True, True])
    handlers = band_ui.BandHandlers(SETTINGS, seeded, send)
    await _watch(handlers, MADE + 25 * HOUR)
    await _watch(handlers, MADE + 26 * HOUR)
    await _watch(handlers, MADE + 27 * HOUR)
    assert send.await_count == 2


async def test_the_alert_links_to_account_when_there_is_an_address(seeded: Sessions) -> None:
    _secret(seeded)
    settings = SETTINGS.model_copy(update={"public_url": "https://coach.example.org"})
    send = AsyncMock(return_value=True)
    await _watch(band_ui.BandHandlers(settings, seeded, send), MADE + 25 * HOUR)
    (button,) = send.await_args_list[0].kwargs["reply_markup"].inline_keyboard[0]
    assert button.url == "https://coach.example.org/account"


async def test_a_database_error_sends_nothing(seeded: Sessions) -> None:
    _secret(seeded)
    send = AsyncMock(return_value=True)
    handlers = band_ui.BandHandlers(SETTINGS, seeded, send)
    with patch.object(
        band_ui.ingest_keys, "watch", side_effect=OperationalError("locked", None, Exception())
    ):
        await _watch(handlers, MADE + 25 * HOUR)
    send.assert_not_awaited()


def test_the_watch_runs_hourly(application: App) -> None:
    assert application.job_queue is not None
    (job,) = application.job_queue.get_jobs_by_name(band_ui.WATCH_JOB)
    assert job.job.trigger.interval == band_ui.WATCH_EVERY


def _kinds(sessions: Sessions, at: datetime, *kinds: str) -> None:
    with sessions() as session:
        ingest_keys.received(session, at, True, kinds)
        session.commit()


async def test_kinds_that_stop_while_steps_flow_are_told_then_their_return(
    seeded: Sessions,
) -> None:
    _secret(seeded)
    for hours in (0, 24, 48):
        _kinds(seeded, MADE + hours * HOUR, "steps")
    settings = SETTINGS.model_copy(update={"public_url": "https://coach.example.org"})
    send = AsyncMock(return_value=True)
    handlers = band_ui.BandHandlers(settings, seeded, send)
    await _watch(handlers, MADE + 47 * HOUR)
    await _watch(handlers, MADE + 49 * HOUR)
    await _watch(handlers, MADE + 50 * HOUR)
    assert _sent(send) == [
        "No sleep or heart-rate data has come from the band for two days, though other band "
        "data has. In the Coach reader, tap Sync now: it says what it sent of each kind, or "
        "why it couldn't."
    ]
    assert send.await_args_list[0].kwargs["reply_markup"] is not None
    _kinds(seeded, MADE + 51 * HOUR, "steps", "sleep", "heart_rate")
    await _watch(handlers, MADE + 52 * HOUR)
    assert _sent(send)[1:] == ["Sleep and heart-rate data are arriving again."]
    assert send.await_args_list[1].kwargs["reply_markup"] is None


def test_the_kinds_message_names_each_one() -> None:
    every = FeedNotices((Feed.STEPS, Feed.SLEEP, Feed.HEART_RATE), (Feed.STEPS,))
    assert band_ui.feeds_text(every, from_webhook=True).split("\n\n") == [
        "No step, sleep or heart-rate data has come from the band for two days, though other "
        "band data has. In HC Webhook, check Data Types, and look under Sync Now for an error.",
        "Step data is arriving again.",
    ]


async def test_a_failed_kinds_alert_is_tried_again_next_run(seeded: Sessions) -> None:
    _secret(seeded)
    _kinds(seeded, MADE + 48 * HOUR, "steps", "heart_rate")
    send = AsyncMock(side_effect=[False, True, True])
    handlers = band_ui.BandHandlers(SETTINGS, seeded, send)
    await _watch(handlers, MADE + 49 * HOUR)
    await _watch(handlers, MADE + 50 * HOUR)
    await _watch(handlers, MADE + 51 * HOUR)
    assert send.await_count == 2
