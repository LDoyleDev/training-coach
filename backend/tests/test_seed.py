import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from training_coach.config import get_settings
from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    LadderStep,
    PlanState,
    SessionTemplate,
    TemplateItem,
    UserSettings,
)
from training_coach.db.session import make_engine
from training_coach.services.seed import PlanSeed, SeedError, apply_seed, load_plan

BACKEND = Path(__file__).resolve().parents[1]

MINI_PLAN = """
[[exercises]]
slug = "pull-up"
name = "Pull-up"
kind = "reps"
start = 1
ladder = ["Negatives", "Strict", "Weighted"]

[[exercises]]
slug = "dip"
name = "Dip"
kind = "reps"
start = 0
ladder = ["Feet down", "Feet up"]

[[sessions]]
slug = "upper"
name = "Upper"
focus = "Strength"
items = [{ exercise = "pull-up", sets = 4, rep_min = 5, rep_max = 12 }]

[[sessions]]
slug = "arms"
name = "Arms"
focus = "Accessories"
is_rest_optional = true
items = [{ exercise = "dip", sets = 3, rep_min = 8, rep_max = 15 }]
"""


@pytest.fixture
def engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    url = f"sqlite:///{tmp_path / 'seed.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    eng = make_engine(url)
    yield eng
    eng.dispose()
    get_settings.cache_clear()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


# ------------------------------------------------------------------ the plan file


def test_bundled_plan_is_valid() -> None:
    plan = load_plan()
    assert [s.slug for s in plan.sessions] == [
        "legs",
        "recovery",
        "torso",
        "moderate-cardio",
        "hiit",
        "arms",
        "zone2",
    ]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda t: t.replace('exercise = "dip"', 'exercise = "squat"'), "unknown exercise"),
        (lambda t: t.replace("start = 1", "start = 3"), "beyond the ladder"),
        (lambda t: t.replace("rep_min = 8, rep_max = 15", "rep_min = 9, rep_max = 2"), "rep_max"),
        (lambda t: t.replace('slug = "dip"', 'slug = "pull-up"'), "duplicate exercise"),
        (lambda t: t.replace('kind = "reps"', 'kind = "kilos"', 1), "kind"),
        (lambda t: t.replace('slug = "upper"', 'slug = "Upper Body"'), "pattern"),
        (lambda t: t.replace('focus = "Strength"', 'focus = "Strength"\ncolour = "red"'), "extra"),
    ],
    ids=["unknown-exercise", "start", "range", "dup-slug", "kind", "slug-format", "unknown-key"],
)
def test_invalid_plans_rejected(change: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        load_plan(change(MINI_PLAN))  # type: ignore[operator]


# ----------------------------------------------------------------------- applying


def test_seed_creates_plan_state_and_settings(session: Session) -> None:
    result = apply_seed(session, load_plan(MINI_PLAN))
    session.commit()

    assert result.created > 0
    assert _count(session, Exercise) == 2
    assert _count(session, LadderStep) == 5
    assert _count(session, SessionTemplate) == 2
    assert _count(session, TemplateItem) == 2

    pull_up = session.scalars(select(Exercise).where(Exercise.slug == "pull-up")).one()
    state = session.get_one(ExerciseState, pull_up.id)
    assert session.get_one(LadderStep, state.ladder_step_id).name == "Strict"

    first = session.scalars(select(SessionTemplate).where(SessionTemplate.position == 0)).one()
    assert session.get_one(PlanState, 1).next_template_id == first.id
    assert first.slug == "upper"
    assert session.get(UserSettings, 1) is not None
    assert session.scalars(select(Event.kind)).all() == ["seed.applied"]


def test_seed_is_idempotent(session: Session) -> None:
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    second = apply_seed(session, load_plan(MINI_PLAN))
    session.commit()

    assert not second.changed
    assert _count(session, Exercise) == 2
    assert _count(session, LadderStep) == 5
    assert _count(session, Event) == 1  # no event for a no-op run


def test_reseed_keeps_progress(session: Session) -> None:
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    pull_up = session.scalars(select(Exercise).where(Exercise.slug == "pull-up")).one()
    state = session.get_one(ExerciseState, pull_up.id)
    weighted = next(s for s in pull_up.ladder if s.name == "Weighted")
    state.ladder_step_id = weighted.id
    arms = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "arms")).one()
    session.get_one(PlanState, 1).next_template_id = arms.id
    session.commit()

    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()

    assert session.get_one(ExerciseState, pull_up.id).ladder_step_id == weighted.id
    assert session.get_one(PlanState, 1).next_template_id == arms.id


def test_reseed_applies_edits_and_additions(session: Session) -> None:
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    edited = (
        MINI_PLAN.replace('"Feet down", "Feet up"]', '"Feet down", "Feet up", "Weighted dip"]')
        .replace("sets = 4, rep_min = 5", "sets = 5, rep_min = 5")
        .replace('name = "Dip"', 'name = "Dip (chairs)"')
    )
    result = apply_seed(session, load_plan(edited))
    session.commit()

    assert result.created == 1  # the new ladder step
    assert result.updated == 2  # dip name, pull-up item sets
    dip = session.scalars(select(Exercise).where(Exercise.slug == "dip")).one()
    assert dip.name == "Dip (chairs)"
    assert [s.name for s in dip.ladder] == ["Feet down", "Feet up", "Weighted dip"]


