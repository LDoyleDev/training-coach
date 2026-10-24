"""Logs a connected AI proposed, in Telegram (ADR-0058): Save / Discard, owner-only."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests import oauth_flow as flow
from tests.bot.fakes import OWNER, SETTINGS, STRANGER, button_data, press, run, texts
from training_coach.bot import proposals as proposals_ui
from training_coach.bot.app import ANNOUNCE
from training_coach.db.models import HabitCheck, LogProposal, McpConnection, Measurement, Workout
from training_coach.domain.queue import local_date
from training_coach.services import proposals, workout_log

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]
TODAY = local_date(datetime.now(UTC), SETTINGS.tz)


def _propose(seeded: Sessions, engine: Engine, **arguments: Any) -> str:
    """A proposal from a fresh connection; its token."""
    flow.mint(engine, ["log:propose"])
    with seeded() as session:
        connection = session.scalars(select(McpConnection.id).order_by(McpConnection.id.desc()))
        found = proposals.propose(
            session,
            connection.first() or 0,
            arguments or {"kind": "habits", "habits": ["protein"]},
            SETTINGS.tz,
            datetime.now(UTC),
        )
        assert isinstance(found, proposals.Proposed), found
        session.commit()
        return session.get_one(LogProposal, found.id).token


def _status(seeded: Sessions, token: str) -> str:
    with seeded() as session:
        return session.scalars(select(LogProposal.status).where(LogProposal.token == token)).one()


def _ticks(seeded: Sessions) -> list[str]:
    with seeded() as session:
        return list(session.scalars(select(HabitCheck.habit)))


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("lp:save:" + "ab" * 16, proposals_ui.Press("save", "ab" * 16)),
        ("lp:discard:" + "ab" * 16, proposals_ui.Press("discard", "ab" * 16)),
        ("lp:zone2:" + "ab" * 16, proposals_ui.Press("zone2", "ab" * 16)),
        ("lp:moderate:" + "ab" * 16, proposals_ui.Press("moderate", "ab" * 16)),
        ("lp:moderate-cardio:" + "ab" * 16, None),
        ("lp:edit:" + "ab" * 16, None),
        ("lp:save:" + "AB" * 16, None),
        ("lp:save:abc", None),
        ("l:save:" + "ab" * 16, None),
        (None, None),
    ],
)
def test_parse(data: str | None, expected: proposals_ui.Press | None) -> None:
    assert proposals_ui.parse(data) == expected


async def test_each_proposal_is_sent_once_naming_the_app(seeded: Sessions, engine: Engine) -> None:
    token = _propose(seeded, engine)
    sent: list[tuple[int, str, Any]] = []

    async def send(_bot: object, chat: int, text: str, **kwargs: Any) -> str:
        sent.append((chat, text, kwargs["reply_markup"]))
        return proposals_ui.SENT

    handlers = proposals_ui.ProposalHandlers(SETTINGS, seeded, send)
    await handlers.announce(None)  # type: ignore[arg-type]  # the fake send needs no bot
    await handlers.job(SimpleNamespace(bot=None))  # type: ignore[arg-type]  # fake context
    ((chat, text, markup),) = sent
    assert chat == OWNER
    assert text == (
        f"From “Claude”: Done on {TODAY:%a %d %b}: Protein target\n\n"
        "Nothing is saved until you tap Save."
    )
    buttons = [b.callback_data for b in markup.inline_keyboard[0]]
    assert buttons == [f"lp:save:{token}", f"lp:discard:{token}"]


async def test_a_failed_send_is_tried_again(seeded: Sessions, engine: Engine) -> None:
    _propose(seeded, engine)
    send = AsyncMock(side_effect=[proposals_ui.UNREACHABLE, proposals_ui.SENT])
    handlers = proposals_ui.ProposalHandlers(SETTINGS, seeded, send)
    for _ in range(3):
        await handlers.announce(None)  # type: ignore[arg-type]
    assert send.await_count == 2  # failed, then sent; not again after that


def _locked(*_args: object, **_kwargs: object) -> None:
    raise OperationalError("UPDATE", {}, Exception("database is locked"))


async def test_a_proposal_sent_but_not_marked_stops_the_run(
    seeded: Sessions, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _propose(seeded, engine)
    _propose(seeded, engine)
    monkeypatch.setattr(proposals_ui.proposals, "announced", _locked)
    send = AsyncMock(return_value=proposals_ui.SENT)
    await proposals_ui.ProposalHandlers(SETTINGS, seeded, send).announce(None)  # type: ignore[arg-type]
    assert send.await_count == 1  # stopped, so nothing goes twice


async def test_an_unreadable_database_sends_nothing(
    seeded: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(proposals_ui.proposals, "pending", _locked)
    send = AsyncMock(return_value=proposals_ui.SENT)
    await proposals_ui.ProposalHandlers(SETTINGS, seeded, send).announce(None)  # type: ignore[arg-type]
    send.assert_not_awaited()


async def test_save(application: App, seeded: Sessions, engine: Engine) -> None:
    token = _propose(seeded, engine)
    calls = await run(application, press(f"lp:save:{token}", OWNER))
    assert texts(calls) == [f"Saved: Done on {TODAY:%a %d %b}: Protein target."]
    assert "editMessageReplyMarkup" in calls  # the buttons go once it's saved
    assert _ticks(seeded) == ["protein"]
    again = await run(application, press(f"lp:save:{token}", OWNER))
    assert texts(again) == ["Already saved."]
    assert _ticks(seeded) == ["protein"]


async def test_a_saved_workout_offers_undo(
    application: App, seeded: Sessions, engine: Engine
) -> None:
    token = _propose(
        seeded, engine, kind="cardio", cardio="zone2", minutes=40, day=TODAY.isoformat()
    )
    (reply,) = texts(await run(application, press(f"lp:zone2:{token}", OWNER)))
    assert reply.endswith("/undo takes it back.")


RIDE = {"kind": "cardio", "cardio": "zone2", "minutes": 40, "activity": "bike"}


async def test_a_cardio_proposal_has_a_button_per_kind_and_names_the_suggestion(
    seeded: Sessions, engine: Engine
) -> None:
    """Owner, 2026-10-24: the app observes and suggests; the person picks."""
    token = _propose(seeded, engine, **RIDE, avg_hr=139)
    send = AsyncMock(return_value=proposals_ui.SENT)
    await proposals_ui.ProposalHandlers(SETTINGS, seeded, send).announce(None)  # type: ignore[arg-type]
    text, markup = send.await_args.args[2], send.await_args.kwargs["reply_markup"]
    assert text == (
        f"From “Claude”: Cardio, 40 min (bike), HR 139 avg, on {TODAY:%a %d %b}\n"
        "Average 139 bpm is in your zone 2 (138-150 bpm), so zone 2 is suggested. You pick.\n\n"
        "Nothing is saved until you tap Zone 2 or Moderate."
    )
    assert [(b.text, b.callback_data) for b in markup.inline_keyboard[0]] == [
        ("Zone 2", f"lp:zone2:{token}"),
        ("Moderate", f"lp:moderate:{token}"),
        ("Discard", f"lp:discard:{token}"),
    ]


async def test_without_a_suggestion_it_says_the_person_picks(
    seeded: Sessions, engine: Engine
) -> None:
    _propose(seeded, engine, kind="cardio", minutes=40)
    send = AsyncMock(return_value=proposals_ui.SENT)
    await proposals_ui.ProposalHandlers(SETTINGS, seeded, send).announce(None)  # type: ignore[arg-type]
    assert "\nZone 2 or moderate. You pick.\n" in send.await_args.args[2]


async def test_the_kind_tapped_is_the_kind_saved(
    application: App, seeded: Sessions, engine: Engine
) -> None:
    token = _propose(seeded, engine, **RIDE)  # the AI's hint is zone 2
    (reply,) = texts(await run(application, press(f"lp:moderate:{token}", OWNER)))
    assert reply.startswith("Saved: Moderate cardio (~75-80% effort), 40 min (bike), on ")
    assert _status(seeded, token) == "saved"


async def test_save_on_a_cardio_one_asks_for_the_kind(
    application: App, seeded: Sessions, engine: Engine
) -> None:
    token = _propose(seeded, engine, **RIDE)
    calls = await run(application, press(f"lp:save:{token}", OWNER))
    assert texts(calls) == [proposals_ui.UNPICKED]
    assert button_data(calls["sendMessage"][0]) == [
        f"lp:zone2:{token}",
        f"lp:moderate:{token}",
        f"lp:discard:{token}",
    ]
    assert _status(seeded, token) == "pending"


async def test_save_on_an_older_cardio_one_asks_for_the_kind_too(
    application: App, seeded: Sessions, engine: Engine
) -> None:
    """Review of #321: its message has a plain Save, which saved the AI's kind untouched."""
    token = _propose(seeded, engine, **RIDE)
    with seeded() as session:  # as proposed before the person picked: the AI's kind kept
        session.scalars(select(LogProposal)).one().payload = {
            "cardio": "zone2",
            "minutes": 40,
            "activity": "bike",
        }
        session.commit()
    calls = await run(application, press(f"lp:save:{token}", OWNER))
    assert texts(calls) == [proposals_ui.UNPICKED]
    assert _status(seeded, token) == "pending"


