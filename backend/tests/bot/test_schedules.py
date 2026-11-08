"""Each person's scheduled messages (step 9): the owner (Telegram 42) and a member (77) each get
their own morning message, evening nudge and Sunday review, at their own times, in their own
chat, from their own data. A member gets nothing with the switch off or while away, no daily
check in the morning without their yes to it (ADR-0090), and their jobs go when they unlink,
leave or are erased. The band offers and alerts, proposals sent out and plan notices go to each
person too, the band's only with their yes to band data."""

from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import time_machine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import MEMBER, MULTI, OWNER, SETTINGS
from tests.bot.test_band import MADE, _secret, _sync, _walk
from tests.bot.test_two_people import _elsewhere, _member_id, _propose, _yes
from training_coach.bot import band as band_ui
from training_coach.bot import daily_check as daily_ui
from training_coach.bot import notices as notices_ui
from training_coach.bot import proposals as proposals_ui
from training_coach.bot import schedules
from training_coach.bot.app import ANNOUNCE, FORGET, RESCHEDULE, build_bot
from training_coach.bot.messages import NUDGE
from training_coach.db.models import PlanNotice, User, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.band_watch import Notice
from training_coach.domain.consent import Category
from training_coach.domain.queue import local_date
from training_coach.services import erase, user_settings, users

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]
AFTER = datetime(2026, 10, 6, 12, tzinfo=UTC)  # a Tuesday, in summer time (UTC+2)


def _names(application: App) -> set[str]:
    assert application.job_queue is not None
    return {job.name for job in application.job_queue.jobs() if job.name is not None}


def _jobs_of(application: App, user_id: int) -> set[str]:
    return {name for name in _names(application) if name.endswith(f":{user_id}")}


def _next_run(application: App, kind: str, user_id: int) -> datetime:
    assert application.job_queue is not None
    (job,) = application.job_queue.get_jobs_by_name(schedules.name(kind, user_id))
    fire: datetime = job.job.trigger.get_next_fire_time(None, AFTER)
    return fire.astimezone(UTC)


async def _fire(application: App, kind: str, user_id: int) -> list[tuple[int, str]]:
    """Run ``user_id``'s job of ``kind`` now; the (chat, text) of each message it sent."""
    return await _run(application, schedules.name(kind, user_id))


async def _run(application: App, name: str) -> list[tuple[int, str]]:
    """Run the job called ``name`` now; the (chat, text) of each message it sent."""
    assert application.job_queue is not None
    (job,) = application.job_queue.get_jobs_by_name(name)
    send = AsyncMock()
    await job.callback(SimpleNamespace(bot=SimpleNamespace(send_message=send)))  # type: ignore[arg-type]  # fake context
    return [(call.kwargs["chat_id"], call.kwargs["text"]) for call in send.await_args_list]


def _times(sessions: Sessions, morning: time, nudge: time, review: time) -> None:
    with sessions() as session:
        user_settings.update(session, morning_time=morning, nudge_time=nudge, review_time=review)
        session.commit()


def _away(sessions: Sessions, user_id: int) -> None:
    with session_scope(make_session_factory(sessions.kw["bind"])) as shared:
        shared.get_one(User, user_id).last_seen_in_europe = datetime.now(UTC) - timedelta(days=31)


def _rest_today(sessions: Sessions) -> None:
    with sessions() as session:
        session.add(Workout(local_date=local_date(datetime.now(UTC), MULTI.tz), status="rest"))
        session.commit()


async def test_each_person_gets_their_own_messages_at_their_own_times(
    seeded: Sessions, member: Sessions
) -> None:
    _times(member, time(6, 15), time(21, 30), time(17, 0))
    both = build_bot(MULTI, seeded)  # start-up makes everyone's jobs
    theirs = _member_id(member)
    kinds = set(schedules.KINDS)
    assert _jobs_of(both, users.OWNER) == {schedules.name(k, users.OWNER) for k in kinds}
    assert _jobs_of(both, theirs) == {schedules.name(k, theirs) for k in kinds}
    # The owner's as always: 07:30, 20:00 and Sunday 19:00; the member's from their settings.
    assert _next_run(both, schedules.MORNING, users.OWNER) == datetime(
        2026, 10, 7, 5, 30, tzinfo=UTC
    )
    assert _next_run(both, schedules.MORNING, theirs) == datetime(2026, 10, 7, 4, 15, tzinfo=UTC)
    assert _next_run(both, schedules.NUDGE, users.OWNER) == datetime(2026, 10, 6, 18, 0, tzinfo=UTC)
    assert _next_run(both, schedules.NUDGE, theirs) == datetime(2026, 10, 6, 19, 30, tzinfo=UTC)
    assert _next_run(both, schedules.REVIEW, users.OWNER) == datetime(2026, 10, 11, 17, tzinfo=UTC)
    assert _next_run(both, schedules.REVIEW, theirs) == datetime(2026, 10, 11, 15, tzinfo=UTC)


