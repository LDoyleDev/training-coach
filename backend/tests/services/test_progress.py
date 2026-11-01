"""Bests and progression after a save, and the Move up / Not yet answers (#13, ADR-0025)."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    LadderStep,
    SessionTemplate,
    SetLog,
    TemplateItem,
    Workout,
)
from training_coach.domain.enums import Places, Side, WorkoutStatus
from training_coach.domain.progression import Progress
from training_coach.domain.records import NewBests
from training_coach.services import progress, user_settings, users
from training_coach.services.progress import MoveOutcome, feedback, move_up, not_yet, overview
from training_coach.services.seed import apply_seed, load_plan

DAY = date(2026, 10, 1)


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _exercise(session: Session, slug: str) -> Exercise:
    exercise = session.scalar(select(Exercise).where(Exercise.slug == slug))
    assert exercise is not None
    return exercise


def _step(session: Session, slug: str) -> LadderStep:
    state = users.exercise_state(session, _exercise(session, slug).id)
    assert state is not None
    step = session.get(LadderStep, state.ladder_step_id)
    assert step is not None
    return step


def _template(session: Session, slug: str) -> int:
    template_id = session.scalar(select(SessionTemplate.id).where(SessionTemplate.slug == slug))
    assert template_id is not None
    return template_id


def _log(
    session: Session,
    slug: str,
    values: list[int],
    days: int,
    *,
    template: str | None = "torso",
    sides: tuple[Side, ...] = (Side.BOTH,),
    step: LadderStep | None = None,
    planned: dict[str, dict[str, int]] | None = None,
) -> int:
    exercise = _exercise(session, slug)
    at = step or _step(session, slug)
    workout = Workout(
        local_date=DAY + timedelta(days=days),
        template_id=_template(session, template) if template else None,
        status=WorkoutStatus.DONE,
        planned=planned,
    )
    workout.sets = [
        SetLog(exercise_id=exercise.id, ladder_step_id=at.id, set_no=n, side=side, value=v)
        for n, v in enumerate(values, start=1)
        for side in sides
    ]
    session.add(workout)
    session.flush()
    return workout.id


TOP = [12, 12, 12, 12]  # pull-up in Torso: 4 sets of 5-12


def test_the_first_session_at_a_step_is_not_a_best_and_holds(plan: Session) -> None:
    (item,) = feedback(plan, _log(plan, "pull-up", [8, 7, 6, 6], 0))
    assert item.exercise == "Pull-up"
    assert item.bests == NewBests()
    assert item.status is Progress.HOLD
    assert item.next_step is None


def test_beating_earlier_sessions_is_a_best(plan: Session) -> None:
    _log(plan, "pull-up", [8, 7, 6, 6], 0)
    (item,) = feedback(plan, _log(plan, "pull-up", [9, 7, 6, 6], 2))
    assert item.bests == NewBests(best_set=9, total=28)


def test_two_sessions_at_the_top_are_ready(plan: Session) -> None:
    _log(plan, "pull-up", TOP, 0)
    (item,) = feedback(plan, _log(plan, "pull-up", TOP, 2))
    assert item.status is Progress.READY
    assert item.next_step == "Pause at top"


def test_18_reps_on_every_set_twice_is_ready(plan: Session) -> None:
    """ADR-0078: push-ups top out at 18 now, so 18 on all four sets twice offers Move up;
    sessions logged under the old 10-20 range count against today's top too."""
    _log(plan, "push-up", [18, 18, 18, 18], 0)
    (short,) = feedback(plan, _log(plan, "push-up", [18, 18, 18, 17], 2))
    assert short.status is Progress.HOLD
    _log(plan, "push-up", [20, 19, 18, 18], 4)
    (item,) = feedback(plan, _log(plan, "push-up", [18, 18, 18, 18], 6))
    assert item.status is Progress.READY
    assert item.next_step == "Feet elevated"


def test_an_extra_session_is_judged_by_the_plan(plan: Session) -> None:
    _log(plan, "pull-up", TOP, 0, template=None)
    (item,) = feedback(plan, _log(plan, "pull-up", TOP, 2, template=None))
    assert item.status is Progress.READY


def test_a_shorter_day_at_the_top_of_its_two_sets_counts_toward_ready(plan: Session) -> None:
    """ADR-0084: a day that planned two of pull-up's four sets is judged on those two."""
    _log(plan, "pull-up", [12, 12], 0, planned={"pull-up": {"sets": 2}})
    (item,) = feedback(plan, _log(plan, "pull-up", TOP, 2))
    assert item.status is Progress.READY


