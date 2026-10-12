"""The question in Telegram (ADR-0060): a log for a day that already has its session asks to
replace it, move it or add to that day; and a session named on the first line is today's."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, STRANGER, button_data, press, run, text_message, texts
from tests.bot.test_band import _walk
from tests.bot.test_proposals import _propose
from training_coach.bot import band as band_ui
from training_coach.bot import clash as clash_ui
from training_coach.bot import logging_flow
from training_coach.bot import proposals as proposals_ui
from training_coach.bot.messages import LOG_CANCELLED, LOG_EXPIRED
from training_coach.db.models import LogProposal, PlanState, SessionTemplate, Workout
from training_coach.domain.queue import local_date
from training_coach.services.day_clash import Clash, Recorded, Resolution

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]
NL = chr(10)
TODAY = local_date(datetime.now(UTC), ZoneInfo("Europe/Berlin"))


def _ago(days: int) -> date:
    return TODAY - timedelta(days=days)


def _days(sessions: Sessions) -> dict[date, list[tuple[str | None, str]]]:
    with sessions() as session:
        slugs = dict(session.execute(select(SessionTemplate.id, SessionTemplate.slug)).all())
        found: dict[date, list[tuple[str | None, str]]] = {}
        for w in session.scalars(select(Workout).order_by(Workout.id)):
            slug = slugs[w.template_id] if w.template_id is not None else None
            found.setdefault(w.local_date, []).append((slug, w.status))
        return found


def _pointer(sessions: Sessions) -> str:
    with sessions() as session:
        state = session.get_one(PlanState, 1)
        return session.get_one(SessionTemplate, state.next_template_id).slug


async def _log(application: App, text: str) -> dict[str, list[dict[str, str]]]:
    """Send a log and tap Save: the replies to the Save."""
    drafted = await run(application, text_message(text, OWNER))
    token = button_data(drafted["sendMessage"][0])[0].split(":")[2]
    return await run(application, press(f"l:save:{token}", OWNER))


def _answers(calls: dict[str, list[dict[str, str]]]) -> list[str]:
    return button_data(calls["sendMessage"][-1])


LEGS = "Legs" + NL + "jump squats 6 6 6"


async def test_another_session_named_today_is_done_out_of_turn(
    application: App, seeded: Sessions
) -> None:
    assert _pointer(seeded) == "legs"
    saved = await _log(application, "today Arms" + NL + "chin ups 8 8")
    assert texts(saved)[0].startswith("Saved Arms, calves + neck")
    assert _days(seeded) == {TODAY: [("arms", "done")]}
    assert _pointer(seeded) == "legs"  # out of turn: Legs is still next (ADR-0016)
    named = await run(application, text_message("Legs" + NL + "jump squats 6 6", OWNER))
    assert texts(named)[0].startswith("Log for Legs:")


async def test_the_8_october_scenario(application: App, seeded: Sessions) -> None:
    """Legs on day N, Legs again for N-1, then a rest day for N: asked, then replaced."""
    await _log(application, "yesterday " + LEGS)
    await _log(application, f"{_ago(2):%Y-%m-%d} " + LEGS)
    asked = await _log(application, "yesterday rest")
    (question,) = texts(asked)
    assert question.startswith(f"{_ago(1):%a %d %b} already has Legs (3 sets: Jump squat).")
    answers = _answers(asked)
    assert [a.split(":")[1] for a in answers] == ["replace", "move", "add", "cancel"]
    assert _days(seeded)[_ago(1)] == [("legs", "done")]  # nothing saved yet
    replaced = await run(application, press(answers[0], OWNER))
    assert texts(replaced)[0].startswith(f"Saved a rest day for {_ago(1):%a %d %b}")
    assert _days(seeded) == {_ago(1): [(None, "rest")], _ago(2): [("legs", "done")]}
    assert _pointer(seeded) == "recovery"  # Legs counted once


async def test_move_by_a_day_button(application: App, seeded: Sessions) -> None:
    await _log(application, "yesterday " + LEGS)
    asked = await _log(application, "yesterday rest")
    days = await run(application, press(_answers(asked)[1], OWNER))
    assert texts(days) == [clash_ui.MOVE_ASK]
    shown = [b.split(":")[1] for b in _answers(days)]
    assert "m1" not in shown  # not the day it's on
    assert shown[-1] == "cancel"
    moved = await run(application, press(f"l:m3:{_answers(days)[0].split(':')[2]}", OWNER))
    assert texts(moved)[0].startswith("Saved a rest day")
    assert _days(seeded) == {_ago(1): [(None, "rest")], _ago(3): [("legs", "done")]}


async def test_move_by_a_typed_date(application: App, seeded: Sessions) -> None:
    await _log(application, "yesterday " + LEGS)
    asked = await _log(application, "yesterday rest")
    await run(application, press(_answers(asked)[1], OWNER))
    bad = await run(application, text_message("2020-01-01", OWNER))
    assert "more than 14 days ago" in texts(bad)[0]
    moved = await run(application, text_message(f"{_ago(4):%a %d %b}", OWNER))
    assert texts(moved)[0].startswith("Saved a rest day")
    assert _days(seeded)[_ago(4)] == [("legs", "done")]


async def test_a_new_log_after_move_is_a_log(application: App, seeded: Sessions) -> None:
    await _log(application, "yesterday " + LEGS)
    asked = await _log(application, "yesterday rest")
    await run(application, press(_answers(asked)[1], OWNER))
    drafted = await run(application, text_message("pull ups 8 8", OWNER))
    assert texts(drafted)[0].startswith("Log for Recovery + posture:")


async def test_a_day_to_move_to_that_is_taken_asks_for_another(
    application: App, seeded: Sessions
) -> None:
    await _log(application, f"{_ago(3):%Y-%m-%d} " + LEGS)
    await _log(application, "yesterday " + LEGS)
    asked = await _log(application, "yesterday rest")
    token = _answers(asked)[0].split(":")[2]
    taken = await run(application, press(f"l:m3:{token}", OWNER))
    (reply,) = texts(taken)
    assert reply.startswith(f"{_ago(3):%a %d %b} has Legs (3 sets: Jump squat) too.")
    assert "m3" not in [b.split(":")[1] for b in _answers(taken)]
    future = await run(application, text_message("Mon 1 Jan", OWNER))
    assert texts(future)  # a date problem, explained
    added = await run(application, press(f"l:add:{token}", OWNER))
    assert texts(added)[0].startswith("Saved a rest day")
    assert _days(seeded)[_ago(1)] == [("legs", "done"), (None, "rest")]


async def test_a_day_that_changed_since_asks_again(application: App, seeded: Sessions) -> None:
    await _log(application, "yesterday " + LEGS)
    asked = await _log(application, "yesterday rest")
    await _log(application, "yesterday Arms" + NL + "chin ups 8")  # asks too: left unanswered
    with seeded() as session:  # Legs moved away meanwhile, on another device
        legs = session.scalars(select(Workout).where(Workout.local_date == _ago(1))).first()
        assert legs is not None
        legs.local_date = _ago(5)
        session.add(Workout(local_date=_ago(1), template_id=legs.template_id, status="rest"))
        session.commit()
    again = await run(application, press(_answers(asked)[0], OWNER))
    assert texts(again)[0].startswith(clash_ui.CHANGED)
    assert _days(seeded)[_ago(1)] == [("legs", "rest")]


async def test_strangers_answers_do_nothing(application: App, seeded: Sessions) -> None:
    await _log(application, "yesterday " + LEGS)
    asked = await _log(application, "yesterday rest")
    for data in _answers(asked):
        assert await run(application, press(data, STRANGER)) == {}
    assert _days(seeded)[_ago(1)] == [("legs", "done")]


async def test_cancel_saves_nothing_and_an_unknown_question_has_expired(
    application: App, seeded: Sessions
) -> None:
    await _log(application, "yesterday " + LEGS)
    asked = await _log(application, "yesterday rest")
    token = _answers(asked)[0].split(":")[2]
    assert texts(await run(application, press(f"l:cancel:{token}", OWNER))) == [LOG_CANCELLED]
    assert texts(await run(application, press(f"l:replace:{token}", OWNER))) == [LOG_EXPIRED]
    assert _days(seeded)[_ago(1)] == [("legs", "done")]


async def test_cancel_forgets_the_question_too(application: App, seeded: Sessions) -> None:
    """Review of #242: Cancel dropped the draft but kept its question until a restart."""
    handlers = next(
        h.callback.__self__
        for group in application.handlers.values()
        for h in group
        if isinstance(getattr(h.callback, "__self__", None), logging_flow.LogHandlers)
    )
    await _log(application, "yesterday " + LEGS)
    asked = await _log(application, "yesterday rest")
    token = _answers(asked)[0].split(":")[2]
    assert token in handlers.asked[OWNER]
    await run(application, press(f"l:cancel:{token}", OWNER))
    assert token not in handlers.asked[OWNER]