async def test_each_message_goes_to_its_own_chat_with_its_own_data(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    theirs = _member_id(member)
    session_name = _elsewhere(member, seeded)  # the member's next session isn't the owner's
    ((owner_chat, owners),) = await _fire(both, schedules.MORNING, users.OWNER)
    ((member_chat, members),) = await _fire(both, schedules.MORNING, theirs)
    assert (owner_chat, member_chat) == (OWNER, MEMBER)
    assert session_name in members
    assert session_name not in owners
    # The member rests today: their evening has the habit buttons and no nudge, and their
    # review counts it; the owner's are as before.
    _rest_today(member)
    nudged = NUDGE.split("{")[0]
    ((chat, nudge),) = await _fire(both, schedules.NUDGE, users.OWNER)
    assert chat == OWNER
    assert nudge.startswith(nudged)
    ((chat, evening),) = await _fire(both, schedules.NUDGE, theirs)
    assert chat == MEMBER
    assert nudged not in evening
    ((owner_chat, owners),) = await _fire(both, schedules.REVIEW, users.OWNER)
    ((member_chat, members),) = await _fire(both, schedules.REVIEW, theirs)
    assert (owner_chat, member_chat) == (OWNER, MEMBER)
    assert "1 rest day" in members
    assert "rest day" not in owners


async def test_a_member_gets_nothing_with_the_switch_off(
    seeded: Sessions, member: Sessions
) -> None:
    off = build_bot(SETTINGS, seeded)
    theirs = _member_id(member)
    assert _jobs_of(off, theirs) == set()
    off.bot_data[RESCHEDULE](theirs)  # a stale hook from the web makes none either
    assert _jobs_of(off, theirs) == set()
    assert len(_jobs_of(off, users.OWNER)) == len(schedules.KINDS)


async def test_a_member_away_gets_nothing_and_the_owner_still_does(
    both: App, member: Sessions
) -> None:
    theirs = _member_id(member)
    _away(member, theirs)
    for kind in schedules.KINDS:
        assert await _fire(both, kind, theirs) == []
    assert [chat for chat, _ in await _fire(both, schedules.MORNING, users.OWNER)] == [OWNER]


async def test_the_daily_check_comes_in_the_morning_only_with_their_yes(
    both: App, member: Sessions
) -> None:
    theirs = _member_id(member)
    ((_, text),) = await _fire(both, schedules.MORNING, theirs)
    assert daily_ui.ASK not in text
    _yes(member, Category.DAILY_CHECK)
    ((_, text),) = await _fire(both, schedules.MORNING, theirs)
    assert daily_ui.ASK in text
    ((_, owners),) = await _fire(both, schedules.MORNING, users.OWNER)
    assert daily_ui.ASK in owners  # the owner is never asked


async def test_unlink_and_leave_take_their_jobs_away(both: App, member: Sessions) -> None:
    theirs = _member_id(member)
    shared = make_session_factory(member.kw["bind"])
    with session_scope(shared) as session:
        session.get_one(User, theirs).telegram_user_id = None  # unlinked on Account
    both.bot_data[FORGET](theirs)
    assert _jobs_of(both, theirs) == set()
    assert len(_jobs_of(both, users.OWNER)) == len(schedules.KINDS)
    with session_scope(shared) as session:  # connected again
        session.get_one(User, theirs).telegram_user_id = MEMBER
    both.bot_data[RESCHEDULE](theirs)
    assert len(_jobs_of(both, theirs)) == len(schedules.KINDS)
    with session_scope(shared) as session:  # and then left: the row goes
        assert erase.leave(session, theirs, None, datetime.now(UTC))
    both.bot_data[FORGET](theirs)
    assert _jobs_of(both, theirs) == set()


async def test_a_job_left_behind_sends_nothing_once_they_are_unlinked(
    both: App, member: Sessions
) -> None:
    """Each run asks the gate again, so an unlink the bot wasn't told of sends nothing."""
    theirs = _member_id(member)
    with session_scope(make_session_factory(member.kw["bind"])) as session:
        session.get_one(User, theirs).telegram_user_id = None
    for kind in schedules.KINDS:
        assert await _fire(both, kind, theirs) == []


async def test_the_owners_erase_starts_their_jobs_again_at_the_default_times(
    seeded: Sessions,
) -> None:
    _times(seeded, time(6, 0), time(21, 0), time(18, 0))
    application = build_bot(SETTINGS, seeded)
    assert _next_run(application, schedules.MORNING, users.OWNER).hour == 4
    with seeded() as session:  # what erase leaves: the link, and no settings of theirs
        row = users.settings_row(session)
        assert row is not None
        session.delete(row)
        session.commit()
    application.bot_data[FORGET](users.OWNER)
    assert _next_run(application, schedules.MORNING, users.OWNER) == datetime(
        2026, 10, 7, 5, 30, tzinfo=UTC
    )


async def test_settings_that_cant_be_read_leave_their_jobs_where_they_are(
    seeded: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A locked database on a change of times mustn't move them to the defaults (review of
    #652); at start-up, with no jobs yet, the defaults are what there is."""
    _times(seeded, time(6, 0), time(21, 0), time(18, 0))
    application = build_bot(SETTINGS, seeded)
    morning = _next_run(application, schedules.MORNING, users.OWNER)
    assert morning == datetime(2026, 10, 7, 4, 0, tzinfo=UTC)

    def locked(_session: Session) -> user_settings.Prefs:
        raise OperationalError("SELECT", {}, Exception("database is locked"))

    monkeypatch.setattr(user_settings, "load", locked)
    application.bot_data[RESCHEDULE](users.OWNER)
    assert _next_run(application, schedules.MORNING, users.OWNER) == morning
    fresh = build_bot(SETTINGS, seeded)
    assert _next_run(fresh, schedules.MORNING, users.OWNER) == datetime(
        2026, 10, 7, 5, 30, tzinfo=UTC
    )


async def test_connecting_telegram_makes_their_jobs(seeded: Sessions) -> None:
    with session_scope(make_session_factory(seeded.kw["bind"])) as shared:
        person = User(role=users.MEMBER)
        shared.add(person)
        shared.flush()
        theirs = person.id
    application = build_bot(MULTI, seeded)
    assert _jobs_of(application, theirs) == set()  # no Telegram yet
    with session_scope(make_session_factory(seeded.kw["bind"])) as shared:
        shared.get_one(User, theirs).telegram_user_id = MEMBER
    application.bot_data[RESCHEDULE](theirs)
    assert len(_jobs_of(application, theirs)) == len(schedules.KINDS)


# ------------------------------------------------------------------ checks for everyone


async def test_band_offers_go_to_each_person_with_band_data_open(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    _walk(seeded)
    _walk(member)
    owners = await _run(both, band_ui.JOB)
    assert [chat for chat, _ in owners] == [OWNER]  # no yes from the member: nothing for them
    _yes(member, Category.BAND)
    assert [chat for chat, _ in await _run(both, band_ui.JOB)] == [MEMBER]


async def test_band_data_alerts_go_to_the_person_whose_band_stopped(
    both: App, member: Sessions
) -> None:
    _secret(member)
    _sync(member, MADE)
    with time_machine.travel(MADE + timedelta(hours=25), tick=False):
        assert await _run(both, band_ui.WATCH_JOB) == []  # band data isn't open to them
        _yes(member, Category.BAND)
        told = await _run(both, band_ui.WATCH_JOB)
    assert told == [(MEMBER, band_ui.NOTICES[Notice.QUIET])]  # the owner has no band: nothing


async def test_proposals_go_to_the_person_whose_ai_proposed_them(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    _propose(member, _member_id(member), kind="habits", habits=["protein"])
    _propose(seeded, users.OWNER, kind="habits", habits=["protein"])
    send = AsyncMock()
    with patch.object(type(both.bot), "send_message", send):  # the bot itself can't be set
        await both.bot_data[ANNOUNCE](_member_id(member))  # from /mcp: only that person's
    assert [call.kwargs["chat_id"] for call in send.await_args_list] == [MEMBER]
    assert [chat for chat, _ in await _run(both, proposals_ui.JOB)] == [OWNER]


async def test_plan_notices_go_to_each_person_with_their_own(
    both: App, seeded: Sessions, member: Sessions
) -> None:
    for sessions, text in ((seeded, "Mine."), (member, "Theirs.")):
        with session_scope(sessions) as session:
            session.add(PlanNotice(text=text))
    told = await _run(both, notices_ui.JOB)
    assert told == [
        (OWNER, notices_ui.message(["Mine."])),
        (MEMBER, notices_ui.message(["Theirs."])),
    ]


async def test_no_checks_for_a_member_away_or_with_the_switch_off(
    seeded: Sessions, member: Sessions
) -> None:
    _yes(member, Category.BAND)
    _walk(member)
    with session_scope(member) as session:
        session.add(PlanNotice(text="Theirs."))
    off = build_bot(SETTINGS, seeded)
    assert await _run(off, band_ui.JOB) == []
    assert await _run(off, notices_ui.JOB) == []
    both = build_bot(MULTI, seeded)
    _away(member, _member_id(member))
    assert await _run(both, band_ui.JOB) == []
    assert await _run(both, notices_ui.JOB) == []
