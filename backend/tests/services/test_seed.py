import re
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    FitnessTestDay,
    LadderStep,
    PlanState,
    PlanVersion,
    SessionTemplate,
    SetLog,
    TemplateItem,
    User,
    UserSettings,
    Workout,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import ExerciseKind, WorkoutStatus
from training_coach.domain.volume import weekly_sets
from training_coach.services import users
from training_coach.services.seed import PlanSeed, SeedError, apply_seed, load_plan

MINI_PLAN = """
[[exercises]]
slug = "pull-up"
name = "Pull-up"
kind = "reps"
muscles = { lats = 1, biceps = 0.5 }
pattern = "vertical pull"
start = 1
ladder = ["Negatives", "Strict", "Weighted"]

[[exercises]]
slug = "dip"
name = "Dip"
kind = "reps"
muscles = { chest = 1 }
pattern = "vertical push"
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
def test_invalid_plans_rejected(change: Callable[[str], str], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        load_plan(change(MINI_PLAN))


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
    state = users.exercise_state(session, pull_up.id)
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
    state = users.exercise_state(session, pull_up.id)
    weighted = next(s for s in pull_up.ladder if s.name == "Weighted")
    state.ladder_step_id = weighted.id
    arms = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "arms")).one()
    session.get_one(PlanState, 1).next_template_id = arms.id
    session.commit()

    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()

    assert users.exercise_state(session, pull_up.id).ladder_step_id == weighted.id
    assert session.get_one(PlanState, 1).next_template_id == arms.id


def test_moving_an_exercise_to_another_session_keeps_its_step(session: Session) -> None:
    """Progress is per exercise, not per plan day: moving pull-ups from Upper to Arms, with
    more sets, keeps the step reached (the Oct 2026 coverage update moves exercises)."""
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    pull_up = session.scalars(select(Exercise).where(Exercise.slug == "pull-up")).one()
    weighted = next(s for s in pull_up.ladder if s.name == "Weighted")
    users.exercise_state(session, pull_up.id).ladder_step_id = weighted.id
    session.commit()
    moved = MINI_PLAN.replace(
        'items = [{ exercise = "pull-up", sets = 4, rep_min = 5, rep_max = 12 }]',
        'items = [{ exercise = "dip", sets = 2, rep_min = 8, rep_max = 15 }]',
    ).replace(
        'items = [{ exercise = "dip", sets = 3, rep_min = 8, rep_max = 15 }]',
        'items = [\n  { exercise = "dip", sets = 3, rep_min = 8, rep_max = 15 },\n'
        '  { exercise = "pull-up", sets = 5, rep_min = 5, rep_max = 12 },\n]',
    )

    apply_seed(session, load_plan(moved))
    session.commit()

    assert users.exercise_state(session, pull_up.id).ladder_step_id == weighted.id
    arms = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "arms")).one()
    assert [(i.exercise_id, i.sets) for i in arms.items][-1] == (pull_up.id, 5)


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
    groups = {e.slug: {*e.muscles, *e.qualities, *e.stress} for e in plan.exercises}

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
        "abs",
        "lower back",
        "grip",
    ):
        assert sessions_hitting(group) >= 1, group


def _weekly_volume() -> dict[str, float]:
    plan = load_plan()
    exercises = {e.slug: e for e in plan.exercises}
    return dict(
        weekly_sets(
            (exercises[item.exercise].muscles, item.sets)
            for session in plan.sessions
            for item in session.items
        )
    )


def test_training_plan_spec_volume_table_matches_plan() -> None:
    """The hand-written weekly-sets table in the spec must not drift from plan.toml."""
    spec = (Path(__file__).resolve().parents[3] / "docs/specs/training-plan.md").read_text()
    section = spec.split("## Weekly hard sets per muscle group", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| ([A-Za-z ]+) \| ([\d.]+) \|", section, flags=re.M)
    assert {name.lower(): float(sets) for name, sets in rows} == _weekly_volume()


# ----------------------------------------------------- ladder steps that history uses (#18)

INSERTED = MINI_PLAN.replace(
    '["Negatives", "Strict", "Weighted"]', '["Negatives", "Assisted", "Strict", "Weighted"]'
)


def _step_names(session: Session, slug: str) -> list[str]:
    exercise = session.scalars(select(Exercise).where(Exercise.slug == slug)).one()
    return [s.name for s in sorted(exercise.ladder, key=lambda s: s.position)]


def test_inserting_a_step_mid_ladder_is_rejected_before_any_write(session: Session) -> None:
    """Strict is the current step: shifting it would silently move progress to Assisted."""
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    with pytest.raises(SeedError, match=r"'pull-up' step 2 .*'Strict'.*'Assisted'"):
        apply_seed(session, load_plan(INSERTED))
    session.rollback()
    assert _step_names(session, "pull-up") == ["Negatives", "Strict", "Weighted"]


def test_renaming_a_step_in_use_needs_a_rename_entry(session: Session) -> None:
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    typo_fix = MINI_PLAN.replace('"Feet down", "Feet up"]', '"Feet flat", "Feet up"]')
    with pytest.raises(SeedError, match="renames"):
        apply_seed(session, load_plan(typo_fix))
    session.rollback()

    marked = typo_fix.replace(
        'ladder = ["Feet flat"', 'renames = { "Feet down" = "Feet flat" }\nladder = ["Feet flat"'
    )
    state_before = users.exercise_state(session, _dip_id(session)).ladder_step_id
    apply_seed(session, load_plan(marked))
    session.commit()
    assert _step_names(session, "dip") == ["Feet flat", "Feet up"]
    assert users.exercise_state(session, _dip_id(session)).ladder_step_id == state_before
    # The rename entry can stay in plan.toml: once applied it changes nothing.
    assert not apply_seed(session, load_plan(marked)).changed


def _dip_id(session: Session) -> int:
    return session.scalars(select(Exercise.id).where(Exercise.slug == "dip")).one()


def test_a_step_with_logged_sets_is_protected(session: Session) -> None:
    apply_seed(session, load_plan(MINI_PLAN))
    pull_up = session.scalars(select(Exercise).where(Exercise.slug == "pull-up")).one()
    weighted = next(s for s in pull_up.ladder if s.name == "Weighted")
    workout = Workout(local_date=date(2026, 10, 1), template_id=None, status=WorkoutStatus.DONE)
    workout.sets = [SetLog(exercise_id=pull_up.id, ladder_step_id=weighted.id, set_no=1, value=5)]
    session.add(workout)
    session.commit()
    vest = MINI_PLAN.replace('"Strict", "Weighted"]', '"Strict", "Weighted vest"]')
    with pytest.raises(SeedError, match="'Weighted'"):
        apply_seed(session, load_plan(vest))


def test_unused_steps_can_change_and_appending_stays_allowed(session: Session) -> None:
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    edited = MINI_PLAN.replace(
        '["Negatives", "Strict", "Weighted"]', '["Slow negatives", "Strict", "Weighted", "Archer"]'
    )
    apply_seed(session, load_plan(edited))
    session.commit()
    assert _step_names(session, "pull-up") == ["Slow negatives", "Strict", "Weighted", "Archer"]


def test_rename_must_name_a_step_in_the_ladder() -> None:
    bad = MINI_PLAN.replace(
        'ladder = ["Feet down"', 'renames = { "Feet down" = "Feet flat" }\nladder = ["Feet down"'
    )
    with pytest.raises(ValidationError, match="not in its ladder"):
        load_plan(bad)


LOADED = 'ladder = ["Negatives", "Strict", "Weighted"]\nloads = { Weighted = "barbell" }'


def test_a_step_can_take_load_with_the_kit_that_carries_it() -> None:
    plan = load_plan(MINI_PLAN.replace('ladder = ["Negatives", "Strict", "Weighted"]', LOADED))
    assert plan.exercises[0].loads == {"Weighted": "barbell"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda t: t.replace("Weighted = ", "Archer = "), "not in its ladder"),
        (lambda t: t.replace('"barbell"', '"kettlebell"'), "loads.Weighted"),
        (lambda t: t.replace('kind = "reps"', 'kind = "seconds"', 1), "counted in reps"),
    ],
    ids=["unknown-step", "unknown-kit", "timed"],
)
def test_loads_must_name_a_step_a_kit_and_count_reps(
    change: Callable[[str], str], message: str
) -> None:
    loaded = MINI_PLAN.replace('ladder = ["Negatives", "Strict", "Weighted"]', LOADED)
    with pytest.raises(ValidationError, match=message):
        load_plan(change(loaded))


@pytest.mark.parametrize(
    ("ladder", "renames"),
    [
        pytest.param('["Strict", "Negatives", "Weighted"]', "", id="swap-unused-and-used"),
        pytest.param(
            '["Strict", "Negatives", "Weighted"]',
            'renames = { "Negatives" = "Strict", "Strict" = "Negatives" }\n',
            id="swap-with-renames",
        ),
        pytest.param(
            '["Negatives", "Weighted", "Archer"]',
            'renames = { "Strict" = "Weighted", "Weighted" = "Archer" }\n',
            id="chain",
        ),
        pytest.param(
            '["Negatives", "Assisted", "Strict", "Weighted"]',
            'renames = { "Strict" = "Assisted", "Weighted" = "Strict" }\n',
            id="insert-dressed-as-renames",
        ),
    ],
)
def test_moving_names_between_steps_is_rejected(
    session: Session, ladder: str, renames: str
) -> None:
    """A step may only take a name no other step has: anything else moves history."""
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    edited = MINI_PLAN.replace(
        'ladder = ["Negatives", "Strict", "Weighted"]', f"{renames}ladder = {ladder}"
    )
    with pytest.raises(SeedError, match="already the name of step"):
        apply_seed(session, load_plan(edited))
    session.rollback()
    assert _step_names(session, "pull-up") == ["Negatives", "Strict", "Weighted"]


def test_ladder_names_must_be_unique() -> None:
    dupes = MINI_PLAN.replace('"Feet down", "Feet up"]', '"Feet up", "Feet up"]')
    with pytest.raises(ValidationError, match="appears twice"):
        load_plan(dupes)


@pytest.mark.parametrize(
    ("exercise", "alias"),
    [("Pull-up", "dips"), ("Dip", "PULL UP")],
    ids=["alias-equals-other-name", "differs-only-in-case-and-punctuation"],
)
def test_two_exercises_cannot_share_a_name(exercise: str, alias: str) -> None:
    """A typed log matches names exactly first, so a shared one would pick silently (#54)."""
    clash = MINI_PLAN.replace(f'name = "{exercise}"', f'name = "{exercise}"\naliases = ["{alias}"]')
    with pytest.raises(ValidationError, match="used by both"):
        load_plan(clash)


def test_seed_gives_every_user_their_own_starting_rows(engine: Engine) -> None:
    """ADR-0026: each person gets ladder positions, a queue and settings of their own."""
    sessions = make_session_factory(engine)
    with session_scope(sessions) as session:
        session.add(User(id=2))
    with session_scope(sessions) as session:
        apply_seed(session, load_plan())
    for user_id in (1, 2):
        with make_session_factory(engine, user_id=user_id)() as session:
            assert users.plan_state(session) is not None
            assert users.settings_row(session) is not None
            assert len(session.scalars(select(ExerciseState)).all()) == len(load_plan().exercises)


def _upper_items(items: str) -> str:
    one = 'items = [{ exercise = "pull-up", sets = 4, rep_min = 5, rep_max = 12 }]'
    return MINI_PLAN.replace(one, f"items = [{items}]", 1)


PULL = '{ exercise = "pull-up", sets = 4, rep_min = 5, rep_max = 12'
DIP = '{ exercise = "dip", sets = 3, rep_min = 8, rep_max = 15'


def test_a_pair_is_two_neighbouring_items_and_is_stored(session: Session) -> None:
    plan = load_plan(_upper_items(f"{PULL}, pair = 1 }}, {DIP}, pair = 1 }}"))
    apply_seed(session, plan)
    session.flush()
    upper = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "upper")).one()
    assert [item.pair for item in upper.items] == [1, 1]


