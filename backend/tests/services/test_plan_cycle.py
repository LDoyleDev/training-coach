"""A person's own cycle saved with their plan (ADR-0093): sessions added, copied, renamed, given
another kind or rest days, moved and removed, in one transaction with the versions, the queue
moved with them, and a notice when the cycle changed."""

from collections.abc import Sequence
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests import factories
from tests.services.test_seed import MINI_PLAN
from training_coach.db.models import (
    Event,
    PlanNotice,
    PlanVersion,
    SessionProgress,
    SessionTemplate,
    TemplateItem,
    Workout,
)
from training_coach.domain.enums import Place, WorkoutStatus
from training_coach.services import plan_edit, users
from training_coach.services.plan_edit import Added, ItemEdit, Kept, VersionEdit
from training_coach.services.seed import PlanSeed, apply_seed, load_plan

TODAY = date(2026, 11, 10)
PULL = ItemEdit("pull-up", 4, 5, 12)
DIP = ItemEdit("dip", 3, 8, 15)
ALIASED = MINI_PLAN.replace('name = "Dip"', 'name = "Dip"\naliases = ["bar dips"]')


@pytest.fixture
def plan(session: Session) -> PlanSeed:
    seeded = load_plan(ALIASED)
    apply_seed(session, seeded)
    session.commit()
    return seeded


@pytest.fixture
def bundled(session: Session) -> PlanSeed:
    """The owner's 7-session cycle, no rest places."""
    seeded = load_plan()
    apply_seed(session, seeded)
    session.commit()
    return seeded


def _cycle(session: Session) -> list[Kept | Added]:
    return [Kept(t.slug, t.name, t.kind, t.rest_after) for t in plan_edit.templates(session)]


def _save(
    session: Session,
    plan: PlanSeed,
    cycle: Sequence[Kept | Added] | None,
    *edits: VersionEdit,
    note: str = "Cycle",
) -> plan_edit.Saved | str:
    revision = plan_edit.revision(session)
    found = plan_edit.save(session, list(edits), note, revision, plan, TODAY, cycle)
    session.commit()
    return found


def _new(*items: ItemEdit, key: str = "n1") -> VersionEdit:
    return VersionEdit(f"new:{key}", Place.HOME, items)


def _row(session: Session, slug: str) -> SessionTemplate:
    return session.scalars(select(SessionTemplate).where(SessionTemplate.slug == slug)).one()


def _live(session: Session) -> list[tuple[int, str]]:
    return [(t.position, t.slug) for t in plan_edit.templates(session)]


def _pointer(session: Session) -> tuple[int | None, list[int]]:
    state = users.plan_state(session)
    assert state is not None
    return state.next_template_id, state.queued


def _notices(session: Session) -> list[str]:
    return list(session.scalars(select(PlanNotice.text).order_by(PlanNotice.id)))


def _events(session: Session) -> list[dict[str, int]]:
    query = select(Event.payload).where(Event.kind == plan_edit.CYCLE_CHANGED)
    return list(session.scalars(query))


def test_without_a_cycle_an_item_edit_writes_no_notice_or_cycle_event(
    session: Session, plan: PlanSeed
) -> None:
    saved = _save(session, plan, None, VersionEdit("upper", Place.HOME, (DIP,)))
    assert isinstance(saved, plan_edit.Saved)
    assert saved.slugs == {}
    assert _notices(session) == []
    assert _events(session) == []


def test_an_item_edit_with_the_cycle_as_it_was_writes_no_notice(
    session: Session, plan: PlanSeed
) -> None:
    saved = _save(session, plan, _cycle(session), VersionEdit("upper", Place.HOME, (DIP,)))
    assert isinstance(saved, plan_edit.Saved)
    assert saved.version == "Cycle"
    assert _notices(session) == []
    assert _events(session) == []


