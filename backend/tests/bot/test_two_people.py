"""Two people on one bot (ADR-0089, step 8): the owner (Telegram 42) and a member (77), with
TC_MULTI_USER on. Each converted command and button sees and changes only the sender's own rows;
a forged id names nothing of the other's. Strangers, and a member while the switch is off, get
nothing. The button classes not converted yet are the owner's alone (a check by hand)."""

import copy
from datetime import UTC, datetime, time
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import (
    MEMBER,
    MULTI,
    OWNER,
    STRANGER,
    button_data,
    command,
    press,
    run,
    text_message,
    texts,
    voice,
)
from tests.bot.test_progress import _pull_up, _step_name, _top_session
from training_coach.bot import stretching as stretching_ui
from training_coach.bot import undo as undo_ui
from training_coach.bot.app import ASK_ADMIN, HELP_TEXT, MEMBER_HELP_TEXT, MORNING_JOB, build_bot
from training_coach.bot.messages import LOG_EXPIRED, STALE
from training_coach.db.models import (
    Event,
    HabitCheck,
    LoginLink,
    PlanState,
    SessionTemplate,
    SetLog,
    Workout,
)
from training_coach.db.session import bound_user
from training_coach.domain.queue import local_date
from training_coach.services import share_card, user_settings

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]
URL = "https://coach.example.com"
LOG = "pull ups 8 8 7, dips 12 11"


def _next(sessions: Sessions) -> int:
    with sessions() as session:
        state = session.scalars(select(PlanState)).one()
        assert state.next_template_id is not None
        return state.next_template_id


def _count(sessions: Sessions, model: type) -> int:
    with sessions() as session:
        return session.scalar(select(func.count()).select_from(model)) or 0


def _next_run(application: App, name: str) -> datetime:
    assert application.job_queue is not None
    (job,) = application.job_queue.get_jobs_by_name(name)
    fire: datetime = job.job.trigger.get_next_fire_time(None, datetime(2026, 10, 6, 12, tzinfo=UTC))
    return fire


def _morning(sessions: Sessions) -> time:
    with sessions() as session:
        return user_settings.load(session).morning_time


def _elsewhere(member: Sessions, owner: Sessions) -> str:
    """Point the member's queue at a session the owner's isn't on; return its name."""
    with owner() as session:
        theirs = session.get(SessionTemplate, _next(owner))
        assert theirs is not None
        taken = theirs.name
    with member() as session:
        other = next(
            t
            for t in session.scalars(select(SessionTemplate).order_by(SessionTemplate.position))
            if t.name != taken
        )
        session.scalars(select(PlanState)).one().next_template_id = other.id
        session.commit()
        return other.name


# ------------------------------------------------------------------ commands


async def test_help_leaves_login_and_recover_out_for_a_member(both: App) -> None:
    assert texts(await run(both, command("/help", OWNER))) == [HELP_TEXT]
    assert texts(await run(both, command("/help", MEMBER))) == [MEMBER_HELP_TEXT]
    for name in ("/login", "/recover"):
        assert name not in MEMBER_HELP_TEXT
        assert name in HELP_TEXT
    assert "/today" in MEMBER_HELP_TEXT