@pytest.mark.parametrize(
    "items",
    [
        f"{PULL}, pair = 1 }}",  # alone
        f"{PULL}, pair = 1 }}, {DIP} }}, {PULL}, pair = 1 }}",  # not neighbours
        f"{PULL}, pair = 1 }}, {DIP}, pair = 1 }}, {DIP}, pair = 1 }}",  # three
    ],
    ids=["alone", "apart", "three"],
)
def test_a_broken_pair_is_rejected(items: str) -> None:
    with pytest.raises(ValidationError, match="pair 1 must be two neighbouring items"):
        load_plan(_upper_items(items))


def test_the_bundled_resistance_sessions_are_fully_paired() -> None:
    sessions = {s.slug: s for s in load_plan().sessions}
    for slug in ("legs", "torso", "arms"):
        assert all(item.pair is not None for item in sessions[slug].items), slug
        assert all(item.pair is not None for item in sessions[slug].gym), slug
    alone = [item.exercise for item in sessions["recovery"].items if item.pair is None]
    assert alone == ["mobility"]


REP_TOP = 18  # ADR-0078: at 18 reps on every set, the next step is due
HIGH_REP = {"calf-raise", "tibialis-raise", "kb-swing", "band-face-pull"}  # keep their ranges


def test_every_reps_range_tops_out_at_18_except_high_rep_work() -> None:
    plan = load_plan()
    kinds = {e.slug: e.kind for e in plan.exercises}
    assert {kinds[slug] for slug in HIGH_REP} == {ExerciseKind.REPS}  # still in the catalogue
    over = {
        f"{s.slug}: {item.exercise} {item.rep_min}-{item.rep_max}"
        for s in plan.sessions
        for item in (*s.items, *s.gym)
        if kinds[item.exercise] is ExerciseKind.REPS
        and item.exercise not in HIGH_REP
        and item.rep_max > REP_TOP
    }
    assert not over
    # Timed work is counted in seconds or minutes, so a long range there is no exception.
    tops = {item.exercise: item.rep_max for s in plan.sessions for item in s.items}
    assert tops["dead-hang"] > REP_TOP
    assert kinds["dead-hang"] is ExerciseKind.SECONDS


