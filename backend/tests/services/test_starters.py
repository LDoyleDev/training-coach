"""The starters (any-level-any-time.md S1, approved 8 Nov 2026): their sessions as S1 gives them,
the trim's order, and that taking them into the seed changes nothing of the owner's."""

import copy
import tomllib
from datetime import date
from importlib.resources import files
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine, select

from training_coach.db.models import (
    Exercise,
    ExerciseState,
    LadderStep,
    PlanNotice,
    PlanState,
    PlanVersion,
    SessionTemplate,
    TemplateItem,
    User,
)
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.domain import trim
from training_coach.services import plan_import, users
from training_coach.services.seed import PlanSeed, apply_seed, bundled_plan
from training_coach.services.users import OWNER

NAMES = {
    "squat": "goblet-squat",
    "split squat": "bulgarian-split-squat",
    "push-up": "push-up",
    "door-frame row": "doorway-row",
    "glute bridge": "glute-bridge",
    "hip hinge": "hip-hinge",
    "calf raise": "calf-raise",
    "plank": "plank",
    "side plank hip dip": "side-plank-hip-dip",
    "lateral raise": "lateral-raise",
    "curl": "kb-curl",
    "balance": "balance",
    "tibialis raise": "tibialis-raise",
}
# S1 "The sessions" (exercises in order, sets) and "The trim order" (goes first ... kept longest).
SESSIONS = {
    "two-days-a": (
        "squat 3 + door-frame row 3; push-up 4 + hip hinge 3; calf raise 3 + plank 3; "
        "lateral raise 3 + side plank hip dip 2; balance 2",
        "side plank hip dip, lateral raise, plank, calf raise, balance, hip hinge, push-up, "
        "door-frame row; squat",
    ),
    "two-days-b": (
        "split squat 3 + push-up 4; glute bridge 3 + door-frame row 3; hip hinge 2 + "
        "lateral raise 3; calf raise 3 + curl 2; plank 2 + balance 2",
        "plank, curl, calf raise, lateral raise, glute bridge, balance, hip hinge, door-frame row; "
        "split squat and push-up",
    ),
    "three-days-a": (
        "squat 3 + door-frame row 3; push-up 4 + hip hinge 3; calf raise 3 + plank 2; "
        "lateral raise 3 + curl 2; balance 2",
        "curl, lateral raise, plank, calf raise, balance, hip hinge, push-up, "
        "door-frame row; squat",
    ),
    "three-days-b": (
        "split squat 3 + push-up 4; glute bridge 3 + door-frame row 3; lateral raise 3 + "
        "side plank hip dip 2; calf raise 3 + balance 2",
        "calf raise, side plank hip dip, lateral raise, glute bridge, balance, door-frame row; "
        "split squat and push-up",
    ),
    "three-days-c": (
        "squat 3 + door-frame row 3; push-up 3 + glute bridge 3; hip hinge 2 + lateral raise 2; "
        "calf raise 2 + plank 2; balance 2",
        "plank, calf raise, lateral raise, glute bridge, balance, hip hinge, push-up, "
        "door-frame row; squat",
    ),
    "four-days-lower-1": (
        "squat 3 + calf raise 3; hip hinge 3 + plank 3; split squat 2 + tibialis raise 2; "
        "balance 2",
        "tibialis raise, plank, calf raise, split squat, balance, hip hinge; squat",
    ),
    "four-days-upper-1": (
        "push-up 4 + door-frame row 4; lateral raise 3 + curl 3; side plank hip dip 2",
        "side plank hip dip, curl, lateral raise, door-frame row; push-up",
    ),
    "four-days-lower-2": (
        "split squat 3 + calf raise 3; glute bridge 3 + side plank hip dip 2; hip hinge 2 + "
        "plank 2; squat 2; balance 2",
        "plank, side plank hip dip, calf raise, glute bridge, split squat, balance, squat; "
        "hip hinge",
    ),
    "four-days-upper-2": (
        "door-frame row 4 + push-up 4; lateral raise 3 + curl 3; plank 2",
        "plank, curl, lateral raise, push-up; door-frame row",
    ),
}
# S1 Decided 9: the queue orders, as rest places after each session.
REST_AFTER = {"two-days": [2, 3], "three-days": [1, 1, 2], "four-days": [0, 1, 0, 2]}
OLD_RANGES = {"goblet-squat": [3, 10], "hip-hinge": [3, 10], "balance": [3, 10]}


def _planned(text: str) -> list[tuple[str, int, int | None]]:
    """S1's "a 3 + b 3; c 2" as (slug, sets, pair)."""
    found: list[tuple[str, int, int | None]] = []
    pair = 0
    for group in text.split(";"):
        parts = [p.strip().rsplit(" ", 1) for p in group.split("+")]
        pair += len(parts) == 2
        found += [(NAMES[n], int(sets), pair if len(parts) == 2 else None) for n, sets in parts]
    return found


def _sessions() -> dict[str, Any]:
    return {s.slug: s for starter in bundled_plan().starters for s in starter.sessions}


