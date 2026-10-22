"""Whether band data has stopped reaching the coach (ADR-0055). Pure logic, no I/O.

Two ways it stops: no sync gets through at all (the phone, HC Webhook or the address), or the
syncs get through but carry nothing new (Mi Fitness stopped syncing the band or sharing with
Health Connect). Each gap is told once; when records arrive again after that, it says so once.

A third, while data does flow: one kind a worn band gives every day (steps, sleep, heart rate)
stops while the others come, as when HC Webhook drops a type it can't read in time. Each kind
is watched on its own over two days, so one night without the band isn't a gap, and told once
per gap the same way; never while a gap in all band data is open, which says it already.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

QUIET_FOR = timedelta(hours=24)
KIND_QUIET_FOR = timedelta(hours=48)
# Held until the day starts, so a gap noticed at 3:00 doesn't wake anyone: local wall-clock
# times, so DST doesn't move them.
DAY_STARTS, DAY_ENDS = time(8, 0), time(21, 0)


class Feed(StrEnum):
    """The kinds of band data that come every day the band is worn, by their key in a sync.
    Workouts and weight come when they happen, so a gap in them means nothing."""

    STEPS = "steps"
    SLEEP = "sleep"
    HEART_RATE = "heart_rate"


class Refusal(StrEnum):
    """Why a sync that carried a known secret stored nothing, kept so Account can show it. A
    wrong secret or a rate limit comes before the secret is known, so isn't kept: it could be
    anyone's."""

    TOO_LARGE = "too_large"  # over the 5 MB cap
    NOT_JSON = "not_json"  # not a JSON object
    FAILED = "failed"  # the coach couldn't store it; the phone sends it again
    SKIPPED = "skipped"  # it got through, but every record in it was left out


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


@dataclass(frozen=True)
class FeedSeen:
    """The last sync that took a record of one kind, and when its gap was last told."""

    last_taken_at: datetime | None = None
    alerted_at: datetime | None = None


@dataclass(frozen=True)
class FeedNotices:
    stopped: tuple[Feed, ...] = ()  # a gap that began
    back: tuple[Feed, ...] = ()  # records again after its gap was told

    def __bool__(self) -> bool:
        return bool(self.stopped or self.back)


def feed_notices(seen: Seen, feeds: dict[Feed, FeedSeen], now: datetime) -> FeedNotices:
    """Which kinds to tell the person about now. Nothing while a gap in all band data is due
    or told: that message covers every kind, and a kind still missing after it ends is told
    then. A kind never seen counts from when the secret was made."""
    if seen.alerted_at is not None or notice(seen, now) is not None:
        return FeedNotices()
    stopped: list[Feed] = []
    back: list[Feed] = []
    for feed in Feed:
        found = feeds.get(feed, FeedSeen())
        taken = found.last_taken_at
        if found.alerted_at is not None:
            if taken is not None and taken > found.alerted_at:
                back.append(feed)
        elif now - (taken or seen.created_at) > KIND_QUIET_FOR:
            stopped.append(feed)
    return FeedNotices(tuple(stopped), tuple(back))


def daytime(now: datetime, tz: ZoneInfo) -> bool:
    """Whether ``now`` is between 08:00 and 21:00 where the person is."""
    return DAY_STARTS <= now.astimezone(tz).time() < DAY_ENDS