@pytest.mark.parametrize("action", ["zone2", "moderate"])
async def test_strangers_cant_pick_a_kind(
    application: App, seeded: Sessions, engine: Engine, action: str
) -> None:
    token = _propose(seeded, engine, **RIDE)
    assert await run(application, press(f"lp:{action}:{token}", STRANGER)) == {}
    assert _status(seeded, token) == "pending"


async def test_discard(application: App, seeded: Sessions, engine: Engine) -> None:
    token = _propose(seeded, engine)
    calls = await run(application, press(f"lp:discard:{token}", OWNER))
    assert texts(calls) == [proposals_ui.DISCARDED]
    assert "editMessageReplyMarkup" in calls
    later = await run(application, press(f"lp:save:{token}", OWNER))
    assert texts(later) == [proposals_ui.ALREADY["discarded"]]
    assert _ticks(seeded) == []


async def test_saved_on_the_web_is_already_saved_here(
    application: App, seeded: Sessions, engine: Engine
) -> None:
    token = _propose(seeded, engine)
    with seeded() as session:
        proposals.save(session, token, SETTINGS.tz, datetime.now(UTC), "web")
        session.commit()
    for action in ("save", "discard"):
        calls = await run(application, press(f"lp:{action}:{token}", OWNER))
        assert texts(calls) == ["Already saved."]
    assert _ticks(seeded) == ["protein"]