def test_an_old_two_set_row_without_a_plan_still_holds(plan: Session) -> None:
    """A workout saved without its plan planned every set: two sets of four is a miss."""
    _log(plan, "pull-up", [12, 12], 0)
    (item,) = feedback(plan, _log(plan, "pull-up", TOP, 2))
    assert item.status is Progress.HOLD


def test_planned_sets_read_each_workouts_plan_in_the_order_given(plan: Session) -> None:
    short = _log(plan, "pull-up", [12], 0, planned={"pull-up": {"sets": 2}})
    other = _log(plan, "pull-up", [12], 1, planned={"push-up": {"sets": 3}})
    old = _log(plan, "pull-up", [12], 2)
    found = progress.planned_sets(plan, "pull-up", [old, short, other])
    assert found == [None, 2, None]  # no plan, and a plan not naming it: every set planned


def test_one_side_short_holds_unilateral_work(plan: Session) -> None:
    """kb-row is per side: the weaker side counts (ADR-0016)."""
    both = (Side.LEFT, Side.RIGHT)
    _log(plan, "kb-row", [18, 18, 18], 0, sides=both)  # 10-18 (ADR-0078)
    workout = _log(plan, "kb-row", [18, 18, 18], 2, sides=both)
    row = plan.scalar(select(SetLog).where(SetLog.workout_id == workout, SetLog.side == Side.LEFT))
    assert row is not None
    row.value = 17
    plan.flush()
    (item,) = feedback(plan, workout)
    assert item.status is Progress.HOLD


def test_a_log_at_an_older_step_counts_for_bests_only(plan: Session) -> None:
    old = _step(plan, "pull-up")
    _log(plan, "pull-up", TOP, 0, step=old)
    state = users.exercise_state(plan, old.exercise_id)
    assert state is not None
    state.ladder_step_id = plan.scalars(
        select(LadderStep.id).where(
            LadderStep.exercise_id == old.exercise_id, LadderStep.position == old.position + 1
        )
    ).one()
    (item,) = feedback(plan, _log(plan, "pull-up", TOP, 2, step=old))
    assert item.status is Progress.HOLD


PUSH_TOP = [18, 18, 18, 18]  # push-up in Torso: 4 sets of 10-18; its top step takes no load


def _on_top(session: Session, slug: str) -> None:
    exercise = _exercise(session, slug)
    state = users.exercise_state(session, exercise.id)
    assert state is not None
    state.ladder_step_id = max(exercise.ladder, key=lambda s: s.position).id


def test_the_top_of_the_ladder_is_said_once(plan: Session) -> None:
    _on_top(plan, "push-up")
    _log(plan, "push-up", PUSH_TOP, 0)
    (first,) = feedback(plan, _log(plan, "push-up", PUSH_TOP, 2))
    (again,) = feedback(plan, _log(plan, "push-up", PUSH_TOP, 4))
    assert first.status is again.status is Progress.TOP_OF_LADDER
    assert (first.note_top, again.note_top) == (True, False)


def test_feedback_lists_each_exercise_once_in_logged_order(plan: Session) -> None:
    workout = _log(plan, "dip", [10, 10, 10], 0)
    _log(plan, "pull-up", [5], 0)
    pull = plan.scalars(select(SetLog).join(Workout).where(Workout.id != workout)).all()
    for row in pull:
        row.workout_id = workout
    plan.flush()
    plan.expire_all()
    assert [i.exercise for i in feedback(plan, workout)] == ["Dip (chairs)", "Pull-up"]


def test_feedback_for_a_missing_workout_is_empty(plan: Session) -> None:
    assert feedback(plan, 999) == []


def test_move_up_when_ready(plan: Session) -> None:
    step = _step(plan, "pull-up")
    _log(plan, "pull-up", TOP, 0)
    _log(plan, "pull-up", TOP, 2)
    move = move_up(plan, step.exercise_id, step.id)
    assert move is not None
    assert (move.outcome, move.exercise, move.step) == (
        MoveOutcome.MOVED,
        "Pull-up",
        "Pause at top",
    )
    assert _step(plan, "pull-up").name == "Pause at top"
    kinds = plan.scalars(select(Event.kind)).all()
    assert "progress.moved_up" in kinds


def test_a_second_press_does_not_move_twice(plan: Session) -> None:
    step = _step(plan, "pull-up")
    _log(plan, "pull-up", TOP, 0)
    _log(plan, "pull-up", TOP, 2)
    move_up(plan, step.exercise_id, step.id)
    again = move_up(plan, step.exercise_id, step.id)
    assert again is not None
    assert again.outcome is MoveOutcome.ALREADY_MOVED
    assert _step(plan, "pull-up").name == "Pause at top"