def test_the_cycle_as_it_was_and_no_edits_makes_no_version(
    session: Session, plan: PlanSeed
) -> None:
    before = plan_edit.revision(session)
    saved = _save(session, plan, _cycle(session))
    assert saved == plan_edit.Saved(before, None)
    assert session.scalars(select(PlanVersion).where(PlanVersion.since == TODAY)).all() == []


def test_an_empty_session_added_with_its_exercises_in_one_save(
    session: Session, plan: PlanSeed
) -> None:
    cycle = [*_cycle(session), Added("n1", "Back day", "strength", 0)]
    saved = _save(session, plan, cycle, _new(PULL))
    assert isinstance(saved, plan_edit.Saved)
    assert saved.slugs == {"n1": "back-day"}
    assert saved.revision == plan_edit.revision(session)
    new = _row(session, "back-day")
    assert (new.position, new.name, new.kind, new.rest_after) == (2, "Back day", "strength", 0)
    assert new.focus == "Lats, biceps"  # its two most-trained muscles, in words
    assert new.is_rest_optional is False
    assert [i.exercise.slug for i in new.items] == ["pull-up"]
    assert new.gym_items == []
    assert new.away_items == []
    assert _live(session) == [(0, "upper"), (1, "arms"), (2, "back-day")]
    versions = session.scalars(select(PlanVersion).where(PlanVersion.since == TODAY)).all()
    assert [v.name for v in versions] == ["Cycle"]
    assert _events(session) == [{"added": 1, "removed": 0, "retired": 0, "moved": 0}]
    assert _notices(session) == ["Your plan changed: added Back day. Next is Upper."]


def test_an_empty_session_working_no_muscle_takes_its_kinds_word(
    session: Session, plan: PlanSeed
) -> None:
    plain = plan.model_copy(
        update={"exercises": [e.model_copy(update={"muscles": {}}) for e in plan.exercises]}
    )
    _save(session, plain, [*_cycle(session), Added("n1", "Easy", "conditioning", 0)], _new(DIP))
    assert _row(session, "easy").focus == "Cardio"


def test_a_copy_keeps_every_version_its_focus_and_optional_flag(
    session: Session, plan: PlanSeed
) -> None:
    _save(session, plan, None, VersionEdit("arms", Place.GYM, (DIP, PULL)))
    _save(session, plan, None, VersionEdit("arms", Place.AWAY, (DIP,)))
    cycle = [*_cycle(session), Added("n1", "Arms 2", "recovery", 1, copy_of="arms")]
    saved = _save(session, plan, cycle)
    assert isinstance(saved, plan_edit.Saved)
    copy, arms = _row(session, "arms-2"), _row(session, "arms")
    assert (copy.focus, copy.is_rest_optional, copy.kind) == (arms.focus, True, "recovery")
    for place in Place:
        mine, theirs = copy.version(place), arms.version(place)
        assert [(i.exercise_id, i.sets) for i in mine] == [(i.exercise_id, i.sets) for i in theirs]
    assert {i.template_id for i in copy.items} == {copy.id}  # its own rows, not arms'


def test_a_copy_can_be_edited_in_the_same_save(session: Session, plan: PlanSeed) -> None:
    cycle = [*_cycle(session), Added("n1", "Arms 2", "strength", 0, copy_of="arms")]
    _save(session, plan, cycle, _new(PULL))
    assert [i.exercise.slug for i in _row(session, "arms-2").items] == ["pull-up"]
    assert [i.exercise.slug for i in _row(session, "arms").items] == ["dip"]