def test_the_rep_tops_take_effect_as_their_own_plan_version() -> None:
    versions = {v.since: v.name for v in load_plan().versions}
    assert versions[date(2026, 10, 27)].startswith("Rep tops at 18")


STRETCH = """
[[stretches]]
slug = "lat"
name = "Lat stretch"
muscles = ["MUSCLE"]
cue = "Reach."
"""


def test_stretches_must_name_muscles_the_exercises_work() -> None:
    plan = MINI_PLAN
    stretches = load_plan(plan + STRETCH.replace("MUSCLE", "lats")).stretches
    assert [s.slug for s in stretches] == ["lat"]
    with pytest.raises(ValidationError, match="no exercise works"):
        load_plan(plan + STRETCH.replace("MUSCLE", "calves"))
    with pytest.raises(ValidationError, match=r"muscles\.0"):
        load_plan(plan + STRETCH.replace("MUSCLE", "latz"))
    with pytest.raises(ValidationError, match="duplicate stretch slug"):
        load_plan(plan + (STRETCH.replace("MUSCLE", "lats") * 2))


def test_the_bundled_plan_has_a_stretch_for_every_resistance_muscle() -> None:
    plan = load_plan()
    stretched = {m for s in plan.stretches for m in s.muscles}
    exercises = {e.slug: e for e in plan.exercises}
    worked = {
        group
        for session in plan.sessions
        if session.type == "strength"
        for item in (*session.items, *session.gym)
        for group in exercises[item.exercise].muscles
    }
    assert worked - stretched == {"adductors"}  # no adductor stretch yet