def test_move_up_rechecks_the_rule(plan: Session) -> None:
    step = _step(plan, "pull-up")
    _log(plan, "pull-up", TOP, 0)
    _log(plan, "pull-up", [12, 12, 12, 11], 2)
    move = move_up(plan, step.exercise_id, step.id)
    assert move is not None
    assert move.outcome is MoveOutcome.NOT_READY
    assert _step(plan, "pull-up").id == step.id


def test_move_up_at_the_last_step(plan: Session) -> None:
    exercise = _exercise(plan, "pull-up")
    last = max(exercise.ladder, key=lambda s: s.position)
    state = users.exercise_state(plan, exercise.id)
    assert state is not None
    state.ladder_step_id = last.id
    move = move_up(plan, exercise.id, last.id)
    assert move is not None
    assert move.outcome is MoveOutcome.NO_NEXT_STEP


def test_move_up_for_an_unknown_exercise(plan: Session) -> None:
    assert move_up(plan, 999, 1) is None


def test_not_yet_records_the_choice(plan: Session) -> None:
    step = _step(plan, "pull-up")
    assert not_yet(plan, step.exercise_id, step.id) == "Pull-up (Strict pull-up)"
    assert plan.scalars(select(Event.kind).where(Event.kind == "progress.not_yet")).one()
    dip = _step(plan, "dip")
    assert not_yet(plan, step.exercise_id, dip.id) is None  # a step of another exercise
    assert not_yet(plan, 999, step.id) is None


def test_a_backdated_log_is_compared_with_earlier_sessions_only(plan: Session) -> None:
    """ADR-0025: a record beats every *earlier* session; a later, better one doesn't count."""
    _log(plan, "pull-up", [10, 10, 10, 10], 0)
    _log(plan, "pull-up", [12, 12, 12, 12], 4)
    (item,) = feedback(plan, _log(plan, "pull-up", [11, 10, 10, 10], 2))
    assert item.bests == NewBests(best_set=11, total=41)


def test_overview_lists_every_exercise_in_plan_order(plan: Session) -> None:
    standings = overview(plan)
    at_home = set(
        plan.scalars(select(TemplateItem.exercise_id).where(TemplateItem.place == "home"))
    )
    # Retired ones, ones in no session (ADR-0072) and, for someone who trains at home, ones only
    # in the gym versions (ADR-0071), only once they have history (#107).
    assert len(standings) == len(at_home)
    user_settings.update(plan, places=Places.BOTH)
    # Ones only in the away versions (ADR-0086) show once they have history, wherever you train.
    trained = select(TemplateItem.exercise_id).where(TemplateItem.place != "away")
    assert len(overview(plan)) == len(set(plan.scalars(trained)))
    names = [s.exercise for s in standings]
    assert names.index("Pull-up") < names.index("Dip (chairs)")  # Torso lists pull-ups first
    pull = standings[names.index("Pull-up")]
    assert (pull.step, pull.step_number, pull.steps) == ("Strict pull-up", 2, 4)
    assert (pull.last, pull.best_set, pull.status) == ((), None, Progress.HOLD)


def test_overview_shows_last_session_best_and_readiness(plan: Session) -> None:
    _log(plan, "pull-up", [12, 12, 12, 12], 0)
    _log(plan, "pull-up", [12, 12, 12, 12], 2)
    _log(plan, "dip", [15, 9, 8], 0)
    _log(plan, "dip", [10, 10, 10], 2)
    by_name = {s.exercise: s for s in overview(plan)}
    assert by_name["Pull-up"].status is Progress.READY
    dip = by_name["Dip (chairs)"]
    assert (dip.last, dip.best_set, dip.status) == ((10, 10, 10), 15, Progress.HOLD)
    assert dip.trend == ()  # only with today's date


def test_the_trend_is_six_weeks_of_best_sets_across_steps(plan: Session) -> None:
    on = DAY + timedelta(days=50)  # six weeks back reaches day 9
    start = _step(plan, "dip")
    harder = next(
        s
        for s in sorted(start.exercise.ladder, key=lambda s: s.position)
        if s.position > start.position
    )
    _log(plan, "dip", [20], 8)  # a day before the window
    _log(plan, "dip", [10, 12], 9)
    _log(plan, "dip", [6], 20, step=harder)
    dip = next(s for s in overview(plan, on) if s.exercise == "Dip (chairs)")
    assert [(p.day, p.best, p.step_number) for p in dip.trend] == [
        (DAY + timedelta(days=9), 12, start.position + 1),
        (DAY + timedelta(days=20), 6, harder.position + 1),  # moved up: fewer reps, harder step
    ]