def test_answers_read_from_buttons_and_typed_dates() -> None:
    clash = Clash(_ago(1), (Recorded(7, "Legs", "3 sets"),))
    assert clash_ui.resolution("replace", clash, TODAY) == Resolution("replace", (7,))
    assert clash_ui.resolution("m2", clash, TODAY) == Resolution("move", (7,), _ago(2))
    assert clash_ui.resolution("move", clash, TODAY) is None
    assert clash_ui.typed_move(f"{_ago(2):%Y-%m-%d}", clash, TODAY) == Resolution(
        "move", (7,), _ago(2)
    )
    assert clash_ui.typed_move("pull ups 8", clash, TODAY) is None
    assert clash_ui.typed_move("yesterday Legs", clash, TODAY) is None  # a log, not a date
    assert "more than 14 days" in str(clash_ui.typed_move("2020-01-01", clash, TODAY))
    two = Clash(_ago(1), (Recorded(7, "Legs", "3 sets"), Recorded(8, "Rest day", "rested")))
    assert "Legs (3 sets) and Rest day (rested)" in clash_ui.text(two)
    assert clash_ui.text(two).count("them") == 2


# ------------------------------------------------------------- AI proposals and the band


async def test_a_proposal_for_a_day_with_its_session_asks_in_telegram(
    application: App, seeded: Sessions, engine: Engine
) -> None:
    await _log(application, "yesterday " + LEGS)
    pull_ups = {"exercise": "Pull-up", "sets": [8, 8], "unit": ""}
    token = _propose(seeded, engine, kind="strength", day=_ago(1).isoformat(), exercises=[pull_ups])
    for data in (f"lp:replace:{token}", f"lp:move:{token}"):
        assert await run(application, press(data, STRANGER)) == {}
    asked = await run(application, press(f"lp:save:{token}", OWNER))
    assert texts(asked)[0].startswith(f"{_ago(1):%a %d %b} already has Legs")
    assert [a.split(":")[1] for a in _answers(asked)] == ["replace", "move", "add", "cancel"]
    days = await run(application, press(f"lp:move:{token}", OWNER))
    assert texts(days) == [clash_ui.MOVE_ASK_BUTTONS]
    await _log(application, f"{_ago(3):%Y-%m-%d} " + LEGS)  # that day gets taken meanwhile
    taken = await run(application, press(f"lp:m3:{token}", OWNER))
    assert texts(taken)[0].startswith(f"{_ago(3):%a %d %b} has Legs")
    moved = await run(application, press(f"lp:m4:{token}", OWNER))
    assert texts(moved)[0].startswith("Saved: ")
    assert _days(seeded)[_ago(4)] == [("legs", "done")]
    assert [s for s, _ in _days(seeded)[_ago(1)]] == ["torso"]  # the proposal's session