@pytest.mark.parametrize("slug", SESSIONS)
def test_each_session_is_s1s(slug: str) -> None:
    found = _sessions()[slug]
    assert [(i.exercise, i.sets, i.pair) for i in found.items] == _planned(SESSIONS[slug][0])
    assert found.away == found.items  # Away is the same list
    assert found.gym == []  # until setup writes someone's gym version (Decided 5)
    one_sided = {i.exercise for i in found.items if i.per_side}
    assert one_sided <= {"bulgarian-split-squat", "side-plank-hip-dip"}  # "a side" in S1


@pytest.mark.parametrize("slug", SESSIONS)
def test_the_trim_drops_exercises_in_s1s_order(slug: str) -> None:
    """Trimmed to nothing, the trim's own rule (ADR-0082) drops them as S1's list says."""
    catalogue = {e.slug: e for e in bundled_plan().exercises}
    items = _sessions()[slug].items
    shapes = [
        trim.Item(
            sets=i.sets,
            pattern=catalogue[i.exercise].pattern,
            primes=frozenset(m for m, w in catalogue[i.exercise].muscles.items() if w == 1),
        )
        for i in items
    ]
    trimmed = trim.trim(shapes, 1, lambda _sets, _durations: 1000.0)
    dropped = [items[i].exercise for i in trimmed.dropped]
    left = [i.exercise for i, n in zip(items, trimmed.sets, strict=True) if n]
    first, last = SESSIONS[slug][1].split(";")
    goes_first = [NAMES[n.strip()] for n in first.split(",")]
    kept_longest = {NAMES[n.strip()] for n in last.split(" and ")}
    assert dropped[: len(goes_first)] == goes_first
    assert {*dropped[len(goes_first) :], *left} == kept_longest


def test_each_starter_is_a_week_with_its_rest_places() -> None:
    plan = bundled_plan()
    assert {s.slug: [x.rest_after for x in s.sessions] for s in plan.starters} == REST_AFTER
    assert {s.slug: s.days for s in plan.starters} == {
        "two-days": 2,
        "three-days": 3,
        "four-days": 4,
    }
    used = {i.exercise for s in _sessions().values() for i in s.items}
    assert used == set(NAMES.values())
    assert [e.slug for e in plan.exercises if e.slug in used and e.range is not None] == []


def test_a_new_person_starts_on_the_three_day_starter_at_the_bottom(engine: Engine) -> None:
    """Until setup picks by days a week; every exercise at its bottom step, as S1 says."""
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, bundled_plan())
    with make_session_factory(engine, user_id=2)() as theirs:
        sessions = theirs.scalars(select(SessionTemplate).order_by(SessionTemplate.position))
        found = [(t.slug, t.rest_after, len(t.items), len(t.away_items)) for t in sessions]
        state = users.plan_state(theirs)
        steps = theirs.scalars(
            select(LadderStep.position).join(
                ExerciseState, ExerciseState.ladder_step_id == LadderStep.id
            )
        ).all()
        first = theirs.scalars(select(SessionTemplate.id).order_by(SessionTemplate.position))
        assert state is not None
        assert state.next_template_id == first.first()
    assert found == [
        ("three-days-a", 1, 9, 9),
        ("three-days-b", 1, 8, 8),
        ("three-days-c", 2, 9, 9),
    ]
    assert len(steps) == len(bundled_plan().exercises)
    assert set(steps) == {0}


def test_an_exercise_added_later_starts_at_the_bottom_for_all_but_the_owner(engine: Engine) -> None:
    """Whatever plan a member has by then: setup's answers move them up, not the catalogue."""
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, bundled_plan())
    data = tomllib.loads(files("training_coach.seed").joinpath("plan.toml").read_text("utf-8"))
    added = copy.deepcopy(_exercise(data, "pull-up"))
    added.update(slug="pull-up-2", name="Pull-up again", aliases=[], start=2)
    data["exercises"].append(added)
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, PlanSeed.model_validate(data))
    for user_id, position in ((OWNER, 2), (2, 0)):
        with make_session_factory(engine, user_id=user_id)() as mine:
            found = mine.scalar(
                select(LadderStep.position)
                .join(ExerciseState, ExerciseState.ladder_step_id == LadderStep.id)
                .join(Exercise, Exercise.id == ExerciseState.exercise_id)
                .where(Exercise.slug == "pull-up-2")
            )
        assert found == position, user_id


def _before() -> PlanSeed:
    """plan.toml as it was before the starters: no starters, and the ranges they took over."""
    text = files("training_coach.seed").joinpath("plan.toml").read_text(encoding="utf-8")
    data = copy.deepcopy(tomllib.loads(text))
    del data["starters"], data["new_people"], data["gym_swaps"]
    for exercise in data["exercises"]:
        if exercise["slug"] in OLD_RANGES:
            exercise["range"] = OLD_RANGES[exercise["slug"]]
    return PlanSeed.model_validate(data)


