"""Nightly backups (#14, ADR-0010): a backup file that exists is complete, retention only ever
touches nightly files, and a failure is reported instead of killing the loop."""

import asyncio
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from structlog.testing import capture_logs

from tests import factories
from training_coach.db.models import Exercise
from training_coach.db.session import make_engine
from training_coach.services import backup
from training_coach.services.backup import (
    FAILED,
    BackupError,
    back_up,
    create,
    database_path,
    nightly_name,
    prune,
    run_nightly,
)

BERLIN = ZoneInfo("Europe/Berlin")


@pytest.fixture
def live(engine: Engine, session: Session) -> Path:
    """A migrated database in WAL mode with a row only in the WAL so far."""
    factories.exercise(session)
    session.commit()
    path = database_path(str(engine.url))
    assert path is not None
    return path


def _count(path: Path) -> int:
    with closing(sqlite3.connect(path)) as db:
        (count,) = db.execute("SELECT count(*) FROM exercises").fetchone()
    return int(count)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite:////data/training_coach.db", Path("/data/training_coach.db")),
        ("sqlite:///./data/training_coach.db", Path("data/training_coach.db")),
        ("sqlite:///:memory:", None),
        ("sqlite://", None),
        ("postgresql://u@h/db", None),
    ],
)
def test_database_path(url: str, expected: Path | None) -> None:
    assert database_path(url) == expected


def test_a_backup_is_a_complete_standalone_copy(live: Path, tmp_path: Path) -> None:
    out = create(live, tmp_path / "backups", nightly_name(date(2026, 10, 7)))
    assert out.name == "training_coach-2026-10-07.db"
    assert _count(out) == 1  # includes what was still in the live WAL
    with closing(sqlite3.connect(out)) as db:
        assert db.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert sorted(p.name for p in out.parent.iterdir()) == [out.name]  # no partial, no -wal
    if sys.platform != "win32":
        assert out.stat().st_mode & 0o777 == backup.FILE_MODE


def test_a_restored_backup_works_with_the_app(live: Path, tmp_path: Path) -> None:
    """The restore drill, automated: the copy opens under the app's engine with every row."""
    out = create(live, tmp_path / "backups", "restore.db")
    restored = make_engine(f"sqlite:///{out}")
    with Session(restored) as session:
        assert session.scalar(select(func.count()).select_from(Exercise)) == 1
    restored.dispose()


def test_a_missing_database_is_an_error_and_writes_nothing(tmp_path: Path) -> None:
    with pytest.raises(BackupError, match="not found"):
        create(tmp_path / "missing.db", tmp_path / "backups", "x.db")
    assert not (tmp_path / "backups").exists()


def test_a_broken_database_leaves_no_partial_and_keeps_the_old_backup(tmp_path: Path) -> None:
    broken = tmp_path / "broken.db"
    broken.write_bytes(b"not a database at all" * 100)
    folder = tmp_path / "backups"
    folder.mkdir()
    (folder / "x.db").write_bytes(b"yesterday")
    with pytest.raises(BackupError):
        create(broken, folder, "x.db")
    assert sorted(p.name for p in folder.iterdir()) == ["x.db"]
    assert (folder / "x.db").read_bytes() == b"yesterday"


