"""Short on time today in the bot (ADR-0082): the work list follows the length chosen in the
app, and the morning message, sent before, shows the planned length and the offer."""

from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, SETTINGS, STRANGER, press, run, texts
from training_coach.bot.app import Handlers, build_bot
from training_coach.bot.messages import (
    ANOTHER_LENGTH,
    RAMP,
    SHORT_ON_TIME,
    WARM_UP,
    WORK_DOWN,
    session_detail_text,
)
from training_coach.db.models import SessionTemplate
from training_coach.services import guided, user_settings, users
from training_coach.services.today import session_plan

Sessions = sessionmaker[Session]
LEGS_PLANNED = "About 49 minutes, warm-up included."  # the bundled home Legs day
DROPPED_AT_20 = (
    "Shortened to 20 minutes in the app; dropped: Hamstring curl, Calf raise, "
    "Tibialis raise, Pistol squat, Single-leg Romanian deadlift."
)


def _at(sessions: Sessions, slug: str) -> int:
    with sessions() as session:
        template = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == slug))
        tid = template.one().id
        state = users.plan_state(session)
        assert state is not None
        state.next_template_id = tid
        session.commit()
    return tid


def _choose(
    sessions: Sessions, handlers: Handlers, minutes: int | None, keep: tuple[str, ...] = ()
) -> None:
    """Pick the day's minutes, and exercises to Keep, as the app does."""
    with sessions() as session:
        plan = guided.today(session, handlers._local_today(), SETTINGS.tz)
        assert plan is not None
        kept = guided.kept(session, plan.day)
        revision = kept.revision if kept is not None else 0
        assert isinstance(guided.choose_length(session, plan, revision, minutes, keep), int)
        session.commit()


def _keep_first_set(sessions: Sessions, handlers: Handlers) -> None:
    with sessions() as session:
        plan = guided.today(session, handlers._local_today(), SETTINGS.tz)
        assert plan is not None
        kept = guided.kept(session, plan.day)
        revision = kept.revision if kept is not None else 0
        first = plan.order[0]
        done = guided.Done(first.item, first.set_no, first.target)
        assert isinstance(guided.keep(session, plan, revision, 1, [], [done]), int)
        session.commit()


def _listed(text: str) -> dict[str, int]:
    """Sets per exercise in the work list."""
    sets: dict[str, int] = {}
    for line in text.splitlines():
        head = line.split(". ", 1)
        if len(head) == 2 and head[0].isdigit():
            name = head[1].split(" (")[0]
            sets[name] = sets.get(name, 0) + 1
    return sets


async def test_the_morning_shows_the_planned_length_and_offers_a_shorter_one(
    seeded: Sessions,
) -> None:
    _at(seeded, "legs")
    context = type("Ctx", (), {"bot": AsyncMock()})()
    await Handlers(SETTINGS, seeded).morning(context)  # type: ignore[arg-type]
    text = context.bot.send_message.await_args.kwargs["text"]
    assert f"{LEGS_PLANNED} {SHORT_ON_TIME}" in text.splitlines()
    assert SHORT_ON_TIME == "Short on time? Pick 40, 30 or 20 minutes in the app before you start."
    assert WARM_UP in text.splitlines()
    assert _listed(text)["Calf raise"] == 4  # the list as planned


async def test_today_follows_a_shorter_day_chosen_in_the_app(seeded: Sessions) -> None:
    _at(seeded, "legs")
    handlers = Handlers(SETTINGS, seeded)
    before, _ = handlers._today()
    _choose(seeded, handlers, 20)
    text, _ = handlers._today()
    lines = text.splitlines()
    assert DROPPED_AT_20 in lines
    assert SHORT_ON_TIME not in text
    assert RAMP in lines  # 30 minutes or less: ramp sets, not the 5-minute warm-up
    assert WARM_UP not in lines
    assert WORK_DOWN not in lines  # every pair lost a partner: each is done straight
    assert _listed(text) == {"Jump squat": 2, "Kettlebell swing": 2, "Split squat": 2}
    assert len(_listed(before)) == 8


