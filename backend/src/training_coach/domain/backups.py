"""Nightly backup schedule and retention (ADR-0010). Pure logic, no I/O."""

from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DAILY = 7
WEEKLY = 4


def keep(days: Iterable[date], daily: int = DAILY, weekly: int = WEEKLY) -> set[date]:
    """The backups to keep: the newest ``daily``, plus the newest of each of the ``weekly``
    ISO weeks before them. Counted over the backups that exist, not the calendar, so missed
    nights never cost a kept backup and the newest is always kept."""
    ordered = sorted(set(days), reverse=True)
    kept = set(ordered[:daily])
    weeks = {d.isocalendar()[:2] for d in kept}
    older: set[tuple[int, int]] = set()
    for day in ordered[daily:]:
        week = day.isocalendar()[:2]
        if week in weeks or week in older:
            continue
        if len(older) == weekly:
            break
        older.add(week)
        kept.add(day)
    return kept


def next_run(now: datetime, tz: ZoneInfo, at: time) -> datetime:
    """The next ``at`` in local time, as UTC. Strictly after ``now``; safe across DST changes
    because the local time is resolved per day."""
    today = now.astimezone(tz).date()
    candidate = datetime.combine(today, at, tzinfo=tz).astimezone(UTC)
    if candidate > now:
        return candidate
    return datetime.combine(today + timedelta(days=1), at, tzinfo=tz).astimezone(UTC)