def _owners(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    """Every row of the owner's plan, queue and levels, as read through their own session."""
    found: dict[str, list[tuple[Any, ...]]] = {}
    with make_session_factory(engine, user_id=OWNER)() as mine:
        for model in (SessionTemplate, TemplateItem, PlanVersion, PlanState, ExerciseState):
            columns = [c for c in model.__table__.columns if c.key != "updated_at"]
            keys = list(model.__table__.primary_key.columns)
            rows = mine.execute(select(*columns).order_by(*keys)).all()
            found[model.__name__] = [tuple(row) for row in rows]
    return found


def test_seeding_the_starters_over_the_owner_changes_none_of_theirs(engine: Engine) -> None:
    """The release that brings the starters leaves the owner's 7-day cycle, items, versions,
    queue and levels as they were, tells them nothing (ADR-0087) and has nothing to import."""
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, _before())
    before = _owners(engine)
    assert len(before["SessionTemplate"]) == 7
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, bundled_plan())
    assert _owners(engine) == before
    with make_session_factory(engine, user_id=OWNER)() as mine:
        assert mine.scalars(select(PlanNotice)).all() == []
        assert plan_import.preview(mine, bundled_plan(), date(2026, 11, 9)).changes == ()


def test_seeding_the_gym_swaps_over_the_owner_changes_none_of_theirs(engine: Engine) -> None:
    """The release that brings the gym swaps (S1, Decided 5) after the starters: the owner's
    rows stay as they were, with no notice (ADR-0087) and nothing to import, and so do a
    member's, whose gym version waits for setup."""
    text = files("training_coach.seed").joinpath("plan.toml").read_text(encoding="utf-8")
    data = tomllib.loads(text)
    del data["gym_swaps"]
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, PlanSeed.model_validate(data))
    before = _owners(engine)
    with make_session_factory(engine, user_id=2)() as theirs:
        items = theirs.scalars(select(TemplateItem.id).order_by(TemplateItem.id)).all()
    with session_scope(make_session_factory(engine)) as shared:
        assert not apply_seed(shared, bundled_plan()).changed
    assert _owners(engine) == before
    with make_session_factory(engine, user_id=2)() as theirs:
        assert theirs.scalars(select(TemplateItem.id).order_by(TemplateItem.id)).all() == items
    with make_session_factory(engine)() as shared:
        assert shared.scalars(select(PlanNotice), execution_options={ALL_USERS: True}).all() == []
    with make_session_factory(engine, user_id=OWNER)() as mine:
        assert plan_import.preview(mine, bundled_plan(), date(2026, 11, 9)).changes == ()


def _swap(data: dict[str, Any], gym: str) -> dict[str, Any]:
    found: dict[str, Any] = next(s for s in data["gym_swaps"] if s["gym"] == gym)
    return found


def _exercise(data: dict[str, Any], slug: str) -> dict[str, Any]:
    found: dict[str, Any] = next(e for e in data["exercises"] if e["slug"] == slug)
    return found


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (lambda d: d.update(new_people="five-days"), "not a starter"),
        (lambda d: d["starters"][0].update(days=3), "3 days but 2 sessions"),
        (lambda d: d["starters"][0]["sessions"][0].update(rest_after=1), "make 6 days"),
        (
            lambda d: d["starters"][0]["sessions"][0]["items"][0].update(exercise="nope"),
            "unknown exercise nope",
        ),
        (lambda d: _exercise(d, "plank").update(range=[10, 30]), "have a range"),
        (lambda d: _swap(d, "leg-press").update(from_step="Squat"), "not in its ladder"),
        (lambda d: _swap(d, "leg-press").update(gym="nope"), "unknown exercise"),
        (lambda d: _swap(d, "leg-press").update(gym="bulgarian-split-squat"), "not a gym exer"),
        (
            lambda d: _swap(d, "leg-press").update(from_step="A lower seat, arms crossed"),
            "below Leg press's level",
        ),
        (
            lambda d: _swap(d, "lat-pulldown").update(sessions=["two-days-a", "four-days-lower-1"]),
            "four-days-lower-1 is no starter session with it",
        ),
        (lambda d: _swap(d, "lat-pulldown").update(sessions=[]), "two swaps for every session"),
        (lambda d: d["gym_swaps"].append(_swap(d, "lat-pulldown")), "two-days-b has two swaps"),
        (
            lambda d: _swap(d, "leg-press").update(exercise="pull-up", from_step="Strict pull-up"),
            "no starter uses",
        ),
        (lambda d: _swap(d, "leg-press").update(rep_min=16), "rep_max < rep_min"),
    ],
    ids=[
        "unknown-default",
        "days",
        "week",
        "exercise",
        "range",
        "swap-step",
        "swap-gym",
        "swap-home-exercise",
        "swap-below",
        "swap-session",
        "swap-two-general",
        "swap-two-named",
        "swap-unused",
        "swap-range",
    ],
)
def test_a_starter_is_checked_like_a_session(change: Any, error: str) -> None:
    text = files("training_coach.seed").joinpath("plan.toml").read_text(encoding="utf-8")
    data = tomllib.loads(text)
    change(data)
    with pytest.raises(ValidationError, match=error):
        PlanSeed.model_validate(data)
