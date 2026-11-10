"""A person editing their own plan (builder step 6): nothing changes until Save, then one version,
and only what the app couldn't run is refused."""

from collections.abc import Callable
from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests import factories
from tests.services.test_seed import MINI_PLAN
from training_coach.db.models import (
    PlanVersion,
    SessionProgress,
    SessionTemplate,
    TemplateItem,
    User,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import Place
from training_coach.services import plan_edit
from training_coach.services.plan_edit import ItemEdit, VersionEdit
from training_coach.services.seed import PlanSeed, apply_seed, load_plan

TODAY = date(2026, 11, 7)
PULL = ItemEdit("pull-up", 4, 5, 12)
DIP = ItemEdit("dip", 3, 8, 15)


@pytest.fixture
def plan(session: Session) -> PlanSeed:
    seeded = load_plan(MINI_PLAN)
    apply_seed(session, seeded)
    session.commit()
    return seeded


def _save(
    session: Session,
    plan: PlanSeed,
    *items: ItemEdit,
    slug: str = "upper",
    place: Place = Place.HOME,
) -> plan_edit.Saved | str:
    edit = VersionEdit(slug, place, tuple(items))
    return plan_edit.save(session, [edit], "More sets", plan_edit.revision(session), plan, TODAY)


def _upper(session: Session) -> SessionTemplate:
    return session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "upper")).one()


def test_save_changes_the_version_and_makes_one_plan_version(
    session: Session, plan: PlanSeed
) -> None:
    before = plan_edit.revision(session)
    saved = _save(session, plan, ItemEdit("pull-up", 5, 6, 10), DIP)
    session.commit()
    assert isinstance(saved, plan_edit.Saved)
    assert saved.version == "More sets"
    assert saved.revision != before
    assert saved.revision == plan_edit.revision(session)
    upper = _upper(session)
    assert [(i.exercise.slug, i.sets, i.rep_min, i.rep_max) for i in upper.items] == [
        ("pull-up", 5, 6, 10),
        ("dip", 3, 8, 15),
    ]
    today = session.scalars(select(PlanVersion).where(PlanVersion.since == TODAY)).all()
    assert [v.name for v in today] == ["More sets"]


def test_a_second_save_that_day_adds_to_its_version(session: Session, plan: PlanSeed) -> None:
    _save(session, plan, ItemEdit("pull-up", 5, 5, 12))
    session.commit()
    edit = VersionEdit("upper", Place.HOME, (ItemEdit("pull-up", 6, 5, 12),))
    saved = plan_edit.save(session, [edit], "Even more", plan_edit.revision(session), plan, TODAY)
    session.commit()
    today = session.scalars(select(PlanVersion).where(PlanVersion.since == TODAY)).all()
    assert [v.name for v in today] == ["More sets; Even more"]
    assert isinstance(saved, plan_edit.Saved)
    assert saved.version == "More sets; Even more"


@pytest.mark.parametrize(
    ("earlier", "note", "name"),
    [
        ("Imported from plan.toml", "Fewer dips", "Imported from plan.toml; Fewer dips"),
        ("Fewer dips", "Fewer dips", "Fewer dips"),
        ("x" * 110, "Fewer dips", "Fewer dips"),  # past what the name holds: the newest
    ],
)
def test_a_days_version_keeps_what_it_said(
    session: Session, plan: PlanSeed, earlier: str, note: str, name: str
) -> None:
    session.add(PlanVersion(since=TODAY, name=earlier))
    session.flush()
    edit = VersionEdit("upper", Place.HOME, (ItemEdit("pull-up", 6, 5, 12),))
    plan_edit.save(session, [edit], note, plan_edit.revision(session), plan, TODAY)
    session.flush()
    today = session.scalars(select(PlanVersion).where(PlanVersion.since == TODAY)).all()
    assert [v.name for v in today] == [name]


def test_an_exercise_the_seed_has_not_loaded_is_refused(session: Session, plan: PlanSeed) -> None:
    """plan.toml has it, but the seed failed on it: refused in words, not a server error."""
    new = plan.exercises[0].model_copy(update={"slug": "new-move"})
    bigger = plan.model_copy(update={"exercises": [*plan.exercises, new]})
    found = _save(session, bigger, ItemEdit("new-move", 3, 5, 12))
    assert found == "new-move isn't in the catalogue."
    assert _upper(session).items[0].sets == 4


def test_saving_what_is_already_there_makes_no_version(session: Session, plan: PlanSeed) -> None:
    saved = _save(session, plan, PULL)
    assert isinstance(saved, plan_edit.Saved)
    assert saved.version is None
    assert session.scalars(select(PlanVersion).where(PlanVersion.since == TODAY)).all() == []


def test_a_draft_of_an_older_plan_is_refused(session: Session, plan: PlanSeed) -> None:
    old = plan_edit.revision(session)
    _save(session, plan, ItemEdit("pull-up", 5, 5, 12))
    session.commit()
    edit = VersionEdit("upper", Place.HOME, (ItemEdit("pull-up", 9, 5, 12),))
    assert plan_edit.save(session, [edit], "Late", old, plan, TODAY) == plan_edit.STALE
    assert _upper(session).items[0].sets == 5