def test_each_point_on_the_trend_carries_its_sessions_heaviest_weight(plan: Session) -> None:
    """For the chart's period per weight (ADR-0072); empty for bodyweight sessions."""
    on = DAY + timedelta(days=50)
    _log(plan, "dip", [10], 20)
    loaded = _log(plan, "dip", [8, 8], 30)
    for row, kg in zip(plan.get_one(Workout, loaded).sets, (10.0, 12.5), strict=True):
        row.load_kg = kg
    plan.flush()
    dip = next(s for s in overview(plan, on) if s.exercise == "Dip (chairs)")
    assert [p.kg for p in dip.trend] == [None, 12.5]


def _weigh(session: Session, workout_id: int, kg: list[float | None]) -> None:
    """Each set's weight, by set number, on both sides of a one-sided set."""
    for row in session.get_one(Workout, workout_id).sets:
        row.load_kg = kg[row.set_no - 1]
    session.flush()


def test_overview_gives_the_last_sessions_weight_per_set(plan: Session) -> None:
    """For "Last 10 · 10 · 9 at 16 kg" (ADR-0072); a dash's place for a set without one."""
    _weigh(plan, _log(plan, "dip", [8, 8], 0), [12.0, 12.0])
    _weigh(plan, _log(plan, "dip", [10, 10, 9], 2), [16.0, 16.0, None])
    dip = next(s for s in overview(plan) if s.exercise == "Dip (chairs)")
    assert (dip.last, dip.last_kg) == ((10, 10, 9), (16.0, 16.0, None))


def test_a_one_sided_sets_weight_is_given_once(plan: Session) -> None:
    sides = (Side.LEFT, Side.RIGHT)
    _weigh(plan, _log(plan, "dip", [8, 7], 0, sides=sides), [10.0, 12.5])
    dip = next(s for s in overview(plan) if s.exercise == "Dip (chairs)")
    assert dip.last_kg == (10.0, 12.5)


def test_a_one_sided_set_with_two_weights_gives_the_heavier(plan: Session) -> None:
    """A weight covers both sides; if they ever differ, the heavier, whichever row is last."""
    workout = _log(plan, "dip", [8], 0, sides=(Side.LEFT, Side.RIGHT))
    for row in sorted(plan.get_one(Workout, workout).sets, key=lambda r: r.id):
        row.load_kg = 12.5 if row.side == Side.LEFT else 10.0
    plan.flush()
    dip = next(s for s in overview(plan) if s.exercise == "Dip (chairs)")
    assert (dip.last_kg, dip.best_kg) == ((12.5,), 12.5)


def test_the_best_names_the_weight_of_the_session_that_set_it(plan: Session) -> None:
    """As the weekly review does (ADR-0072): the best counts every weight, so it says which,
    the heaviest set's of the first session to reach it; a later tie sets no best."""
    _weigh(plan, _log(plan, "dip", [12, 10], 0), [10.0, 12.0])
    _weigh(plan, _log(plan, "dip", [12, 12], 2), [16.0, 16.0])
    _weigh(plan, _log(plan, "dip", [9, 9], 4), [18.0, 18.0])
    dip = next(s for s in overview(plan) if s.exercise == "Dip (chairs)")
    assert (dip.best_set, dip.best_kg, dip.last_kg) == (12, 12.0, (18.0, 18.0))


def test_an_exercise_without_weights_names_none(plan: Session) -> None:
    _log(plan, "dip", [10, 9], 0)
    dip = next(s for s in overview(plan) if s.exercise == "Dip (chairs)")
    assert (dip.last_kg, dip.best_kg) == ((None, None), None)
    pull = next(s for s in overview(plan) if s.exercise == "Pull-up")
    assert (pull.last_kg, pull.best_kg) == ((), None)  # not logged at this step yet


def test_overview_reports_the_top_of_the_ladder(plan: Session) -> None:
    _on_top(plan, "push-up")
    _log(plan, "push-up", PUSH_TOP, 0)
    _log(plan, "push-up", PUSH_TOP, 2)
    by_name = {s.exercise: s for s in overview(plan)}
    assert by_name["Push-up"].status is Progress.TOP_OF_LADDER


def test_the_vest_step_at_the_top_is_never_the_top_of_the_ladder(plan: Session) -> None:
    """ADR-0072 (29 Oct 2026): the pull-up's last step takes load, so it gets harder by weight."""
    _on_top(plan, "pull-up")
    _log(plan, "pull-up", TOP, 0)
    _log(plan, "pull-up", TOP, 2)
    by_name = {s.exercise: s for s in overview(plan)}
    assert (by_name["Pull-up"].step, by_name["Pull-up"].status) == (
        "Vest or backpack",
        Progress.HOLD,
    )