def test_the_owners_seven_sessions_gain_an_eighth_which_is_next(
    session: Session, bundled: PlanSeed
) -> None:
    """Added straight after the session done last, before the pointer's: next (Decided 9)."""
    legs, recovery = _row(session, "legs"), _row(session, "recovery")
    session.add(Workout(local_date=TODAY - timedelta(days=1), template_id=legs.id, status="done"))
    state = users.plan_state(session)
    assert state is not None
    state.next_template_id = recovery.id
    session.commit()
    cycle = _cycle(session)
    cycle.insert(1, Added("n1", "Legs 2", "strength", 0, copy_of="legs"))
    saved = _save(session, bundled, cycle, note="Added Legs 2")
    assert isinstance(saved, plan_edit.Saved)
    assert saved.slugs == {"n1": "legs-2"}
    slugs = [s for _, s in _live(session)]
    assert slugs == [
        "legs",
        "legs-2",
        "recovery",
        "torso",
        "moderate-cardio",
        "hiit",
        "arms",
        "zone2",
    ]
    assert [p for p, _ in _live(session)] == list(range(8))
    assert _pointer(session) == (_row(session, "legs-2").id, [])
    assert _notices(session) == ["Your plan changed: added Legs 2. Next is Legs 2."]


def test_a_new_sessions_slug_is_never_a_starters_nor_a_retired_ones(
    session: Session, bundled: PlanSeed
) -> None:
    factories.retire(session, _row(session, "arms"), TODAY - timedelta(days=3))
    session.commit()
    cycle = [
        *_cycle(session),
        Added("n1", "Three days A", "strength", 0, copy_of="legs"),
        Added("n2", "Arms", "strength", 0, copy_of="torso"),  # a retired name can be used again
        Added("n3", "Bänder & Co!", "strength", 0, copy_of="torso"),
    ]
    saved = _save(session, bundled, cycle)
    assert isinstance(saved, plan_edit.Saved)
    assert saved.slugs == {"n1": "three-days-a-2", "n2": "arms-2", "n3": "bander-co"}


def test_a_long_name_makes_a_slug_of_at_most_64() -> None:
    taken = {"a" * 64}
    assert plan_edit._slug("a" * 70, taken) == "a" * 62 + "-2"
    assert plan_edit._slug("!!!", taken) == "session"


def test_the_pointers_session_removed_with_nothing_logged_goes_and_next_moves_on(
    session: Session, plan: PlanSeed
) -> None:
    upper, arms = _row(session, "upper"), _row(session, "arms")
    session.add(
        SessionProgress(local_date=TODAY - timedelta(days=2), template_id=upper.id, token="ab" * 16)
    )
    state = users.plan_state(session)
    assert state is not None
    state.next_template_id, state.queued = upper.id, [upper.id, arms.id]
    session.commit()
    saved = _save(session, plan, [Kept("arms", "Arms", "strength", 1)])
    assert isinstance(saved, plan_edit.Saved)
    assert _live(session) == [(0, "arms")]
    assert session.get(SessionTemplate, upper.id) is None
    assert (
        session.scalars(select(TemplateItem).where(TemplateItem.template_id == upper.id)).all()
        == []
    )
    assert session.scalars(select(SessionProgress)).all() == []
    assert _pointer(session) == (arms.id, [])
    assert _events(session) == [{"added": 0, "removed": 1, "retired": 0, "moved": 0}]
    assert _notices(session) == [
        "Your plan changed: removed Upper; Arms now has 1 rest day after it. Next is Arms."
    ]


def test_the_session_done_today_removed_is_retired_and_its_workout_kept(
    session: Session, plan: PlanSeed
) -> None:
    upper, arms = _row(session, "upper"), _row(session, "arms")
    workout = Workout(local_date=TODAY, template_id=upper.id, status=WorkoutStatus.DONE)
    session.add(workout)
    state = users.plan_state(session)
    assert state is not None
    state.next_template_id = arms.id
    session.commit()
    saved = _save(session, plan, [Kept("arms", "Arms", "strength", 1)])
    assert isinstance(saved, plan_edit.Saved)
    session.refresh(upper)
    assert upper.retired_on == TODAY
    assert upper.position == 10_000 + upper.id
    assert (upper.items, upper.gym_items, upper.away_items) == ([], [], [])
    assert upper.name == "Upper"  # history still names it
    assert session.get_one(Workout, workout.id).template_id == upper.id
    assert _live(session) == [(0, "arms")]
    assert _pointer(session) == (arms.id, [])
    assert _events(session) == [{"added": 0, "removed": 1, "retired": 1, "moved": 0}]