def test_a_session_in_progress_is_refused_unchanged(session: Session, plan: PlanSeed) -> None:
    kept = [{"item": 0, "set_no": 1, "left": 8}]
    session.add(
        SessionProgress(
            local_date=TODAY, template_id=_upper(session).id, token="ab" * 16, sets=kept
        )
    )
    session.commit()
    assert _save(session, plan, ItemEdit("pull-up", 5, 5, 12)) == plan_edit.IN_PROGRESS
    assert _upper(session).items[0].sets == 4


@pytest.mark.parametrize(
    ("items", "place", "message"),
    [
        ((), Place.HOME, "at least one"),
        ((ItemEdit("no-such", 3, 8, 12),), Place.HOME, "isn't in the catalogue"),
        ((ItemEdit("pull-up", 3, 12, 8),), Place.HOME, "low first"),
        ((ItemEdit("pull-up", 3, 8, 12, pair=1), DIP), Place.HOME, "neighbouring"),
    ],
    ids=["empty", "unknown", "range", "pair"],
)
def test_what_the_app_couldnt_run_is_refused_unchanged(
    session: Session, plan: PlanSeed, items: tuple[ItemEdit, ...], place: Place, message: str
) -> None:
    found = _save(session, plan, *items, place=place)
    assert isinstance(found, str)
    assert message in found
    assert _upper(session).items[0].sets == 4


def test_an_exercise_outside_its_place_is_refused(session: Session) -> None:
    gym_only = MINI_PLAN.replace(
        'ladder = ["Negatives", "Strict", "Weighted"]',
        'ladder = ["Negatives", "Strict", "Weighted"]\n[exercises.loads]\nStrict = "machine"',
    )
    seeded = load_plan(gym_only)
    apply_seed(session, seeded)
    session.commit()
    moved = _save(session, seeded, DIP, PULL, place=Place.HOME)
    assert moved == "Pull-up can't be done at home."
    away = _save(session, seeded, PULL, place=Place.AWAY)
    assert away == "Pull-up can't be done away."
    gym = _save(session, seeded, PULL, place=Place.GYM)
    assert isinstance(gym, plan_edit.Saved)


def test_the_bundled_plan_is_within_the_places_it_could_be_edited_at() -> None:
    plan = load_plan()
    catalogue = {e.slug: e for e in plan.exercises}
    for planned in plan.sessions:
        for place, items in ((Place.HOME, planned.items), (Place.AWAY, planned.away)):
            for item in items:
                assert place in plan_edit.places_for(catalogue[item.exercise]), item.exercise


def test_an_empty_gym_version_means_the_same_at_the_gym(session: Session, plan: PlanSeed) -> None:
    _save(session, plan, DIP, place=Place.GYM)
    session.commit()
    assert [i.exercise.slug for i in _upper(session).gym_items] == ["dip"]
    _save(session, plan, place=Place.GYM)
    session.commit()
    session.expire_all()
    assert _upper(session).gym_items == []


def test_an_unknown_session_is_refused(session: Session, plan: PlanSeed) -> None:
    found = _save(session, plan, PULL, slug="nope")
    assert found == "nope isn't one of your sessions."


def test_warnings_stay_warnings(session: Session, plan: PlanSeed) -> None:
    assert isinstance(_save(session, plan, ItemEdit("pull-up", 20, 1, 100)), plan_edit.Saved)


def test_my_edit_is_mine(engine: Engine) -> None:
    seeded = load_plan(MINI_PLAN)
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
        shared.flush()
        apply_seed(shared, seeded)
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        assert isinstance(_save(theirs, seeded, ItemEdit("pull-up", 9, 5, 12)), plan_edit.Saved)
    with session_scope(make_session_factory(engine, user_id=1)) as mine:
        assert 9 not in set(mine.scalars(select(TemplateItem.sets)))
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        assert 9 in set(theirs.scalars(select(TemplateItem.sets)))


def _arms(session: Session) -> SessionTemplate:
    return session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "arms")).one()


@pytest.mark.parametrize(
    "change",
    [
        lambda s, t: setattr(t, "name", "Arms 2"),
        lambda s, t: setattr(t, "kind", "recovery"),
        lambda s, t: setattr(t, "rest_after", 1),
        lambda s, t: factories.retire(s, t, TODAY),
    ],
    ids=["name", "kind", "rest days", "retired"],
)
def test_the_revision_follows_a_sessions_name_kind_rest_days_and_retiring(
    session: Session, plan: PlanSeed, change: Callable[[Session, SessionTemplate], None]
) -> None:
    """So a draft opened before the cycle changed is stale (ADR-0093)."""
    before = plan_edit.revision(session)
    change(session, _arms(session))
    session.flush()
    assert plan_edit.revision(session) != before


def test_a_retired_session_is_not_edited(session: Session, plan: PlanSeed) -> None:
    factories.retire(session, _arms(session), TODAY)
    assert [s.slug for s in plan_edit.editable(session)] == ["upper"]
    edit = VersionEdit("arms", Place.HOME, (DIP,))
    found = plan_edit.save(session, [edit], "Back", plan_edit.revision(session), plan, TODAY)
    assert isinstance(found, str)
    assert "isn't one of your sessions" in found
