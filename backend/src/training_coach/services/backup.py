"""Nightly SQLite backups (ADR-0010, ADR-0024, phase 1 step 1-H).

``create`` copies the live database with SQLite's online backup API (safe while the app
writes), checks the copy's integrity and only then renames it into place, so a backup file
that exists is a complete one. ``prune`` applies the retention in ``domain.backups`` and only
ever deletes files matching the nightly or manual names it writes: other files are left alone.
``run_nightly`` is started by the app's lifespan, whether or not the bot is on.
"""

import asyncio
import os
import re
import sqlite3
from collections.abc import Awaitable, Callable
from contextlib import closing
from datetime import UTC, date, datetime, time
from pathlib import Path
from time import time as time_now
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.engine import make_url

from training_coach.domain.backups import keep, manual_expired, next_run

log = structlog.get_logger(__name__)

AT = time(3, 30)  # local; quiet, and clear of the DST jumps at 02:00-03:00
NIGHTLY = re.compile(r"^training_coach-(\d{4}-\d{2}-\d{2})\.db$")
MANUAL = re.compile(r"^training_coach-manual-(\d{8}T\d{6}Z)\.db$")
FILE_MODE = 0o640  # owner and the app group only: the copy holds the same data as the live db
DIR_MODE = 0o750
STALE_PARTIAL = 3600  # seconds: older partials were left by a killed run, not one in progress
FAILED = (
    "The nightly backup failed. Your data is fine, but there is no fresh copy; "
    "check the app logs for backup.failed."
)

Notify = Callable[[str], Awaitable[object]]


class BackupError(Exception):
    """The copy could not be made or failed its integrity check. Nothing was replaced."""


def database_path(database_url: str) -> Path | None:
    """The SQLite file behind ``database_url``; None for in-memory or non-SQLite databases."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        return None
    return Path(url.database)


def nightly_name(day: date) -> str:
    return f"training_coach-{day.isoformat()}.db"


def manual_name(now: datetime) -> str:
    return f"training_coach-manual-{now.astimezone(UTC):%Y%m%dT%H%M%SZ}.db"


def create(source: Path, directory: Path, name: str) -> Path:
    """Copy ``source`` to ``directory/name``. Raises ``BackupError``; never leaves a partial."""
    if not source.is_file():
        raise BackupError("database file not found")
    final = directory / name
    partial = directory / f".{name}.partial"
    try:
        directory.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
        directory.chmod(DIR_MODE)  # mkdir leaves an existing directory's mode alone
        partial.unlink(missing_ok=True)
        # Private from the first byte: sqlite would create it with the process umask, and a
        # run killed mid-copy would leave it that way. Its journal inherits this mode.
        os.close(os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600))
        with closing(sqlite3.connect(source)) as live, closing(sqlite3.connect(partial)) as copy:
            live.backup(copy)
            # One self-contained file: no -wal/-shm beside it. The app turns WAL back on.
            copy.execute("PRAGMA journal_mode=DELETE")
            (result,) = copy.execute("PRAGMA integrity_check").fetchone()
        if result != "ok":
            raise BackupError("integrity check failed")
        partial.chmod(FILE_MODE)
        os.replace(partial, final)
    except (sqlite3.Error, OSError) as exc:
        raise BackupError(type(exc).__name__) from exc
    finally:
        partial.unlink(missing_ok=True)
    return final


def nightly_days(directory: Path) -> dict[date, Path]:
    found = {}
    for path in directory.glob("training_coach-*.db"):
        match = NIGHTLY.match(path.name)
        if match is None:
            continue
        try:
            found[date.fromisoformat(match.group(1))] = path
        except ValueError:  # a name like 2026-02-30: not ours to judge, leave it alone
            continue
    return found


def prune(directory: Path, now: float | None = None) -> int:
    """Delete nightly and manual backups outside the retention, and partial copies left by a
    killed run. Returns how many backups were removed."""
    clock = time_now() if now is None else now
    cutoff = clock - STALE_PARTIAL
    for leftover in directory.glob(".training_coach-*.partial*"):
        try:
            if leftover.stat().st_mtime < cutoff:
                leftover.unlink(missing_ok=True)
        except FileNotFoundError:  # finished or cleaned up meanwhile
            continue
    days = nightly_days(directory)
    kept = keep(days)
    removed = 0
    for day, path in days.items():
        if day not in kept:
            path.unlink(missing_ok=True)
            removed += 1
    moment = datetime.fromtimestamp(clock, UTC)
    for path in directory.glob("training_coach-manual-*.db"):
        match = MANUAL.match(path.name)
        if match is None:
            continue
        # Its name says when it was taken, which a copy or a restore can't change.
        taken = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        if manual_expired(taken, moment):
            path.unlink(missing_ok=True)
            removed += 1
    return removed


async def back_up(source: Path, directory: Path, today: date, notify: Notify | None) -> bool:
    """One nightly backup and prune. Failures are logged and reported, never raised: a
    crashed loop would mean no backups and no word about it."""
    try:
        path = await asyncio.to_thread(create, source, directory, nightly_name(today))
    except BackupError as exc:
        log.error("backup.failed", reason=str(exc))
    except Exception:
        log.exception("backup.failed", reason="unexpected")
    else:
        log.info("backup.created", file=path.name)
        # The fresh copy stands either way: a failed prune is worth a log line, not an alarm.
        try:
            removed = await asyncio.to_thread(prune, directory)
        except Exception:
            log.exception("backup.prune_failed")
        else:
            log.info("backup.pruned", removed=removed)
        return True
    if notify is not None:
        try:
            await notify(FAILED)
        except Exception:
            log.exception("backup.notify_failed")
    return False


async def run_nightly(
    source: Path,
    directory: Path,
    tz: ZoneInfo,
    notify: Notify | None = None,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
) -> None:
    """Back up now if today has no backup yet (the Pi may have been off at 03:30), then
    every night at ``AT`` local time. Runs until cancelled."""
    today = clock().astimezone(tz).date()
    if today not in nightly_days(directory):
        await _back_up_unless_clock_behind(source, directory, today, notify)
    while True:
        now = clock()
        await sleep((next_run(now, tz, AT) - now).total_seconds())
        today = clock().astimezone(tz).date()
        await _back_up_unless_clock_behind(source, directory, today, notify)


async def _back_up_unless_clock_behind(
    source: Path, directory: Path, today: date, notify: Notify | None
) -> None:
    """A Pi without a clock battery can boot with a stale date until NTP syncs. A "today"
    older than the newest backup means the clock is wrong: don't name a backup after it."""
    newest = max(nightly_days(directory), default=None)
    if newest is not None and today < newest:
        log.warning("backup.skipped", reason="clock behind the newest backup")
        return
    await back_up(source, directory, today, notify)