def test_one_save_deletes_one_session_retires_another_and_adds_a_third(
    session: Session, bundled: PlanSeed
) -> None:
    """Every live position is rewritten after parking above the retired rows (#714's clash)."""
    factories.retire(session, _row(session, "zone2"), TODAY - timedelta(days=9))
    hiit = _row(session, "hiit")
    session.add(Workout(local_date=TODAY - timedelta(days=4), template_id=hiit.id, status="done"))
    session.commit()
    cycle = [e for e in _cycle(session) if e.name not in ("High intensity", "Legs")]
    cycle.insert(0, Added("n1", "Legs A", "strength", 0, copy_of="legs"))
    saved = _save(session, bundled, cycle)
    assert isinstance(saved, plan_edit.Saved)
    assert _live(session) == [
        (0, "legs-a"),
        (1, "recovery"),
        (2, "torso"),
        (3, "moderate-cardio"),
        (4, "arms"),
    ]
    assert (
        session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "legs")).all() == []
    )
    assert _row(session, "hiit").retired_on == TODAY
    assert _events(session) == [{"added": 1, "removed": 2, "retired": 1, "moved": 0}]


def test_rename_kind_rest_and_a_move_tell_the_person(session: Session, plan: PlanSeed) -> None:
    cycle = [Kept("arms", "Arms A", "conditioning", 0), Kept("upper", "Upper", "strength", 2)]
    saved = _save(session, plan, cycle)
    assert isinstance(saved, plan_edit.Saved)
    assert saved.version == "Cycle"
    assert _live(session) == [(0, "arms"), (1, "upper")]
    arms = _row(session, "arms")
    assert (arms.name, arms.kind) == ("Arms A", "conditioning")
    assert _pointer(session)[0] == _row(session, "upper").id  # stays on its session
    assert _events(session) == [{"added": 0, "removed": 0, "retired": 0, "moved": 1}]
    assert _notices(session) == [
        "Your plan changed: renamed Arms to Arms A; moved Arms A; made Arms A a cardio "
        "session; Upper now has 2 rest days after it. Next is Upper."
    ]


def test_a_rename_alone_tells_but_writes_no_cycle_event(session: Session, plan: PlanSeed) -> None:
    cycle = [Kept("upper", "Top half", "strength", 0), Kept("arms", "Arms", "strength", 0)]
    _save(session, plan, cycle)
    assert _notices(session) == ["Your plan changed: renamed Upper to Top half. Next is Top half."]
    assert _events(session) == []


def test_a_long_notice_says_how_many_changes(session: Session, bundled: PlanSeed) -> None:
    cycle = [
        Kept(t.slug, f"{t.name} renamed to something quite long"[:40], t.kind, t.rest_after)
        for t in plan_edit.templates(session)
    ]
    _save(session, bundled, cycle)
    [text] = _notices(session)
    assert text.startswith("Your plan changed: 7 changes to your sessions. Next is Legs")
    assert len(text) <= 300


