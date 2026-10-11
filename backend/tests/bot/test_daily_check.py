"""The daily check on the morning message (ADR-0053)."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

from tests.bot.fakes import OWNER, SETTINGS, STRANGER, button_data, press, run, texts
from training_coach.bot import daily_check as daily_ui
from training_coach.bot.app import Handlers
from training_coach.db.models import DailyCheck, PlanState, SleepSession
from training_coach.domain.daily_check import Answers, Energy, Sleep, Soreness
from training_coach.domain.queue import local_date
from training_coach.services import daily_check

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]


def _today() -> date:
    return local_date(datetime.now(UTC), SETTINGS.tz)


def _data(day: date, sleep: str = "-", soreness: str = "-", energy: str = "-") -> str:
    return f"d:{day:%Y%m%d}:{sleep}:{soreness}:{energy}"


def _saved(sessions: Sessions) -> list[tuple[date, str, str, str]]:
    with sessions() as session:
        rows = session.scalars(select(DailyCheck))
        return [(r.local_date, r.sleep, r.soreness, r.energy) for r in rows]


def _pointer(sessions: Sessions) -> int:
    with sessions() as session:
        state = session.scalars(select(PlanState)).one()
        assert state.next_template_id is not None
        return state.next_template_id


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("d:20261011:-:-:-", daily_ui.Tap(date(2026, 10, 11), (None, None, None))),
        ("d:20261011:poor:a_lot:low", daily_ui.Tap(date(2026, 10, 11), ("poor", "a_lot", "low"))),
        ("d:20261011:ok:-:normal", daily_ui.Tap(date(2026, 10, 11), ("ok", None, "normal"))),
        ("d:20261011:great:-:-", None),  # not an answer
        ("d:20261011:-:poor:-", None),  # an answer to another question
        ("d:20261332:-:-:-", None),  # no such date
        ("d:2026101" + chr(0xFF11) + ":-:-:-", None),  # a full-width 1
        ("d:20261011:-:-", None),
        ("h:20261011:-:-:-", None),
        (None, None),
    ],
)
def test_parse(data: str | None, expected: daily_ui.Tap | None) -> None:
    assert daily_ui.parse(data) == expected


def test_each_button_carries_the_answers_so_far() -> None:
    day = date(2026, 10, 11)
    rows = daily_ui.rows(daily_ui.Tap(day, ("ok", None, None)))
    assert [b.text for b in rows[0]] == ["Slept well", "✓ Slept OK", "Slept poorly"]
    assert [b.callback_data for b in rows[1]] == [
        _data(day, "ok", s) for s in ("none", "some", "a_lot")
    ]


async def _morning(sessions: Sessions) -> dict[str, object]:
    bot = AsyncMock()
    await Handlers(SETTINGS, sessions).morning(type("Ctx", (), {"bot": bot})())  # type: ignore[arg-type]  # fake context
    kwargs: dict[str, object] = bot.send_message.await_args.kwargs
    return kwargs


async def test_the_morning_message_asks_until_answered(seeded: Sessions) -> None:
    sent = await _morning(seeded)
    assert str(sent["text"]).endswith(daily_ui.ASK)
    data = [b.callback_data for row in sent["reply_markup"].inline_keyboard for b in row]  # type: ignore[attr-defined]  # an InlineKeyboardMarkup
    assert data[0].startswith("q:start:")
    assert _data(_today(), "poor") in data
    with seeded() as session:
        daily_check.save(
            session, _today(), Answers(Sleep.OK, Soreness.NONE, Energy.HIGH), datetime.now(UTC)
        )
        session.commit()
    sent = await _morning(seeded)
    assert daily_ui.ASK not in str(sent["text"])
    data = [b.callback_data for row in sent["reply_markup"].inline_keyboard for b in row]  # type: ignore[attr-defined]
    assert not any(str(d).startswith("d:") for d in data)


async def test_the_morning_message_says_what_the_band_saw(seeded: Sessions) -> None:
    """Last night's sleep from the band helps with the sleep row (ADR-0055)."""
    end = datetime.combine(_today(), datetime.min.time(), tzinfo=SETTINGS.tz) + timedelta(hours=7)
    with seeded() as session:
        session.add(
            SleepSession(
                source="com.mi.health",
                start_at=end - timedelta(hours=7, minutes=30),
                end_at=end,
                local_date=_today(),
                asleep_min=440,
                awake_min=10,
                light_min=250,
                deep_min=90,
                rem_min=100,
            )
        )
        session.commit()
    sent = await _morning(seeded)
    assert str(sent["text"]).endswith(f"{daily_ui.ASK}\nYour band: 7 h 20 min asleep last night.")


