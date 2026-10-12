"""Whether band data has stopped reaching the coach (ADR-0055). Pure logic, no I/O.

Two ways it stops: no sync gets through at all (the phone, HC Webhook or the address), or the
syncs get through but carry nothing new (Mi Fitness stopped syncing the band or sharing with
Health Connect). Each gap is told once; when records arrive again after that, it says so once.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

QUIET_FOR = timedelta(hours=24)
# Held until the day starts, so a gap noticed at 3:00 doesn't wake anyone: local wall-clock
# times, so DST doesn't move them.
DAY_STARTS, DAY_ENDS = time(8, 0), time(21, 0)


class Notice(StrEnum):
    QUIET = "quiet"  # no sync got through for a day
    EMPTY = "empty"  # syncs got through, but none took a record for a day
    BACK = "back"  # records arrive again after one of those was sent


@dataclass(frozen=True)
class Seen:
    """What is known about a person's band import: when the secret was made (the clock starts
    there), the last sync that got through, the last that took a record, and when a gap was
    last told (None once data flows again)."""

    created_at: datetime
    last_used_at: datetime | None
    last_taken_at: datetime | None
    alerted_at: datetime | None


def notice(seen: Seen, now: datetime) -> Notice | None:
    """What to tell the person now, if anything."""
    if seen.alerted_at is not None:
        taken = seen.last_taken_at
        return Notice.BACK if taken is not None and taken > seen.alerted_at else None
    if now - (seen.last_used_at or seen.created_at) > QUIET_FOR:
        return Notice.QUIET
    if now - (seen.last_taken_at or seen.created_at) > QUIET_FOR:
        return Notice.EMPTY
    return None


def daytime(now: datetime, tz: ZoneInfo) -> bool:
    """Whether ``now`` is between 08:00 and 21:00 where the person is."""
    return DAY_STARTS <= now.astimezone(tz).time() < DAY_ENDS