# ------------------------------------------------------------------ retired exercises (#107)


def test_a_retired_exercise_shows_its_history_but_is_never_ready(plan: Session) -> None:
    for days in (0, 2):  # the top of the old 12-20 range twice: ready, were it still planned
        _log(plan, "goblet-squat", [20, 20, 20], days, template="legs")
    by_name = {s.exercise: s for s in overview(plan)}
    goblet = by_name["Goblet squat"]
    assert (goblet.retired, goblet.status, goblet.last) == (True, Progress.HOLD, (20, 20, 20))
    assert "Reverse lunge" not in by_name  # retired with no history: nothing to show
    workout_id = _log(plan, "goblet-squat", [20, 20, 20], 4, template="legs")
    (said,) = feedback(plan, workout_id)
    assert said.status is Progress.HOLD
    step = _step(plan, "goblet-squat")
    move = move_up(plan, step.exercise_id, step.id)
    assert move is not None
    assert move.outcome is MoveOutcome.NOT_READY


def test_a_one_sided_retired_exercise_keeps_its_sides(plan: Session) -> None:
    lunge = _exercise(plan, "reverse-lunge")
    assert progress.per_side_for(plan, lunge.id, None)
    assert not progress.per_side_for(plan, _exercise(plan, "goblet-squat").id, None)


def _last_step(session: Session, slug: str) -> LadderStep:
    return max(_exercise(session, slug).ladder, key=lambda s: s.position)


def test_a_level_can_be_set_up_or_down_without_being_ready(plan: Session) -> None:
    """ADR-0075: choosing a level by hand never needs "ready"; each change is an event."""
    start = _step(plan, "pull-up")
    top = _last_step(plan, "pull-up")
    up = progress.set_level(plan, start.exercise_id, top.id)
    assert up is not None
    assert (up.outcome, up.step) == (MoveOutcome.LEVEL_SET, top.name)
    assert _step(plan, "pull-up").id == top.id
    down = progress.set_level(plan, start.exercise_id, start.id)
    assert down is not None
    assert down.outcome is MoveOutcome.LEVEL_SET
    assert _step(plan, "pull-up").id == start.id
    payloads = plan.scalars(select(Event.payload).where(Event.kind == progress.LEVEL_SET)).all()
    assert [(p["from_step_id"], p["to_step_id"]) for p in payloads] == [
        (start.id, top.id),
        (top.id, start.id),
    ]
    assert plan.scalars(select(Event).where(Event.kind == "progress.moved_up")).all() == []


def test_setting_the_level_it_is_on_changes_nothing(plan: Session) -> None:
    step = _step(plan, "pull-up")
    same = progress.set_level(plan, step.exercise_id, step.id)
    assert same is not None
    assert same.outcome is MoveOutcome.SAME_LEVEL
    assert plan.scalars(select(Event).where(Event.kind == progress.LEVEL_SET)).all() == []


def test_a_step_of_another_exercise_is_refused(plan: Session) -> None:
    pull_up = _step(plan, "pull-up")
    dip = _step(plan, "dip")
    assert progress.set_level(plan, pull_up.exercise_id, dip.id) is None
    assert progress.set_level(plan, 999, dip.id) is None
    assert progress.stay(plan, pull_up.exercise_id, dip.id) is None
    assert _step(plan, "pull-up").id == pull_up.id


def test_not_yet_from_a_stale_page_changes_nothing(plan: Session) -> None:
    step = _step(plan, "pull-up")
    stayed = progress.stay(plan, step.exercise_id, step.id)
    assert stayed is not None
    assert (stayed.outcome, stayed.step) == (MoveOutcome.STAYED, "Strict pull-up")
    progress.set_level(plan, step.exercise_id, _last_step(plan, "pull-up").id)
    stale = progress.stay(plan, step.exercise_id, step.id)
    assert stale is not None
    assert stale.outcome is MoveOutcome.ALREADY_MOVED
    assert len(plan.scalars(select(Event).where(Event.kind == "progress.not_yet")).all()) == 1


def test_overview_carries_the_slug_and_the_whole_ladder(plan: Session) -> None:
    pull_up = next(s for s in overview(plan) if s.exercise == "Pull-up")
    assert pull_up.slug == "pull-up"
    assert [r.name for r in pull_up.ladder][:2] == ["Slow negatives", "Strict pull-up"]
    assert len(pull_up.ladder) == pull_up.steps
    assert progress.exercise_id_for(plan, "pull-up") == pull_up.exercise_id
    assert progress.exercise_id_for(plan, "no-such") is None