def test_a_failed_integrity_check_is_an_error(
    live: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = sqlite3.connect

    class Corrupt:
        def __init__(self, conn: sqlite3.Connection) -> None:
            self.conn = conn

        def execute(self, sql: str) -> sqlite3.Cursor:
            if sql == "PRAGMA integrity_check":
                return real(":memory:").execute("SELECT 'row 3 missing from index'")
            return self.conn.execute(sql)

        def backup(self, target: object) -> None:
            self.conn.backup(target.conn if isinstance(target, Corrupt) else target)  # type: ignore[arg-type]

        def close(self) -> None:
            self.conn.close()

    monkeypatch.setattr(backup.sqlite3, "connect", lambda path: Corrupt(real(path)))
    with pytest.raises(BackupError, match="integrity"):
        create(live, tmp_path / "backups", "x.db")
    assert list((tmp_path / "backups").iterdir()) == []


def test_prune_touches_only_nightly_files(tmp_path: Path) -> None:
    today = date(2026, 10, 7)
    for n in range(40):
        (tmp_path / nightly_name(today - timedelta(days=n))).write_bytes(b"")
    others = [
        "training_coach-manual-20261001T080000Z.db",
        "training_coach-2026-02-30.db",
        "notes.txt",
        "training_coach.db",
    ]
    for name in others:
        (tmp_path / name).write_bytes(b"")
    assert prune(tmp_path) == 40 - 11
    left = {p.name for p in tmp_path.iterdir()}
    assert set(others) <= left
    assert nightly_name(today) in left
    assert len(left) == 11 + len(others)


async def test_a_failure_is_logged_and_reported_not_raised(tmp_path: Path) -> None:
    told: list[str] = []

    async def notify(text: str) -> None:
        told.append(text)

    with capture_logs() as logs:
        ok = await back_up(tmp_path / "missing.db", tmp_path / "b", date(2026, 10, 7), notify)
    assert ok is False
    assert told == [FAILED]
    assert [e["event"] for e in logs] == ["backup.failed"]


async def test_an_unexpected_error_and_a_failing_notify_do_not_escape(
    live: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_directory: Path) -> int:
        raise RuntimeError("disk on fire")

    async def notify(_text: str) -> None:
        raise ConnectionError("telegram down")

    monkeypatch.setattr(backup, "prune", boom)
    with capture_logs() as logs:
        ok = await back_up(live, tmp_path / "b", date(2026, 10, 7), notify)
    assert ok is False
    assert [e["event"] for e in logs] == ["backup.failed", "backup.notify_failed"]


async def test_success_logs_the_file_and_tells_no_one(live: Path, tmp_path: Path) -> None:
    told: list[str] = []

    async def notify(text: str) -> None:
        told.append(text)

    with capture_logs() as logs:
        assert await back_up(live, tmp_path / "b", date(2026, 10, 7), notify) is True
    assert told == []
    (entry,) = logs
    assert entry["event"] == "backup.created"
    assert entry["file"] == "training_coach-2026-10-07.db"


class StopLoopError(Exception):
    pass


def _clock(*times: datetime):  # type: ignore[no-untyped-def]
    it = iter(times)
    last = times[-1]
    return lambda: next(it, last)


async def test_the_loop_catches_up_then_sleeps_until_half_three(live: Path, tmp_path: Path) -> None:
    folder = tmp_path / "b"
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)
        if len(slept) == 2:
            raise StopLoopError

    noon = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)  # 12:00 in Berlin
    night = datetime(2026, 10, 8, 1, 30, tzinfo=UTC)  # 03:30 the next morning
    clock = _clock(noon, noon, noon, night, night, night)
    with pytest.raises(StopLoopError):
        await run_nightly(live, folder, BERLIN, clock=clock, sleep=sleep)
    assert sorted(p.name for p in folder.iterdir()) == [
        "training_coach-2026-10-07.db",  # caught up: the Pi was off at 03:30
        "training_coach-2026-10-08.db",
    ]
    assert slept[0] == (night - noon).total_seconds()


async def test_no_catch_up_when_today_is_already_backed_up(live: Path, tmp_path: Path) -> None:
    folder = tmp_path / "b"
    folder.mkdir()
    (folder / "training_coach-2026-10-07.db").write_bytes(b"from 03:30")

    async def sleep(_seconds: float) -> None:
        raise StopLoopError

    noon = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)
    with pytest.raises(StopLoopError):
        await run_nightly(live, folder, BERLIN, clock=lambda: noon, sleep=sleep)
    assert (folder / "training_coach-2026-10-07.db").read_bytes() == b"from 03:30"


async def test_the_loop_is_cancelled_cleanly(live: Path, tmp_path: Path) -> None:
    started = asyncio.Event()

    async def sleep(_seconds: float) -> None:
        started.set()
        await asyncio.Event().wait()  # until cancelled

    task = asyncio.create_task(run_nightly(live, tmp_path / "b", BERLIN, sleep=sleep))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