def test_the_cycle_and_versions_make_one_version_with_the_days_note(
    session: Session, plan: PlanSeed
) -> None:
    _save(session, plan, None, VersionEdit("upper", Place.HOME, (DIP,)), note="Dips")
    cycle = [*_cycle(session), Added("n1", "Back", "strength", 0)]
    saved = _save(session, plan, cycle, _new(PULL), note="Added Back")
    assert isinstance(saved, plan_edit.Saved)
    assert saved.version == "Dips; Added Back"
    versions = session.scalars(select(PlanVersion).where(PlanVersion.since == TODAY)).all()
    assert [v.name for v in versions] == ["Dips; Added Back"]


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", "1 to 40 characters"),
        ("x" * 41, "1 to 40 characters"),
        ("upper!", "Two sessions can't both be called upper!."),
        ("pull up", "pull up is an exercise's name"),
        ("Bar dip", "Bar dip is an exercise's name"),  # an alias, once normalised
        ("Monday", "Monday reads as a day"),
        ("Today legs", "Today legs reads as a day"),
        ("Yesterday", "Yesterday reads as a day"),
    ],
)
def test_a_name_typed_logs_couldnt_tell_apart_is_refused(
    session: Session, plan: PlanSeed, name: str, message: str
) -> None:
    before = plan_edit.revision(session)
    for cycle in (
        [*_cycle(session), Added("n1", name, "strength", 0)],  # new
        [Kept("upper", "Upper", "strength", 0), Kept("arms", name, "strength", 0)],  # renamed
    ):
        found = _save(session, plan, cycle, _new(PULL))
        assert isinstance(found, str)
        assert message in found
    assert plan_edit.revision(session) == before


@pytest.mark.parametrize(
    ("cycle", "message"),
    [
        ([], "at least one session"),
        ([Kept("upper", "Upper", "strength", 7)], "0 to 6"),
        (
            [
                Kept("upper", "Upper", "strength", 6),
                Kept("arms", "Arms", "strength", 6),
                Added("n1", "Back", "strength", 1, copy_of="upper"),
            ],
            "16 days; it can be at most 14",
        ),
        ([Kept("upper", "Upper", "strength", 0)] * 2, "only once"),
        ([Kept("nope", "Nope", "strength", 0)], "nope isn't one of your sessions."),
        ([Kept("upper", "Upper", "heavy", 0)], "strength, cardio or recovery"),
        ([Added("n1", "Copy", "strength", 0, copy_of="nope")], "nope isn't one of your"),
        ([Added("n1", "Empty", "strength", 0)], "Empty needs at least one exercise."),
        ([Added(f"n{i}", f"S {i}", "strength", 0) for i in range(11)], "at most 10"),
    ],
    ids=["none", "rest", "days", "twice", "unknown", "kind", "copy", "empty", "limit"],
)
def test_a_cycle_the_app_couldnt_save_is_refused_unchanged(
    session: Session, plan: PlanSeed, cycle: list[Kept | Added], message: str
) -> None:
    before = plan_edit.revision(session)
    found = _save(session, plan, cycle)
    assert isinstance(found, str)
    assert message in found
    assert plan_edit.revision(session) == before
    assert _notices(session) == []


def test_a_version_of_a_removed_session_is_refused(session: Session, plan: PlanSeed) -> None:
    found = _save(
        session,
        plan,
        [Kept("upper", "Upper", "strength", 0)],
        VersionEdit("arms", Place.HOME, (DIP,)),
    )
    assert found == "arms isn't one of your sessions."


def test_a_draft_of_an_older_plan_is_stale(session: Session, plan: PlanSeed) -> None:
    old = plan_edit.revision(session)
    _save(session, plan, None, VersionEdit("upper", Place.HOME, (DIP,)))
    cycle = [*_cycle(session), Added("n1", "Back", "strength", 0)]
    found = plan_edit.save(session, [_new(PULL)], "Late", old, plan, TODAY, cycle)
    assert found == plan_edit.STALE
    assert len(plan_edit.templates(session)) == 2


def test_a_session_in_progress_refuses_a_cycle_change(session: Session, plan: PlanSeed) -> None:
    kept = [{"item": 0, "set_no": 1, "left": 8}]
    arms = _row(session, "arms")
    session.add(SessionProgress(local_date=TODAY, template_id=arms.id, token="ab" * 16, sets=kept))
    session.commit()
    found = _save(session, plan, [Kept("upper", "Upper", "strength", 0)])
    assert found == plan_edit.IN_PROGRESS
    assert _live(session) == [(0, "upper"), (1, "arms")]
    assert _notices(session) == []