async def test_today_and_week_are_each_persons_own(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    theirs = _elsewhere(member, seeded)
    owner_today = (await run(both, command("/today", OWNER)))["sendMessage"][0]
    member_today = (await run(both, command("/today", MEMBER)))["sendMessage"][0]
    assert f"q:start:{_next(seeded)}" in button_data(owner_today)
    assert f"q:start:{_next(member)}" in button_data(member_today)
    assert theirs in member_today["text"]
    assert theirs not in owner_today["text"].split("\n")[0]
    owner_week = texts(await run(both, command("/week", OWNER)))[0].split("\n")[2]
    member_week = texts(await run(both, command("/week", MEMBER)))[0].split("\n")[2]
    assert member_week.endswith(theirs)
    assert not owner_week.endswith(theirs)


async def test_a_member_gets_the_passkey_pointer_never_a_link(
    seeded: Sessions, member: Sessions
) -> None:
    bot = build_bot(MULTI.model_copy(update={"public_url": URL}), seeded)
    (reply,) = texts(await run(bot, command("/login", MEMBER)))
    assert f"{URL}/signin\n" in reply
    assert "#" not in reply  # no link token
    assert ASK_ADMIN in reply
    assert "/recover" not in reply
    assert texts(await run(bot, command("/recover", MEMBER))) == [ASK_ADMIN]
    assert _count(member, LoginLink) == 0
    assert _count(seeded, LoginLink) == 0
    (owner,) = texts(await run(bot, command("/login", OWNER)))  # the owner's is unchanged
    assert f"{URL}/signin#" in owner
    assert (_count(seeded, LoginLink), _count(member, LoginLink)) == (1, 0)


# ------------------------------------------------------------------ buttons


async def test_a_morning_button_changes_only_the_pressers_queue(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    mine, theirs = _next(seeded), _next(member)
    assert mine != theirs  # each person's sessions are their own rows
    (text,) = texts(await run(both, press(f"q:rest:{theirs}", MEMBER)))
    assert "moves to tomorrow" in text
    assert (_count(seeded, Workout), _count(member, Workout)) == (0, 1)
    # The member's old button, forged by the owner, names nothing of the owner's: stale.
    for data in (f"q:rest:{theirs}", f"q:next:{theirs}", f"q:pick:{mine}:{theirs}"):
        assert texts(await run(both, press(data, OWNER))) == [STALE]
    assert (_count(seeded, Workout), _count(member, Workout)) == (0, 1)
    assert _next(seeded) == mine


async def test_logs_are_saved_for_the_sender_and_drafts_are_their_own(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    calls = await run(both, text_message(LOG, MEMBER))
    token = button_data(calls["sendMessage"][0])[0].split(":")[2]
    assert texts(await run(both, press(f"l:save:{token}", OWNER))) == [LOG_EXPIRED]
    assert texts(await run(both, press(f"l:cancel:{token}", OWNER))) != []
    assert (_count(seeded, Workout), _count(member, Workout)) == (0, 0)
    await run(both, press(f"l:save:{token}", MEMBER))  # the owner's Cancel didn't touch it
    assert (_count(seeded, Workout), _count(member, Workout)) == (0, 1)


async def test_a_members_settings_leave_the_owners_and_their_job_times(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    before = _next_run(both, MORNING_JOB)
    calls = await run(both, press("s:morning:0630", MEMBER))
    assert "Morning message: 06:30" in calls["editMessageText"][0]["text"]
    await run(both, press("s:ask-morning", MEMBER))
    assert "Morning message: 07:30" in texts(await run(both, command("/settings", OWNER)))[0]
    # The owner wasn't asked for a time: their 06:45 is a log, the member's answers.
    assert not texts(await run(both, text_message("06:45", OWNER)))[0].startswith("Settings")
    await run(both, press("s:ask-morning", MEMBER))
    assert "Morning message: 06:45" in texts(await run(both, text_message("06:45", MEMBER)))[0]
    assert (_morning(member), _morning(seeded)) == (time(6, 45), time(7, 30))
    assert _next_run(both, MORNING_JOB) == before  # the jobs are the owner's until step 9
    await run(both, press("s:morning:0700", OWNER))
    assert _next_run(both, MORNING_JOB) != before


async def _saved(both: App, sender: int, sessions: Sessions) -> tuple[int, list[str]]:
    """Log and save LOG as ``sender``: their workout's id and the Saved reply's buttons."""
    drafted = await run(both, text_message(LOG, sender))
    token = button_data(drafted["sendMessage"][0])[0].split(":")[2]
    saved = await run(both, press(f"l:save:{token}", sender))
    with sessions() as session:
        workout_id = session.scalars(select(Workout.id)).one()
    return workout_id, button_data(saved["sendMessage"][0])


async def test_progress_and_its_buttons_are_each_persons_own(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    _top_session(member, days_ago=3)
    _top_session(member, days_ago=1)
    exercise_id, step_id = _pull_up(member)
    up = f"p:up:{exercise_id}:{step_id}"
    assert up in button_data((await run(both, command("/progress", MEMBER)))["sendMessage"][0])
    assert up not in button_data((await run(both, command("/progress", OWNER)))["sendMessage"][0])
    owner_step, member_step = _step_name(seeded), _step_name(member)
    # The ids are the catalogue's: the owner's press acts on the owner's own place, not ready.
    assert texts(await run(both, press(up, OWNER))) == [
        "Pull-up doesn't meet the rule any more. Keep going."
    ]
    assert (_step_name(seeded), _step_name(member)) == (owner_step, member_step)
    await run(both, press(up, MEMBER))
    assert (_step_name(seeded), _step_name(member)) == (owner_step, "Pause at top")


async def test_review_is_each_persons_own(both: App, seeded: Sessions, member: Sessions) -> None:
    before = texts(await run(both, command("/review", OWNER)))
    await _saved(both, MEMBER, member)
    assert texts(await run(both, command("/review", OWNER))) == before
    (theirs,) = texts(await run(both, command("/review", MEMBER)))
    assert [theirs] != before


async def test_habits_tick_only_the_pressers_own(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    today = local_date(datetime.now(UTC), MULTI.tz)
    tick = f"h:{today:%Y%m%d}:protein"
    assert tick in button_data((await run(both, command("/habits", MEMBER)))["sendMessage"][0])
    await run(both, press(tick, MEMBER))
    assert (_count(seeded, HabitCheck), _count(member, HabitCheck)) == (0, 1)
    await run(both, press(tick, OWNER))  # the owner's own tick, not an untick of the member's
    assert (_count(seeded, HabitCheck), _count(member, HabitCheck)) == (1, 1)


async def test_stretching_is_offered_and_logged_on_the_members_own_workout(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    """The gap #624 left: a member's Saved reply offered buttons only the owner could press."""
    workout_id, data = await _saved(both, MEMBER, member)
    choice = f"st:{workout_id}:10"
    assert choice in data
    assert texts(await run(both, press(choice, OWNER))) == [stretching_ui.GONE]
    done = f"st:done:{workout_id}:10"
    assert texts(await run(both, press(done, OWNER))) == [stretching_ui.GONE]
    assert texts(await run(both, press(choice, MEMBER)))[0].startswith("Stretching after")
    await run(both, press(done, MEMBER))
    with member() as session:
        assert 10 in session.scalars(select(SetLog.value)).all()
    assert _count(seeded, SetLog) == 0


async def test_undo_takes_back_only_the_pressers_own_change(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    await run(both, press(f"q:rest:{_next(member)}", MEMBER))
    asked = await run(both, command("/undo", MEMBER))
    with member() as session:
        event = session.scalars(select(Event.id).order_by(Event.id.desc())).first()
    assert button_data(asked["sendMessage"][0]) == [f"u:{event}", "u:keep"]
    assert texts(await run(both, command("/undo", OWNER))) == [undo_ui.REFUSED["nothing"]]
    assert texts(await run(both, press(f"u:{event}", OWNER))) == [undo_ui.REFUSED["nothing"]]
    assert _count(member, Workout) == 1
    assert texts(await run(both, press(f"u:{event}", MEMBER)))[0].startswith("Undone:")
    assert _count(member, Workout) == 0


async def test_share_draws_the_senders_own_weeks(
    both: App, monkeypatch: pytest.MonkeyPatch, member: Sessions
) -> None:
    drawn: list[int | None] = []
    facts = share_card.facts

    def spy(session: Session, today: Any) -> share_card.Card:
        drawn.append(bound_user(session))
        return facts(session, today)

    monkeypatch.setattr(share_card, "facts", spy)
    await run(both, command("/share", MEMBER))
    await run(both, command("/share", OWNER))
    with member() as session:
        assert drawn == [bound_user(session), 1]


# ------------------------------------------------------------------ nobody else

UPDATES = {
    "/start": command("/start", 0),
    "/help": command("/help", 0),
    "/today": command("/today", 0),
    "/week": command("/week", 0),
    "/login": command("/login", 0),
    "/recover": command("/recover", 0),
    "/settings": command("/settings", 0),
    "a log": text_message(LOG, 0),
    "a voice note": voice(0),
    "a morning button": press("q:rest:1", 0),
    "a log button": press("l:save:" + "ab" * 16, 0),
    "a settings button": press("s:morning:0630", 0),
    "a settings question": press("s:ask-morning", 0),
    "/progress": command("/progress", 0),
    "/review": command("/review", 0),
    "/habits": command("/habits", 0),
    "/undo": command("/undo", 0),
    "/share": command("/share", 0),
    "a progress button": press("p:up:1:1", 0),
    "a habit button": press("h:20261108:protein", 0),
    "a stretching button": press("st:1:10", 0),
    "an undo button": press("u:1", 0),
}


def _from(update: dict[str, Any], sender: int) -> dict[str, Any]:
    """``update`` sent by ``sender``, in their own private chat."""
    update = copy.deepcopy(update)
    body = update.get("message") or update["callback_query"]
    body["from"]["id"] = sender
    (body if "chat" in body else body["message"])["chat"]["id"] = sender
    return update


@pytest.mark.parametrize("update", UPDATES.values(), ids=UPDATES.keys())
async def test_a_stranger_gets_nothing(both: App, update: dict[str, Any]) -> None:
    assert await run(both, _from(update, STRANGER)) == {}


@pytest.mark.parametrize("update", UPDATES.values(), ids=UPDATES.keys())
async def test_a_member_gets_nothing_while_the_switch_is_off(
    application: App, member: Sessions, update: dict[str, Any]
) -> None:
    assert await run(application, _from(update, MEMBER)) == {}
    assert (_count(member, Workout), _count(member, HabitCheck)) == (0, 0)
    with member() as session:
        assert user_settings.load(session).morning_time == time(7, 30)