async def test_an_expired_one_has_gone(application: App, seeded: Sessions, engine: Engine) -> None:
    token = _propose(seeded, engine)
    with seeded() as session:
        session.scalars(select(LogProposal)).one().expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
        session.commit()
    calls = await run(application, press(f"lp:save:{token}", OWNER))
    assert texts(calls) == [proposals_ui.GONE]
    assert _ticks(seeded) == []


async def test_one_that_no_longer_fits_is_not_saved(
    application: App, seeded: Sessions, engine: Engine
) -> None:
    pull_ups = {"exercise": "Pull-up", "sets": [8], "unit": ""}
    token = _propose(seeded, engine, kind="strength", exercises=[pull_ups])
    with seeded() as session:  # today's session logged meanwhile
        typed = workout_log.draft(session, "pull-ups 5", TODAY, SETTINGS.tz)
        workout_log.save(session, typed, SETTINGS.tz)
        session.commit()
    (reply,) = texts(await run(application, press(f"lp:save:{token}", OWNER)))
    assert reply.startswith("Not saved: today's session changed.")
    assert _status(seeded, token) == "discarded"
    with seeded() as session:
        assert len(list(session.scalars(select(Workout.id)))) == 1


@pytest.mark.parametrize("action", ["save", "discard"])
async def test_strangers_get_nothing(
    application: App, seeded: Sessions, engine: Engine, action: str
) -> None:
    token = _propose(seeded, engine)
    assert await run(application, press(f"lp:{action}:{token}", STRANGER)) == {}
    assert _status(seeded, token) == "pending"
    assert _ticks(seeded) == []


@pytest.mark.parametrize("action", ["save", "discard"])
async def test_a_failed_save_keeps_the_buttons_and_says_so(
    application: App,
    seeded: Sessions,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    token = _propose(seeded, engine)
    monkeypatch.setattr(proposals_ui.proposals, "save", _locked)
    monkeypatch.setattr(proposals_ui.proposals, "discard", _locked)
    calls = await run(application, press(f"lp:{action}:{token}", OWNER))
    assert texts(calls) == [proposals_ui.FAILED]
    assert "editMessageReplyMarkup" not in calls
    assert _status(seeded, token) == "pending"


async def test_a_forged_button_does_nothing(application: App, seeded: Sessions) -> None:
    calls = await run(application, press("lp:save:" + "ab" * 16, OWNER))
    assert texts(calls) == [proposals_ui.GONE]
    assert texts(await run(application, press("lp:save:nonsense", OWNER))) == []


def test_the_app_hands_the_api_a_way_to_announce(application: App) -> None:
    assert callable(application.bot_data[ANNOUNCE])
    assert application.job_queue is not None
    assert application.job_queue.get_jobs_by_name(proposals_ui.JOB)


async def test_one_telegram_refuses_does_not_hold_up_the_rest(
    seeded: Sessions, engine: Engine
) -> None:
    """Review of #234: a message Telegram turned down for good stopped every later one."""
    refused = _propose(seeded, engine)
    later = _propose(seeded, engine, kind="habits", habits=["wind_down"])
    send = AsyncMock(side_effect=[proposals_ui.REFUSED, proposals_ui.SENT])
    handlers = proposals_ui.ProposalHandlers(SETTINGS, seeded, send)
    await handlers.announce(None)  # type: ignore[arg-type]  # the fake send needs no bot
    await handlers.announce(None)  # type: ignore[arg-type]
    assert send.await_count == 2  # each once; the refused one isn't tried again
    with seeded() as session:
        rows = {r.token: r for r in session.scalars(select(LogProposal))}
        assert rows[refused].announce_refused_at is not None
        assert rows[refused].announced_at is None
        assert rows[later].announced_at is not None
    with seeded() as session:  # still on Today in the app
        waiting = proposals.pending(session, datetime.now(UTC))
    assert {p.token for p in waiting} == {refused, later}


async def test_a_replaced_measurement_is_named_in_telegram(
    seeded: Sessions, engine: Engine
) -> None:
    with seeded() as session:
        session.add(Measurement(local_date=TODAY, kind="bodyweight", tenths=784))
        session.commit()
    _propose(seeded, engine, kind="body", measurements={"bodyweight": 82.4})
    send = AsyncMock(return_value=proposals_ui.SENT)
    await proposals_ui.ProposalHandlers(SETTINGS, seeded, send).announce(None)  # type: ignore[arg-type]
    text = send.await_args.args[2]
    assert "Bodyweight 82.4 kg\nReplaces the 78.4 kg saved that day." in text