async def test_forty_minutes_keeps_every_exercise_at_two_sets_and_the_warm_up(
    seeded: Sessions,
) -> None:
    _at(seeded, "legs")
    handlers = Handlers(SETTINGS, seeded)
    _choose(seeded, handlers, 40)
    text, _ = handlers._today()
    lines = text.splitlines()
    assert "Shortened to 40 minutes in the app." in lines
    assert WARM_UP in lines
    assert WORK_DOWN in lines
    assert set(_listed(text).values()) == {2}
    assert len(_listed(text)) == 8


async def test_a_day_that_cannot_get_that_short_says_how_short_it_got(seeded: Sessions) -> None:
    """Five exercises pinned with Keep: 20 minutes is out of reach, so the line gives the
    shortest the app could make it (``Trimmed.shortest``), not the minutes chosen."""
    _at(seeded, "legs")
    handlers = Handlers(SETTINGS, seeded)
    pinned = ("tibialis-raise", "calf-raise", "hamstring-curl", "pistol-squat", "single-leg-rdl")
    _choose(seeded, handlers, 20, pinned)
    with seeded() as session:
        plan = guided.today(session, handlers._local_today(), SETTINGS.tz)
        assert plan is not None
        assert plan.length is not None
        shortest = plan.length.trimmed.shortest
    assert shortest is not None
    assert shortest > 20
    text, _ = handlers._today()
    assert (
        f"Shortened as far as it goes in the app: about {shortest} minutes; dropped: "
        "Split squat, Kettlebell swing, Jump squat."
    ) in text.splitlines()
    assert "Shortened to 20 minutes" not in text
    assert set(_listed(text)) == {
        "Tibialis raise",
        "Calf raise",
        "Hamstring curl",
        "Pistol squat",
        "Single-leg Romanian deadlift",
    }


async def test_as_planned_again_shows_the_whole_list(seeded: Sessions) -> None:
    _at(seeded, "legs")
    handlers = Handlers(SETTINGS, seeded)
    before, _ = handlers._today()
    _choose(seeded, handlers, 20)
    _choose(seeded, handlers, None)
    text, _ = handlers._today()
    assert text == before


async def test_no_offer_once_the_session_has_started(seeded: Sessions) -> None:
    _at(seeded, "legs")
    handlers = Handlers(SETTINGS, seeded)
    _keep_first_set(seeded, handlers)
    text, _ = handlers._today()
    assert LEGS_PLANNED in text.splitlines()
    assert SHORT_ON_TIME not in text


async def test_a_conditioning_session_offers_it_without_a_warm_up(seeded: Sessions) -> None:
    _at(seeded, "moderate-cardio")
    text, _ = Handlers(SETTINGS, seeded)._today()
    (line,) = [line for line in text.splitlines() if line.startswith("About ")]
    assert line.endswith(f" minutes. {SHORT_ON_TIME}")
    assert "Warm up" not in text


async def test_a_recovery_session_is_not_offered_shorter(seeded: Sessions) -> None:
    _at(seeded, "recovery")
    text, _ = Handlers(SETTINGS, seeded)._today()
    assert SHORT_ON_TIME not in text
    assert "About " not in text


@pytest.fixture
def app(seeded: Sessions) -> Application:  # type: ignore[type-arg]  # see build_bot
    return build_bot(SETTINGS, seeded)


async def test_start_lists_the_shorter_day(
    app: Application,  # type: ignore[type-arg]
    seeded: Sessions,
) -> None:
    tid = _at(seeded, "legs")
    _choose(seeded, Handlers(SETTINGS, seeded), 20)
    (text,) = texts(await run(app, press(f"q:start:{tid}", OWNER)))
    assert DROPPED_AT_20 in text.splitlines()
    assert _listed(text) == {"Jump squat": 2, "Kettlebell swing": 2, "Split squat": 2}
    assert "- Tibialis raise:" not in text  # no how-to for a dropped exercise


async def test_a_strangers_start_still_gets_nothing(
    app: Application,  # type: ignore[type-arg]
    seeded: Sessions,
) -> None:
    tid = _at(seeded, "legs")
    _choose(seeded, Handlers(SETTINGS, seeded), 20)
    assert await run(app, press(f"q:start:{tid}", STRANGER)) == {}