async def test_a_proposals_question_can_be_cancelled_and_left_waiting(
    application: App, seeded: Sessions, engine: Engine
) -> None:
    await _log(application, "yesterday " + LEGS)
    pull_ups = {"exercise": "Pull-up", "sets": [8], "unit": ""}
    token = _propose(seeded, engine, kind="strength", day=_ago(1).isoformat(), exercises=[pull_ups])
    await run(application, press(f"lp:save:{token}", OWNER))
    cancelled = await run(application, press(f"lp:cancel:{token}", OWNER))
    assert texts(cancelled) == [proposals_ui.WAITING]
    assert [a.split(":")[1] for a in _answers(cancelled)] == ["save", "discard"]
    unknown = await run(application, press(f"lp:add:{token}", OWNER))  # no question asked now
    assert texts(unknown) == [proposals_ui.WAITING]
    with seeded() as session:
        assert session.scalars(select(LogProposal.status)).one() == "pending"


def _rest_today_and_zone2_next(sessions: Sessions) -> None:
    with sessions() as session:
        zone2 = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "zone2"))
        session.get_one(PlanState, 1).next_template_id = zone2.one().id
        session.add(Workout(local_date=TODAY, status="rest"))
        session.commit()


async def test_counting_a_band_workout_into_a_day_with_its_session_asks(
    application: App, seeded: Sessions
) -> None:
    _rest_today_and_zone2_next(seeded)
    walk = _walk(seeded)
    for data in (f"ba:add:{walk}", f"ba:move:{walk}"):
        assert await run(application, press(data, STRANGER)) == {}
    asked = await run(application, press(f"bc:{walk}", OWNER))
    assert texts(asked)[0].startswith(f"{TODAY:%a %d %b} already has Rest day (rested).")
    assert _answers(asked)[0].split(":")[:2] == ["ba", "replace"]
    days = await run(application, press(f"ba:move:{walk}", OWNER))
    assert texts(days) == [clash_ui.MOVE_ASK_BUTTONS]
    refused = await run(application, press(f"ba:m0:{walk}", OWNER))  # the same day
    assert texts(refused)[0].startswith("pick a different day")
    added = await run(application, press(f"ba:add:{walk}", OWNER))
    assert texts(added)[0].startswith("Counted, and today's session is done.")
    assert _days(seeded)[TODAY] == [(None, "rest"), ("zone2", "done")]


async def test_a_band_question_cancelled_or_forgotten_leaves_it_on_offer(
    application: App, seeded: Sessions
) -> None:
    _rest_today_and_zone2_next(seeded)
    walk = _walk(seeded)
    await run(application, press(f"bc:{walk}", OWNER))
    cancelled = await run(application, press(f"ba:cancel:{walk}", OWNER))
    assert texts(cancelled) == [band_ui.NOT_COUNTED]
    assert _answers(cancelled) == [f"bc:{walk}", f"bx:{walk}"]
    forgotten = await run(application, press(f"ba:replace:{walk}", OWNER))
    assert texts(forgotten) == [band_ui.NOT_COUNTED]
    assert _days(seeded) == {TODAY: [(None, "rest")]}
    assert band_ui.parse(f"ba:m3:{walk}") == ("m3", walk)
    assert band_ui.parse(f"ba:dance:{walk}") is None
