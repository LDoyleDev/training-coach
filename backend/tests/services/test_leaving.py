"""A member leaving (ADR-0088): everything of theirs goes, with no fresh start, and they are put
on the left list first."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select

from training_coach.db.models import Invite, Measurement, PlanState, User
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.services import erase, left_list, users
from training_coach.services.left_list import Left
from training_coach.services.seed import apply_seed, load_plan

JOINED = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
NOW = datetime(2026, 11, 7, 12, tzinfo=UTC)


@pytest.fixture
def member(engine: Engine) -> int:
    """Member 2, with a plan, a measurement and the invite they joined with; the owner too."""
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
        shared.add(User(id=2, role=users.MEMBER, label="Mum", created_at=JOINED))
        shared.flush()
        shared.add(
            Invite(
                token_hash="ab" * 32,
                label="Mum",
                created_by=users.OWNER,
                expires_at=JOINED + timedelta(days=3),
                used_at=JOINED,
                used_by=2,
            )
        )
        apply_seed(shared, load_plan())  # starts them
    for person in (users.OWNER, 2):
        with session_scope(make_session_factory(engine, user_id=person)) as theirs:
            theirs.add(Measurement(local_date=date(2026, 11, 2), kind="waist", tenths=800))
    return 2


def _rows(engine: Engine, model: type[Measurement] | type[PlanState], user: int) -> int:
    with session_scope(make_session_factory(engine)) as shared:
        query = select(func.count()).select_from(model).where(model.user_id == user)
        return shared.scalar(query, execution_options={ALL_USERS: True}) or 0


def test_leaving_takes_everything_of_theirs_and_no_fresh_start(
    engine: Engine, member: int, tmp_path: Path
) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        assert erase.leave(shared, member, tmp_path / left_list.NAME, NOW)
    with session_scope(make_session_factory(engine)) as shared:
        assert shared.get(User, member) is None
        assert shared.scalar(select(func.count()).select_from(Invite)) == 0  # held "Mum"
        assert shared.get(User, users.OWNER) is not None
    assert _rows(engine, Measurement, member) == 0
    assert _rows(engine, PlanState, member) == 0
    assert _rows(engine, Measurement, users.OWNER) == 1  # everyone else's untouched


def test_leaving_puts_them_on_the_left_list(engine: Engine, member: int, tmp_path: Path) -> None:
    path = tmp_path / left_list.NAME
    with session_scope(make_session_factory(engine)) as shared:
        erase.leave(shared, member, path, NOW)
    assert left_list.read(path) == [Left(member, JOINED, NOW)]


def test_a_failed_delete_still_leaves_them_listed(
    engine: Engine, member: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Listed first: a leave that fails half way can only err towards deleting them later."""

    def boom(*_args: object) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(erase, "_delete", boom)
    path = tmp_path / left_list.NAME
    with pytest.raises(RuntimeError), session_scope(make_session_factory(engine)) as shared:
        erase.leave(shared, member, path, NOW)
    assert [e.user_id for e in left_list.read(path)] == [member]
    with session_scope(make_session_factory(engine)) as shared:
        assert shared.get(User, member) is not None  # rolled back


@pytest.mark.parametrize("who", [users.OWNER, 99])
def test_only_a_member_can_leave(engine: Engine, member: int, tmp_path: Path, who: int) -> None:
    """The owner erases instead (ADR-0044); nobody is nothing to do."""
    path = tmp_path / left_list.NAME
    with session_scope(make_session_factory(engine)) as shared:
        assert not erase.leave(shared, who, path, NOW)
    assert left_list.read(path) == []
    with session_scope(make_session_factory(engine)) as shared:
        assert shared.get(User, users.OWNER) is not None


def test_forgetting_deletes_someone_a_restore_put_back(engine: Engine, member: int) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        erase.forget(shared, member)
        erase.forget(shared, 99)  # gone already: nothing to do
    with session_scope(make_session_factory(engine)) as shared:
        assert shared.get(User, member) is None
        assert shared.scalar(select(func.count()).select_from(Invite)) == 0
    assert _rows(engine, Measurement, member) == 0