DIP_FACTS = 'muscles = { chest = 1 }\npattern = "vertical push"'


@pytest.mark.parametrize(
    ("facts", "error"),
    [
        ('pattern = "vertical push"', "say which muscles or qualities"),
        ('muscles = { chest = 0.4 }\npattern = "vertical push"', "must be 1, 0.5 or 0.25"),
        ('muscles = { pecs = 1 }\npattern = "vertical push"', "muscles.pecs"),
        ('muscles = { chest = 1 }\npattern = "press"', "pattern"),
        (DIP_FACTS + '\nparts = ["triceps long head"]', "reaches the triceps long head"),
        (DIP_FACTS + '\nneeds = { "Rings" = ["rings"] }', "needs for \\['Rings'\\]"),
        (DIP_FACTS + '\nneeds = { "Feet up" = ["kettlebell"] }', "'Feet up'.*say the weight in kg"),
    ],
)
def test_catalogue_facts_are_checked(facts: str, error: str) -> None:
    with pytest.raises(ValidationError, match=error):
        load_plan(MINI_PLAN.replace(DIP_FACTS, facts))


def test_catalogue_facts_are_read() -> None:
    facts = DIP_FACTS + '\nstress = ["grip"]\nneeds = { "Feet up" = ["dip bars", "kettlebell:8"] }'
    exercises = load_plan(MINI_PLAN.replace(DIP_FACTS, facts)).exercises
    dip = next(e for e in exercises if e.slug == "dip")
    assert (dip.muscles, dip.pattern, dip.stress) == ({"chest": 1}, "vertical push", ["grip"])
    assert dip.needs == {"Feet up": ["dip bars", "kettlebell:8"]}


