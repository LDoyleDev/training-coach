"""User ids are never handed out twice (ADR-0088 addendum): what is still kept by a left person's
id outside the database (the bot's drafts, later scheduled jobs) must never reach someone new.
The migration that gives ``users`` AUTOINCREMENT keeps every row, and starts the counter above
anyone in the left list."""

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, select, text

from training_coach.db.models import LoginLink, Measurement, User
from training_coach.db.session import make_engine, make_session_factory, session_scope
from training_coach.services import auth, telegram_link, users
from training_coach.services.erase import erase, leave
from training_coach.services.seed import apply_seed, load_plan

BACKEND = Path(__file__).resolve().parents[2]
BEFORE = "e7b9d1f3a5c8"  # the revision before users got AUTOINCREMENT


def _join(engine: Engine) -> int:
    with session_scope(make_session_factory(engine)) as shared:
        person = User(role=users.MEMBER)
        shared.add(person)
        shared.flush()
        return person.id


def _leave(engine: Engine, user_id: int) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        assert leave(shared, user_id, None, datetime.now(UTC))


def test_the_users_table_never_reuses_an_id(engine: Engine) -> None:
    with engine.connect() as connection:
        ddl = connection.execute(text("SELECT sql FROM sqlite_master WHERE name = 'users'"))
        assert "AUTOINCREMENT" in ddl.scalar_one()


def test_a_new_joiner_never_gets_the_id_of_the_newest_who_left(engine: Engine) -> None:
    first, newest = _join(engine), _join(engine)
    _leave(engine, newest)
    assert _join(engine) == newest + 1
    _leave(engine, first)
    assert _join(engine) == newest + 2


@pytest.fixture
def before(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Config, Path]]:
    """A database file migrated to just before AUTOINCREMENT."""
    from training_coach.config import get_settings

    database = tmp_path / "ids.db"
    monkeypatch.setenv("TC_DATABASE_URL", f"sqlite:///{database}")
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, BEFORE)
    yield cfg, database
    get_settings.cache_clear()


def _members(database: Path, ids: list[int], gone: list[int]) -> None:
    """Members by id, then those in ``gone`` deleted, as SQLite left things before the fix."""
    with sqlite3.connect(database) as raw:
        for user_id in ids:
            raw.execute(
                "INSERT INTO users (id, created_at, last_seen_in_europe, role)"
                " VALUES (?, '2026-11-01 10:00:00', '2026-11-01 10:00:00', 'member')",
                (user_id,),
            )
        raw.executemany("DELETE FROM users WHERE id = ?", [(g,) for g in gone])


def _left_list(database: Path, ids: list[int]) -> None:
    entries = [
        {"id": i, "joined": "2026-11-01T10:00:00+00:00", "left": "2026-11-02T10:00:00+00:00"}
        for i in ids
    ]
    (database.parent / "left-users.json").write_text(json.dumps(entries), encoding="utf-8")


def _next_id(database: Path) -> int:
    engine = make_engine(f"sqlite:///{database}")
    try:
        return _join(engine)
    finally:
        engine.dispose()


def test_an_id_that_left_before_the_migration_is_never_handed_out(
    before: tuple[Config, Path],
) -> None:
    cfg, database = before
    _members(database, [2, 3, 4], gone=[3, 4])  # the newest two left, listed by the app
    _left_list(database, [3, 4])
    command.upgrade(cfg, "head")
    assert _next_id(database) == 5


@pytest.mark.parametrize("listed", [None, "", "[]"])
def test_without_anyone_listed_the_counter_starts_at_the_highest_id(
    before: tuple[Config, Path], listed: str | None
) -> None:
    cfg, database = before
    if listed is not None:
        (database.parent / "left-users.json").write_text(listed, encoding="utf-8")
    _members(database, [2, 3], gone=[])
    command.upgrade(cfg, "head")
    assert _next_id(database) == 4


def test_an_unreadable_left_list_stops_the_migration(before: tuple[Config, Path]) -> None:
    cfg, database = before
    (database.parent / "left-users.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="can't be read"):
        command.upgrade(cfg, "head")
    with sqlite3.connect(database) as raw:  # nothing changed: users still as it was
        (ddl,) = raw.execute("SELECT sql FROM sqlite_master WHERE name = 'users'").fetchone()
    assert "AUTOINCREMENT" not in ddl


def _counts(database: Path) -> dict[str, int]:
    with sqlite3.connect(database) as raw:
        tables = [
            name
            for (name,) in raw.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
                " AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
            )
        ]
        # Table names straight from sqlite_master, not from input.
        count = 'SELECT count(*) FROM "{}"'
        return {t: raw.execute(count.format(t)).fetchone()[0] for t in tables}


def test_the_rebuild_keeps_every_row_and_the_cascades(before: tuple[Config, Path]) -> None:
    """On a database with people and their rows: the same rows after, nothing dangling, leaving
    still takes everything of theirs, and erase can still put its person back on their id."""
    cfg, database = before
    engine = make_engine(f"sqlite:///{database}")
    now = datetime.now(UTC)
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
        shared.add_all([User(id=2, role=users.MEMBER), User(id=3, role=users.MEMBER)])
        shared.flush()
        apply_seed(shared, load_plan())
    for person in (users.OWNER, 2, 3):
        with session_scope(make_session_factory(engine, user_id=person)) as theirs:
            theirs.add(Measurement(local_date=date(2026, 11, 2), kind="waist", tenths=800))
            auth.create_link(theirs, now)
            telegram_link.make(theirs, now)
    engine.dispose()
    rows = _counts(database)
    command.upgrade(cfg, "head")
    assert _counts(database) == rows
    with sqlite3.connect(database) as raw:
        assert raw.execute("PRAGMA foreign_key_check").fetchall() == []
    engine = make_engine(f"sqlite:///{database}")
    try:
        _leave(engine, 3)
        with session_scope(make_session_factory(engine, user_id=3)) as gone:
            assert gone.scalars(select(Measurement)).all() == []
            assert gone.scalars(select(LoginLink)).all() == []
        with session_scope(make_session_factory(engine)) as shared:
            assert erase(shared, 2, load_plan())
            assert shared.get(User, 2) is not None
        with session_scope(make_session_factory(engine, user_id=2)) as fresh:
            assert fresh.scalars(select(Measurement)).all() == []
        assert _join(engine) == 4
    finally:
        engine.dispose()


def test_the_downgrade_takes_autoincrement_away(before: tuple[Config, Path]) -> None:
    cfg, database = before
    command.upgrade(cfg, "head")
    command.downgrade(cfg, BEFORE)
    with sqlite3.connect(database) as raw:
        (ddl,) = raw.execute("SELECT sql FROM sqlite_master WHERE name = 'users'").fetchone()
        assert "AUTOINCREMENT" not in ddl
        assert raw.execute("SELECT * FROM sqlite_sequence WHERE name = 'users'").fetchall() == []