async def test_a_tap_marks_it_and_keeps_the_other_buttons(
    application: App, seeded: Sessions
) -> None:
    first = _data(_today(), "ok")
    calls = await run(application, press(first, OWNER, [["q:start:1"], [first]]))
    assert _saved(seeded) == []
    shown = button_data(calls["editMessageReplyMarkup"][0])
    assert shown[0] == "q:start:1"
    assert _data(_today(), "ok", "a_lot") in shown


async def test_the_third_tap_saves_and_says_the_advice(application: App, seeded: Sessions) -> None:
    last = _data(_today(), "ok", "some", "high")
    calls = await run(application, press(last, OWNER, [["q:start:1"], [last]]))
    assert _saved(seeded) == [(_today(), "ok", "some", "high")]
    assert button_data(calls["editMessageReplyMarkup"][0]) == ["q:start:1"]
    (reply,) = texts(calls)
    assert reply.startswith("Slept OK, a bit sore, high energy: go lighter today.")
    assert button_data(calls["sendMessage"][0]) == []


async def test_rest_advice_offers_rest_today(application: App, seeded: Sessions) -> None:
    calls = await run(application, press(_data(_today(), "poor", "a_lot", "normal"), OWNER))
    (reply,) = texts(calls)
    assert "take a rest day" in reply
    assert button_data(calls["sendMessage"][0]) == [f"q:rest:{_pointer(seeded)}"]


async def test_answering_again_replaces_todays_answers(application: App, seeded: Sessions) -> None:
    await run(application, press(_data(_today(), "poor", "a_lot", "low"), OWNER))
    await run(application, press(_data(_today(), "good", "none", "high"), OWNER))
    assert _saved(seeded) == [(_today(), "good", "none", "high")]


async def test_yesterdays_buttons_save_nothing(application: App, seeded: Sessions) -> None:
    old = _data(_today() - timedelta(days=1), "good", "none", "high")
    calls = await run(application, press(old, OWNER, [[old]]))
    assert calls["answerCallbackQuery"][0]["text"] == daily_ui.OLD
    assert _saved(seeded) == []
    assert "sendMessage" not in calls


@pytest.mark.parametrize("data", [_data(date(2026, 10, 11), "good", "none", "high"), "d:junk"])
async def test_strangers_taps_do_nothing(application: App, seeded: Sessions, data: str) -> None:
    assert await run(application, press(data, STRANGER)) == {}
    assert _saved(seeded) == []


async def test_a_malformed_tap_is_only_acknowledged(application: App, seeded: Sessions) -> None:
    calls = await run(application, press("d:junk", OWNER))
    assert set(calls) == {"answerCallbackQuery"}


def test_the_check_goes_above_open_in_app() -> None:
    day = date(2026, 10, 11)
    start = InlineKeyboardButton("Start", callback_data="q:start:1")
    link = InlineKeyboardButton("Open in app", url="https://coach.example.com/session")
    rows = daily_ui.with_check(InlineKeyboardMarkup([[start], [link]]), day).inline_keyboard
    firsts = [row[0].text for row in rows]
    assert firsts == ["Start", "Slept well", "Not sore", "High energy", "Open in app"]
    plain = daily_ui.with_check(InlineKeyboardMarkup([[start]]), day).inline_keyboard
    assert [row[0].text for row in plain] == ["Start", "Slept well", "Not sore", "High energy"]