def test_bundled_catalogue_needs_name_real_steps_and_kit() -> None:
    """Every ladder step that holds the 8 kg kettlebell says so, and the bar steps need a bar."""
    plan = load_plan()
    for exercise in plan.exercises:
        for step in exercise.ladder:
            if "8 kg" in step and "water bottles" not in step:
                assert "kettlebell:8" in exercise.needs.get(step, []), (exercise.slug, step)
    pull_up = next(e for e in plan.exercises if e.slug == "pull-up")
    assert all("pull-up bar" in pull_up.needs[step] for step in pull_up.ladder)


def test_a_retired_exercise_cannot_be_in_a_session() -> None:
    retired = MINI_PLAN.replace(
        'ladder = ["Feet down", "Feet up"]', 'ladder = ["Feet down", "Feet up"]\nretired = true'
    )
    with pytest.raises(ValidationError, match="uses dip, which is retired"):
        load_plan(retired)


def test_the_seed_marks_retired_exercises(session: Session) -> None:
    apply_seed(session, load_plan())
    session.flush()
    retired = session.scalars(select(Exercise.slug).where(Exercise.retired.is_(True))).all()
    assert sorted(retired) == ["goblet-squat", "reverse-lunge"]
    lunge = session.scalars(select(Exercise).where(Exercise.slug == "reverse-lunge")).one()
    assert lunge.per_side


def test_every_exercise_in_a_session_says_how_to_do_it() -> None:
    """The guided session and the bot's Start message show each exercise's how-to (#116)."""
    plan = load_plan()
    used = {i.exercise for session in plan.sessions for i in (*session.items, *session.gym)}
    missing = sorted(e.slug for e in plan.exercises if e.slug in used and not e.summary)
    assert missing == []


# ------------------------------------------------------------------ plan versions (ADR-0034)

VERSIONS = """
[[versions]]
since = 2026-09-29
name = "Original plan"

[[versions]]
since = 2026-10-01
name = "Rebuild"
"""


def _workout(session: Session, on: date) -> Workout:
    workout = Workout(local_date=on, template_id=None, status=WorkoutStatus.DONE)
    session.add(workout)
    session.flush()
    session.refresh(workout)
    return workout


def _version(session: Session, workout: Workout) -> str | None:
    if workout.plan_version_id is None:
        return None
    return session.get_one(PlanVersion, workout.plan_version_id).name


def test_the_bundled_plan_starts_with_the_original_and_the_rebuild() -> None:
    versions = [(v.since, v.name) for v in load_plan().versions][:2]
    assert versions == [
        (date(2026, 9, 29), "Original plan"),
        (date(2026, 10, 1), "Rebuild (Oct 2026, ADR-0017)"),
    ]


