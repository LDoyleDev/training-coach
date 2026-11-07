"""The wind-down when ``TC_MULTI_USER`` goes off with members still here (ADR-0059).

Each member gets a closing day 30 days on and is told; on that day everything of theirs is
erased, as if they had left (ADR-0088). Until then they can sign in only to export or leave
(``api.auth.WIND_DOWN``). Switching back on clears the day. It runs every day whatever the switch
says, bot or no bot, and does nothing with no members.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import User
from training_coach.domain.backups import next_run
from training_coach.services.erase import leave
from training_coach.services.users import OWNER

log = structlog.get_logger(__name__)

CLOSING = timedelta(days=30)
# After the 03:30 backup, so the last copy before an erase is fresh; and never at start-up, when
# a Pi without a clock battery can still have a stale date that would close someone early.
AT = time(4, 30)


@dataclass(frozen=True)
class Told:
    chat: int | None  # their Telegram chat, found before anything is deleted
    on: date


@dataclass
class Report:
    closing: list[Told] = field(default_factory=list)  # given a closing day today
    erased: list[Told] = field(default_factory=list)  # their day came
    reopened: int = 0  # the switch went back on


def run(session: Session, multi_user: bool, today: date, left: Path | None) -> Report:
    """One day's wind-down. Runs in an unbound session (``users`` is shared, and an erase
    deletes the user row)."""
    report = Report()
    members = list(session.scalars(select(User).where(User.id != OWNER).order_by(User.id)))
    if multi_user:
        for member in members:
            if member.closing_on is not None:
                member.closing_on = None
                report.reopened += 1
        if report.reopened:
            log.info("wind_down.reopened", members=report.reopened)
        return report
    for member in members:
        if member.closing_on is None:
            member.closing_on = today + CLOSING
            report.closing.append(Told(member.telegram_user_id, member.closing_on))
    due = [
        (m.id, Told(m.telegram_user_id, m.closing_on))
        for m in members
        if m.closing_on is not None and m.closing_on <= today
    ]
    session.flush()
    now = datetime.now(UTC)
    for user_id, told in due:
        if leave(session, user_id, left, now):
            report.erased.append(told)
    log.info("wind_down.ran", closing=len(report.closing), erased=len(report.erased))
    return report


def day(on: date) -> str:
    return f"{on.day} {on:%B %Y}"


def closing_text(on: date) -> str:
    return (
        f"Training Coach is closing to members. Everything of yours will be erased on {day(on)}. "
        "Until then you can sign in to download your data, or leave now, on the Account page."
    )


ERASED = (
    "As announced, Training Coach has erased everything of yours. Backups age out within 5 weeks."
)


async def run_daily(
    once: Callable[[], Awaitable[object]],
    tz: ZoneInfo,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
) -> None:
    """``once`` every day at ``AT`` local time, until cancelled. A failed day is logged and the
    next day tried again: the loop never stops by itself."""
    while True:
        now = clock()
        await sleep((next_run(now, tz, AT) - now).total_seconds())
        try:
            await once()
        except Exception as exc:  # one bad day mustn't end the wind-down
            log.error("wind_down.failed", error=type(exc).__name__)