# ---------------------------------------------------------------- minutes per session (T2)


def _setting(sessions: Sessions, minutes: int) -> None:
    with sessions() as session:
        user_settings.update(session, session_minutes=minutes)
        session.commit()


def _minutes_today(sessions: Sessions, handlers: Handlers) -> int:
    with sessions() as session:
        plan = guided.today(session, handlers._local_today(), SETTINGS.tz)
        assert plan is not None
        return plan.minutes


async def test_the_morning_follows_minutes_per_session(seeded: Sessions) -> None:
    _at(seeded, "legs")
    _setting(seeded, 30)
    handlers = Handlers(SETTINGS, seeded)
    context = type("Ctx", (), {"bot": AsyncMock()})()
    await handlers.morning(context)  # type: ignore[arg-type]
    text = context.bot.send_message.await_args.kwargs["text"]
    lines = text.splitlines()
    about = _minutes_today(seeded, handlers)
    assert f"About {about} minutes at your 30-minute setting. {ANOTHER_LENGTH}" in lines
    assert ANOTHER_LENGTH == "Pick another length for today in the app before you start."
    assert RAMP in lines
    assert SHORT_ON_TIME not in text
    assert set(_listed(text).values()) == {2}


async def test_the_work_list_names_what_the_setting_drops(seeded: Sessions) -> None:
    _at(seeded, "legs")
    _setting(seeded, 20)
    handlers = Handlers(SETTINGS, seeded)
    text, _ = handlers._today()
    about = _minutes_today(seeded, handlers)
    assert (
        f"About {about} minutes at your 20-minute setting; dropped: Hamstring curl, "
        "Calf raise, Tibialis raise, Pistol squat, Single-leg Romanian deadlift. "
        f"{ANOTHER_LENGTH}"
    ) in text.splitlines()
    assert _listed(text) == {"Jump squat": 2, "Kettlebell swing": 2, "Split squat": 2}


async def test_a_days_as_planned_overrides_the_setting(seeded: Sessions) -> None:
    _at(seeded, "legs")
    handlers = Handlers(SETTINGS, seeded)
    planned, _ = handlers._today()
    _setting(seeded, 20)
    _choose(seeded, handlers, None)
    text, _ = handlers._today()
    assert text == planned


async def test_no_other_length_is_offered_once_the_session_has_started(seeded: Sessions) -> None:
    _at(seeded, "legs")
    _setting(seeded, 30)
    handlers = Handlers(SETTINGS, seeded)
    _keep_first_set(seeded, handlers)
    text, _ = handlers._today()
    about = _minutes_today(seeded, handlers)
    assert f"About {about} minutes at your 30-minute setting." in text.splitlines()
    assert ANOTHER_LENGTH not in text


async def test_start_lists_the_session_at_the_setting(
    app: Application,  # type: ignore[type-arg]
    seeded: Sessions,
) -> None:
    tid = _at(seeded, "legs")
    _setting(seeded, 20)
    (text,) = texts(await run(app, press(f"q:start:{tid}", OWNER)))
    assert "at your 20-minute setting; dropped: Hamstring curl" in text
    assert ANOTHER_LENGTH not in text  # the offer is the morning's and /today's
    assert _listed(text) == {"Jump squat": 2, "Kettlebell swing": 2, "Split squat": 2}


def test_a_setting_out_of_reach_says_the_shortest_it_gets(seeded: Sessions) -> None:
    tid = _at(seeded, "legs")
    _setting(seeded, 20)
    with seeded() as session:
        shown = session_plan(session, tid, None)
        assert shown is not None
        cut, length = guided.at_length(session, Handlers(SETTINGS, seeded)._local_today(), shown)
    assert length is not None
    out_of_reach = replace(length, trimmed=replace(length.trimmed, minutes=23, fits=False))
    text = session_detail_text(cut, out_of_reach)
    assert "About 23 minutes, the shortest it gets, at your 20-minute setting; dropped: " in text