def test_a_workout_records_the_version_in_force_on_its_date(session: Session) -> None:
    apply_seed(session, load_plan(VERSIONS + MINI_PLAN))
    # A past day logged late gets the version of its own date, not today's.
    assert _version(session, _workout(session, date(2026, 9, 30))) == "Original plan"
    assert _version(session, _workout(session, date(2026, 10, 1))) == "Rebuild"
    assert _version(session, _workout(session, date(2026, 10, 9))) == "Rebuild"
    assert _version(session, _workout(session, date(2026, 9, 1))) is None  # before any


def test_the_seed_fills_in_workouts_saved_before_their_version(session: Session) -> None:
    apply_seed(session, load_plan(MINI_PLAN))
    early, late = _workout(session, date(2026, 9, 30)), _workout(session, date(2026, 10, 2))
    before = _workout(session, date(2026, 9, 1))
    assert _version(session, early) is None
    result = apply_seed(session, load_plan(VERSIONS + MINI_PLAN))
    assert result.updated == 2
    for workout in (early, late, before):
        session.refresh(workout)
    assert (_version(session, early), _version(session, late)) == ("Original plan", "Rebuild")
    assert _version(session, before) is None
    assert not apply_seed(session, load_plan(VERSIONS + MINI_PLAN)).changed


def test_a_recorded_version_keeps_its_date_but_can_be_renamed(session: Session) -> None:
    apply_seed(session, load_plan(VERSIONS + MINI_PLAN))
    _workout(session, date(2026, 9, 30))
    renamed = VERSIONS.replace("Original plan", "First plan")
    assert apply_seed(session, load_plan(renamed + MINI_PLAN)).updated == 1
    redated = renamed.replace("2026-09-29", "2026-09-28")
    with pytest.raises(SeedError, match=re.escape("'First plan' (since 2026-09-29) is recorded")):
        apply_seed(session, load_plan(redated + MINI_PLAN))


def test_an_unrecorded_version_can_be_removed(session: Session) -> None:
    apply_seed(session, load_plan(VERSIONS + MINI_PLAN))
    only_original = VERSIONS.split("[[versions]]")[1]
    result = apply_seed(session, load_plan("[[versions]]" + only_original + MINI_PLAN))
    assert result.deleted == 1
    assert session.scalars(select(PlanVersion.name)).all() == ["Original plan"]


def test_versions_must_be_in_date_order() -> None:
    swapped = VERSIONS.replace("2026-09-29", "2026-10-02")
    with pytest.raises(ValidationError, match="in date order"):
        load_plan(swapped + MINI_PLAN)


def test_a_version_added_between_two_others_takes_over_its_workouts(session: Session) -> None:
    apply_seed(session, load_plan(VERSIONS + MINI_PLAN))
    before, after = _workout(session, date(2026, 10, 3)), _workout(session, date(2026, 10, 6))
    between = (
        VERSIONS
        + """
[[versions]]
since = 2026-10-05
name = "Heavier bell"
"""
    )
    assert apply_seed(session, load_plan(between + MINI_PLAN)).updated == 1
    for workout in (before, after):
        session.refresh(workout)
    assert (_version(session, before), _version(session, after)) == ("Rebuild", "Heavier bell")


# ------------------------------------------------------------------ baseline tests (#94)

HANG_TEST = """
[[tests]]
slug = "dead-hang"
name = "Dead hang"
day = 1
unit = "seconds"
cue = "Hang."
"""


