"""The members' wind-down (ADR-0059): with the switch off each member gets a closing day 30 days
on, then everything of theirs goes on that day; switching back on clears it. The owner never
closes."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine

from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import left_list, users, wind_down
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.wind_down import Told

TODAY = date(2026, 11, 7)


@pytest.fixture
def members(engine: Engine) -> Engine:
    """The owner, member 2 with Telegram and member 3 without."""
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
        shared.get_one(User, users.OWNER).telegram_user_id = 1111
        shared.add(User(id=2, role=users.MEMBER, telegram_user_id=2222))
        shared.add(User(id=3, role=users.MEMBER))
        shared.flush()
        apply_seed(shared, load_plan())
    return engine


def _run(engine: Engine, multi_user: bool, today: date, left: Path | None) -> wind_down.Report:
    with session_scope(make_session_factory(engine)) as shared:
        return wind_down.run(shared, multi_user, today, left)


def _closing(engine: Engine) -> dict[int, date | None]:
    with session_scope(make_session_factory(engine)) as shared:
        return {u.id: u.closing_on for u in shared.query(User).order_by(User.id)}


def test_switched_off_each_member_gets_a_day_30_days_on_once(
    members: Engine, tmp_path: Path
) -> None:
    on = TODAY + timedelta(days=30)
    report = _run(members, False, TODAY, tmp_path / left_list.NAME)
    assert report.closing == [Told(2222, on), Told(None, on)]
    assert report.erased == []
    assert _closing(members) == {users.OWNER: None, 2: on, 3: on}
    later = _run(members, False, TODAY + timedelta(days=1), tmp_path / left_list.NAME)
    assert later.closing == []  # told once
    assert _closing(members)[2] == on  # the day doesn't move


def test_on_their_day_everything_of_theirs_goes(members: Engine, tmp_path: Path) -> None:
    path = tmp_path / left_list.NAME
    _run(members, False, TODAY, path)
    day = TODAY + timedelta(days=30)
    assert _run(members, False, day - timedelta(days=1), path).erased == []
    report = _run(members, False, day, path)
    assert report.erased == [Told(2222, day), Told(None, day)]
    assert report.gone == [2, 3]  # for the bot to forget (ADR-0089)
    assert list(_closing(members)) == [users.OWNER]
    assert sorted(e.user_id for e in left_list.read(path)) == [2, 3]  # kept gone after a restore


def test_switching_back_on_clears_the_day(members: Engine, tmp_path: Path) -> None:
    _run(members, False, TODAY, tmp_path / left_list.NAME)
    report = _run(members, True, TODAY + timedelta(days=5), tmp_path / left_list.NAME)
    assert report.reopened == 2
    assert _closing(members) == {users.OWNER: None, 2: None, 3: None}
    again = _run(members, True, TODAY + timedelta(days=60), tmp_path / left_list.NAME)
    assert again.erased == []
    assert len(_closing(members)) == 3


def test_nothing_to_do_without_members(engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    report = _run(engine, False, TODAY, None)
    assert (report.closing, report.erased, report.reopened) == ([], [], 0)


def test_the_closing_text_names_the_day() -> None:
    assert "erased on 7 December 2026" in wind_down.closing_text(date(2026, 12, 7))


async def test_the_loop_runs_each_day_at_its_time_and_outlives_a_bad_day() -> None:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Europe/Berlin")
    clock = [datetime(2026, 11, 7, 3, 0, tzinfo=UTC)]  # 04:00 in Berlin
    slept: list[float] = []
    runs: list[int] = []

    async def sleep(seconds: float) -> None:
        if len(slept) == 2:
            raise asyncio.CancelledError
        slept.append(seconds)
        clock[0] += timedelta(seconds=seconds)

    async def once() -> None:
        runs.append(1)
        if len(runs) == 1:
            raise RuntimeError("locked database")

    with pytest.raises(asyncio.CancelledError):
        await wind_down.run_daily(once, tz, clock=lambda: clock[0], sleep=sleep)
    assert slept == [30 * 60, 24 * 3600]  # to 04:30, then a day
    assert len(runs) == 2  # the failed day didn't end it
