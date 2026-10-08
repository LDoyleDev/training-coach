"""Stretching after a session (#98), against the bundled plan."""

from datetime import date

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, SessionTemplate, SetLog, User, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import stretching
from training_coach.services.seed import apply_seed, load_plan


def _template(session: Session, slug: str) -> int:
    apply_seed(session, load_plan())
    session.flush()
    return session.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == slug)).one()


def test_legs_works_quads_and_glutes_most(session: Session) -> None:
    worked = stretching.worked(session, _template(session, "legs"))
    assert worked is not None
    plan = load_plan()
    groups = {e.slug: e.muscle_groups for e in plan.exercises}
    legs = next(p for p in plan.sessions if p.slug == "legs")
    assert worked["glutes"] == sum(i.sets for i in legs.items if "glutes" in groups[i.exercise])
    assert worked.most_common(1)[0][0] == "glutes"


def test_legs_stretching_starts_with_the_legs(session: Session) -> None:
    steps = stretching.for_session(session, _template(session, "legs"), 10)
    assert steps is not None
    muscles = set().union(*(s.stretch.muscles for s in steps))
    assert {"glutes", "quads", "hamstrings"} <= muscles
    assert sum(s.seconds for s in steps) <= 600


def test_torso_stretching_starts_with_the_upper_body(session: Session) -> None:
    steps = stretching.for_session(session, _template(session, "torso"), 10)
    assert steps is not None
    assert steps[0].stretch.muscles & {"lats", "upper back", "chest", "triceps"}


def test_every_choice_fits_and_longer_choices_cover_more(session: Session) -> None:
    arms = _template(session, "arms")
    sizes = []
    for minutes in (10, 20, 30):
        steps = stretching.for_session(session, arms, minutes)
        assert steps is not None
        assert sum(s.seconds for s in steps) <= minutes * 60
        sizes.append(len(steps))
    assert sizes == sorted(sizes)
    assert sizes[0] < sizes[-1]


def test_an_unknown_session_has_no_routine(session: Session) -> None:
    assert stretching.for_session(session, 999_999, 10) is None


def _workout(session: Session, slug: str, status: WorkoutStatus = WorkoutStatus.DONE) -> int:
    template = _template(session, slug)
    workout = Workout(local_date=date(2026, 10, 8), template_id=template, status=status)
    session.add(workout)
    session.flush()
    return workout.id


def _stretching_sets(session: Session, workout_id: int) -> list[int]:
    mobility = session.scalars(select(Exercise.id).where(Exercise.slug == "mobility")).one()
    query = select(SetLog.value).where(
        SetLog.workout_id == workout_id, SetLog.exercise_id == mobility
    )
    return list(session.scalars(query))


def test_stretching_is_offered_only_after_a_saved_resistance_session(session: Session) -> None:
    assert stretching.offered(session, _workout(session, "legs"))
    assert not stretching.offered(session, _workout(session, "zone2"))
    assert not stretching.offered(session, _workout(session, "recovery"))
    assert not stretching.offered(session, _workout(session, "torso", WorkoutStatus.REST))
    assert not stretching.offered(session, 999_999)


def test_the_routine_names_the_session_and_the_time(session: Session) -> None:
    routine = stretching.for_workout(session, _workout(session, "legs"), 20)
    assert routine is not None
    assert (routine.session, routine.minutes) == ("Legs", 20)
    assert sum(step.seconds for step in routine.steps) <= 20 * 60
    assert stretching.for_workout(session, _workout(session, "legs"), 15) is None  # not a choice


def test_done_adds_the_minutes_once(session: Session) -> None:
    legs = _workout(session, "legs")
    assert stretching.log(session, legs, 10) is True
    assert stretching.log(session, legs, 20) is False
    assert _stretching_sets(session, legs) == [10]


def test_done_refuses_what_it_cannot_log(session: Session) -> None:
    assert stretching.log(session, _workout(session, "zone2"), 10) is None
    assert stretching.log(session, _workout(session, "legs"), 7) is None
    assert stretching.log(session, 999_999, 10) is None


def test_another_persons_workout_is_not_there(engine: Engine) -> None:
    """Workout ids travel in button data; a bound session never reaches someone else's."""
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
        apply_seed(shared, load_plan())
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        legs = theirs.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == "legs"))
        workout = Workout(local_date=date(2026, 10, 8), template_id=legs.one(), status="done")
        theirs.add(workout)
        theirs.flush()
        their_id = workout.id
    with session_scope(make_session_factory(engine, user_id=1)) as mine:
        assert not stretching.offered(mine, their_id)
        assert stretching.for_workout(mine, their_id, 10) is None
        assert stretching.log(mine, their_id, 10) is None
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        assert _stretching_sets(theirs, their_id) == []