@pytest.mark.parametrize(
    ("tests", "message"),
    [
        (HANG_TEST + HANG_TEST, "duplicate test slug"),
        (HANG_TEST.replace("day = 1", "day = 3"), "day must be one of"),
        (HANG_TEST.replace('"seconds"', '"kg"'), "unit"),
    ],
)
def test_invalid_tests_are_rejected(tests: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        load_plan(tests + MINI_PLAN)


def test_a_test_with_results_cant_leave_the_plan(session: Session) -> None:
    apply_seed(session, load_plan(HANG_TEST + MINI_PLAN))
    session.add(
        FitnessTestDay(
            local_date=date(2026, 10, 10),
            day=1,
            time_of_day="morning",
            fed=True,
            slept_well=True,
            results=[{"test": "dead-hang", "side": "both", "value": 40}],
            token="x" * 20,
        )
    )
    session.flush()
    with pytest.raises(SeedError, match="'dead-hang'"):
        apply_seed(session, load_plan(MINI_PLAN))
    apply_seed(session, load_plan(HANG_TEST.replace("Hang.", "Hang still.") + MINI_PLAN))


def test_cardio_targets_are_not_in_the_plan_file_any_more() -> None:
    """They come from the cycle's sessions and the person's extra cardio (ADR-0079)."""
    with pytest.raises(ValidationError, match="targets"):
        load_plan("[targets]\nzone2_minutes = [180, 200]\n" + MINI_PLAN)


# ------------------------------------------------------------- mobility flow (ADR-0062)

FLOW = """
[mobility]
exercise = "EXERCISE"
safety = "Stop if it hurts."

[[mobility.moves]]
slug = "cat-cow"
name = "Cat-cow"
seconds = SECONDS
target = "Spine"
start = "All fours, back rounded."
end = "All fours, back arched."
cues = ["Slowly."]
breathing = "Out as you round."
easier = "Smaller."
pacing = "Slow reps."
"""


def _flow(exercise: str = "walk", seconds: int = 60) -> str:
    walk = """
[[exercises]]
slug = "walk"
name = "Walk"
kind = "duration_min"
qualities = ["conditioning"]
pattern = "cardio"
start = 0
ladder = ["Easy"]
"""
    return MINI_PLAN + walk + FLOW.replace("EXERCISE", exercise).replace("SECONDS", str(seconds))


def test_the_mobility_flow_is_logged_as_an_exercise_in_minutes() -> None:
    flow = load_plan(_flow()).mobility
    assert flow is not None
    assert (flow.exercise, flow.flow().seconds) == ("walk", 60)
    with pytest.raises(ValidationError, match="must be an exercise counted in minutes"):
        load_plan(_flow("pull-up"))
    with pytest.raises(ValidationError, match="must be an exercise counted in minutes"):
        load_plan(_flow("nothing"))
    with pytest.raises(ValidationError, match="must last whole minutes, not 45 s"):
        load_plan(_flow(seconds=45))


def test_a_flow_movement_is_named_once() -> None:
    again = FLOW[FLOW.index("[[mobility.moves]]") :].replace("SECONDS", "60")
    twice = _flow() + again
    with pytest.raises(ValidationError, match="duplicate flow movement slug"):
        load_plan(twice)


def test_the_bundled_flow_is_ten_minutes_standing_to_lying() -> None:
    flow = load_plan().mobility
    assert flow is not None
    found = flow.flow()
    assert found.seconds == 600
    assert len(found.moves) == 8
    assert [m.slug for m in found.moves if m.per_side] == [
        "half-kneeling-hip-flexor",
        "kneeling-lunge-rotation",
        "quadruped-t-spine-rotation",
        "hamstring-floss",
    ]


def test_split_squats_load_the_spine_only_with_a_kettlebell() -> None:
    """program-builder.md, Decided 3: loaded squats count; bodyweight and jump squats don't."""
    exercises = {e.slug: e for e in load_plan().exercises}
    split = exercises["bulgarian-split-squat"]
    assert [bool(split.step_stress(s)) for s in split.ladder] == [False, *[True] * 5]
    jump = exercises["jump-squat"]
    assert not any(jump.step_stress(s) for s in jump.ladder)
    assert all(exercises["kb-swing"].step_stress(s) for s in exercises["kb-swing"].ladder)


def test_the_gym_catalogue_takes_load_on_its_last_step_in_the_gym_versions_only() -> None:
    """ADR-0072: a loaded exercise is one step, or a ladder whose top step takes load; the gym
    exercises are in the sessions' gym versions (builder step 9), never the home ones."""
    plan = load_plan()
    loaded = [e for e in plan.exercises if e.loads]
    assert len(loaded) == 23
    assert all(list(e.loads) == [e.ladder[-1]] for e in loaded)
    at_home = {i.exercise for s in plan.sessions for i in s.items}
    assert not at_home & {e.slug for e in loaded}
    at_the_gym = {i.exercise for s in plan.sessions for i in s.gym}
    unused = {e.slug for e in loaded} - at_the_gym
    assert unused == {"hammer-curl", "wrist-curl", "chest-fly"}  # in the catalogue for later
    assert {e.slug for e in loaded if "triceps long head" in e.parts} == {
        "overhead-cable-extension"
    }


# ------------------------------------------------------------- gym versions (ADR-0071)


def test_four_sessions_have_a_gym_version_and_three_are_the_same_at_both() -> None:
    gym = {s.slug for s in load_plan().sessions if s.gym}
    assert gym == {"legs", "torso", "moderate-cardio", "arms"}


def test_a_gym_version_keeps_its_sessions_muscles() -> None:
    """No muscle loses more than a set and a half against the home version (ADR-0064), so the
    week's coverage holds wherever each session is done."""
    plan = load_plan()
    exercises = {e.slug: e.muscles for e in plan.exercises}
    for session in plan.sessions:
        if not session.gym:
            continue
        home = dict(weekly_sets((exercises[i.exercise], i.sets) for i in session.items))
        gym = dict(weekly_sets((exercises[i.exercise], i.sets) for i in session.gym))
        short = {m: (home[m], gym.get(m, 0)) for m in home if gym.get(m, 0) < home[m] - 1.5}
        assert not short, (session.slug, short)


def test_a_gym_version_pairs_by_the_home_rules() -> None:
    """Pairs (program-builder J3): at most one spine-loading or grip-heavy exercise, and no
    shared prime mover unless the home version pairs the same two (the neck pair)."""
    plan = load_plan()
    exercises = {e.slug: e for e in plan.exercises}
    for session in plan.sessions:
        home_pairs = {
            (a.exercise, b.exercise) for a, b in zip(session.items, session.items[1:], strict=False)
        }
        for a, b in zip(session.gym, session.gym[1:], strict=False):
            if a.pair is None or a.pair != b.pair:
                continue
            first, second = exercises[a.exercise], exercises[b.exercise]
            for stress in ("spine", "grip"):
                assert not (stress in first.stress and stress in second.stress), (a, b)
            primes = {m for m, w in first.muscles.items() if w == 1}
            shared = primes & {m for m, w in second.muscles.items() if w == 1}
            assert not shared or (a.exercise, b.exercise) in home_pairs, (a, b)


def test_the_seed_stores_each_version_with_its_place(session: Session) -> None:
    apply_seed(session, load_plan())
    session.flush()
    legs = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "legs")).one()
    assert {i.place for i in legs.items} == {"home"}
    assert {i.place for i in legs.gym_items} == {"gym"}
    assert [i.exercise.slug for i in legs.gym_items][2] == "back-squat"
    zone2 = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "zone2")).one()
    assert zone2.gym_items == []
    assert apply_seed(session, load_plan()).changed is False  # idempotent


def _upper_gym(gym: str) -> str:
    """The mini plan with a gym version of its upper session."""
    return _upper_items(f"{PULL} }}]\ngym = [{gym}")


def test_a_gym_version_shrinks_and_goes_like_a_home_one(session: Session) -> None:
    apply_seed(session, load_plan(_upper_gym(f"{PULL}, pair = 1 }}, {DIP}, pair = 1 }}")))
    session.flush()
    upper = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "upper")).one()
    assert [(i.position, i.pair) for i in upper.gym_items] == [(0, 1), (1, 1)]
    assert [i.position for i in upper.items] == [0]
    result = apply_seed(session, load_plan(_upper_items(f"{PULL} }}")))
    session.flush()
    session.expire_all()
    assert result.deleted == 2
    assert upper.gym_items == []
    assert [i.position for i in upper.items] == [0]


def test_a_gym_version_names_known_exercises_in_pairs() -> None:
    with pytest.raises(ValidationError, match="unknown exercise squat"):
        load_plan(_upper_gym('{ exercise = "squat", sets = 3, rep_min = 5, rep_max = 8 }'))
    with pytest.raises(ValidationError, match="pair 1 must be two neighbouring items"):
        load_plan(_upper_gym(f"{PULL}, pair = 1 }}"))