def test_reseed_can_reorder_sessions(session: Session) -> None:
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    upper_block, arms_block = MINI_PLAN.split("[[sessions]]")[1:]
    reordered = (
        MINI_PLAN.split("[[sessions]]")[0]
        + "[[sessions]]"
        + arms_block
        + "[[sessions]]"
        + upper_block
    )
    apply_seed(session, load_plan(reordered))
    session.commit()

    order = session.scalars(select(SessionTemplate.slug).order_by(SessionTemplate.position)).all()
    assert order == ["arms", "upper"]
    positions = session.scalars(select(SessionTemplate.position).order_by(SessionTemplate.position))
    assert list(positions) == [0, 1]


def test_full_bundled_plan_seeds(session: Session) -> None:
    plan: PlanSeed = load_plan()
    apply_seed(session, plan)
    session.commit()
    assert _count(session, Exercise) == len(plan.exercises)
    assert _count(session, SessionTemplate) == 7
    assert _count(session, ExerciseState) == len(plan.exercises)


NEW_SESSION = """
[[sessions]]
slug = "core"
name = "Core"
focus = "Core"
items = [{ exercise = "dip", sets = 2, rep_min = 5, rep_max = 10 }]
"""


def _sessions(text: str) -> tuple[str, list[str]]:
    head, *blocks = text.split("[[sessions]]")
    return head, ["[[sessions]]" + b for b in blocks]


@pytest.mark.parametrize("insert_at", [0, 1, 2], ids=["front", "middle", "end"])
def test_new_session_can_be_inserted_anywhere(session: Session, insert_at: int) -> None:
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    head, blocks = _sessions(MINI_PLAN)
    blocks.insert(insert_at, NEW_SESSION)
    apply_seed(session, load_plan(head + "".join(blocks)))
    session.commit()

    order = session.scalars(select(SessionTemplate.slug).order_by(SessionTemplate.position)).all()
    expected = ["upper", "arms"]
    expected.insert(insert_at, "core")
    assert order == expected
    positions = session.scalars(select(SessionTemplate.position).order_by(SessionTemplate.position))
    assert list(positions) == [0, 1, 2]


def test_removing_a_session_is_rejected_and_changes_nothing(session: Session) -> None:
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    head, blocks = _sessions(MINI_PLAN)

    with pytest.raises(SeedError, match=r"\['upper'\].*needs a data migration"):
        apply_seed(session, load_plan(head + blocks[1]))
    session.rollback()

    order = session.scalars(select(SessionTemplate.slug).order_by(SessionTemplate.position)).all()
    assert order == ["upper", "arms"]


def test_item_removed_from_session_is_deleted(session: Session) -> None:
    two_items = MINI_PLAN.replace(
        'items = [{ exercise = "pull-up", sets = 4, rep_min = 5, rep_max = 12 }]',
        'items = [{ exercise = "pull-up", sets = 4, rep_min = 5, rep_max = 12 },'
        ' { exercise = "dip", sets = 3, rep_min = 8, rep_max = 15 }]',
    )
    apply_seed(session, load_plan(two_items))
    session.commit()
    assert _count(session, TemplateItem) == 3

    result = apply_seed(session, load_plan(MINI_PLAN))
    session.commit()

    assert result.deleted == 1
    upper = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "upper")).one()
    assert [item.position for item in upper.items] == [0]
    assert _count(session, TemplateItem) == 2


def test_shortening_a_ladder_is_rejected_before_any_write(session: Session) -> None:
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    shorter = MINI_PLAN.replace('"Feet down", "Feet up"]', '"Feet down"]').replace(
        'name = "Pull-up"', 'name = "Pull-up renamed"'
    )

    with pytest.raises(SeedError, match="'dip' has 2 ladder steps"):
        apply_seed(session, load_plan(shorter))
    session.rollback()

    assert (
        session.scalars(select(Exercise.name).where(Exercise.slug == "pull-up")).one() == "Pull-up"
    )


def test_bundled_plan_covers_huberman_protocol() -> None:
    """docs/specs/training-plan.md: neck twice a week, posture work, every major muscle trained."""
    plan = load_plan()
    groups = {e.slug: set(e.muscle_groups) for e in plan.exercises}

    def sessions_hitting(group: str) -> int:
        return sum(any(group in groups[item.exercise] for item in s.items) for s in plan.sessions)

    assert sessions_hitting("neck") >= 2
    assert sessions_hitting("posture") >= 2
    for group in (
        "quads",
        "hamstrings",
        "glutes",
        "calves",
        "tibialis",
        "chest",
        "lats",
        "upper back",
        "rear delts",
        "side delts",
        "biceps",
        "triceps",
        "core",
        "lower back",
        "grip",
    ):
        assert sessions_hitting(group) >= 1, group


def test_bundled_plan_weekly_volume_in_galpin_range() -> None:
    """10-20 hard sets per week for the big muscle groups (Galpin)."""
    volume = _weekly_volume()
    for group in ("quads", "glutes", "lats", "upper back", "biceps", "triceps"):
        assert 10 <= volume[group] <= 20, (group, volume[group])


def _weekly_volume() -> dict[str, int]:
    plan = load_plan()
    groups = {e.slug: e.muscle_groups for e in plan.exercises}
    volume: dict[str, int] = {}
    for session in plan.sessions:
        for item in session.items:
            for group in groups[item.exercise]:
                volume[group] = volume.get(group, 0) + item.sets
    return volume


def test_training_plan_spec_volume_table_matches_plan() -> None:
    """The hand-written weekly-sets table in the spec must not drift from plan.toml."""
    spec = (Path(__file__).resolve().parents[2] / "docs/specs/training-plan.md").read_text()
    section = spec.split("## Weekly hard sets per muscle group", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| ([A-Za-z ]+) \| (\d+) \|", section, flags=re.M)
    assert len(rows) >= 10
    volume = _weekly_volume()
    for name, sets in rows:
        assert volume[name.lower()] == int(sets), (name, volume[name.lower()], sets)
