"""The list of people who left, outside the database (ADR-0088)."""

import stat
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine

from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import left_list
from training_coach.services.left_list import Left

JOINED = datetime(2026, 11, 1, 9, 30, 15, 123456, tzinfo=UTC)
NOW = datetime(2026, 11, 7, 12, tzinfo=UTC)


def test_an_empty_list_until_someone_leaves(tmp_path: Path) -> None:
    assert left_list.read(tmp_path / left_list.NAME) == []


def test_it_lives_beside_the_database_not_with_the_backups(tmp_path: Path) -> None:
    assert left_list.path_for(tmp_path / "training_coach.db") == tmp_path / left_list.NAME


def test_leaving_is_recorded_to_the_microsecond(tmp_path: Path) -> None:
    path = tmp_path / left_list.NAME
    left_list.record(path, 4, JOINED, NOW)
    left_list.record(path, 5, JOINED + timedelta(days=1), NOW)
    assert left_list.read(path) == [
        Left(4, JOINED, NOW),
        Left(5, JOINED + timedelta(days=1), NOW),
    ]
    assert not list(tmp_path.glob("*.partial"))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_only_the_app_can_read_it(tmp_path: Path) -> None:
    path = tmp_path / left_list.NAME
    left_list.record(path, 4, JOINED, NOW)
    assert stat.S_IMODE(path.stat().st_mode) == left_list.FILE_MODE


def test_an_entry_goes_once_no_backup_can_hold_them(tmp_path: Path) -> None:
    path = tmp_path / left_list.NAME
    left_list.record(path, 4, JOINED, NOW)
    left_list.record(path, 5, JOINED, NOW + left_list.KEEP - timedelta(seconds=1))
    assert [e.user_id for e in left_list.read(path)] == [4, 5]
    left_list.record(path, 6, JOINED, NOW + left_list.KEEP)
    assert [e.user_id for e in left_list.read(path)] == [5, 6]


def test_back_finds_listed_people_a_restore_put_back(engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=4, created_at=JOINED))
    with session_scope(make_session_factory(engine)) as shared:
        assert left_list.back(shared, [Left(4, JOINED, NOW)]) == [4]
        assert left_list.back(shared, []) == []


def test_back_never_takes_someone_new_on_a_left_persons_id(engine: Engine) -> None:
    """A restore resets the next id: someone joining after it can get a left person's id."""
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=4, created_at=JOINED + timedelta(days=3)))
    with session_scope(make_session_factory(engine)) as shared:
        assert left_list.back(shared, [Left(4, JOINED, NOW)]) == []


def test_back_matches_any_of_the_times_an_id_left(engine: Engine) -> None:
    later = JOINED + timedelta(days=2)
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=4, created_at=JOINED))
    entries = [Left(4, JOINED, NOW), Left(4, later, NOW + timedelta(days=3))]
    with session_scope(make_session_factory(engine)) as shared:
        assert left_list.back(shared, entries) == [4]
