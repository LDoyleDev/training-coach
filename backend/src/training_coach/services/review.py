"""The weekly review (phase 2 step 2-C, #73; D6 in docs/specs/phase-2-decisions.md).

One week is Monday to Sunday in local time. The review counts what was logged: sessions done
against the plan's cycle, hard sets per muscle group against Galpin's 10-20, the personal
bests set that week, and what is ready to move up. It only reads; the caller owns the session.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, SessionTemplate, SetLog, Workout
from training_coach.domain.enums import ExerciseKind, WorkoutStatus
from training_coach.domain.progression import Progress
from training_coach.domain.records import NewBests
from training_coach.domain.volume import weekly_sets
from training_coach.services import progress


@dataclass(frozen=True)
class Best:
    exercise: str
    kind: ExerciseKind
    bests: NewBests


@dataclass(frozen=True)
class Review:
    start: date  # Monday
    planned: int  # sessions in the plan's cycle
    done: int  # planned sessions completed
    rested: int
    extras: int  # unplanned sessions
    volume: list[tuple[str, int]]  # hard sets logged per muscle group, largest first
    bests: list[Best]
    ready: list[str]  # exercises ready to move up


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _volume(session: Session, start: date, end: date) -> list[tuple[str, int]]:
    """Each logged set counts once per muscle group of its exercise; a set done on both sides
    (left and right) is still one set."""
    one_per_set = (
        select(SetLog.exercise_id, SetLog.workout_id, SetLog.set_no)
        .join(Workout)
        .where(
            Workout.local_date >= start,
            Workout.local_date <= end,
            Workout.status == WorkoutStatus.DONE,  # as the other sections count
        )
        .distinct()
        .subquery()
    )
    rows = session.execute(
        select(one_per_set.c.exercise_id, func.count()).group_by(one_per_set.c.exercise_id)
    )
    groups = {e.id: e.muscle_groups for e in session.scalars(select(Exercise))}
    return weekly_sets((groups.get(exercise_id, []), int(sets)) for exercise_id, sets in rows)


def _higher(a: int | None, b: int | None) -> int | None:
    return max((v for v in (a, b) if v is not None), default=None)


def _bests(session: Session, workouts: list[Workout]) -> list[Best]:
    """The best record per exercise set this week, in the order first achieved."""
    found: dict[int, Best] = {}
    for workout in sorted(workouts, key=lambda w: (w.local_date, w.created_at, w.id)):
        steps = {(s.exercise_id, s.ladder_step_id) for s in workout.sets}
        for exercise_id, step_id in sorted(steps):
            per_side = progress.per_side_for(session, exercise_id, workout.template_id)
            bests = progress.bests_in(session, workout.id, exercise_id, step_id, per_side)
            exercise = session.get(Exercise, exercise_id)
            if not bests or exercise is None:
                continue
            earlier = found.get(exercise_id)
            if earlier is not None:  # a second record that week: keep the higher of each
                bests = NewBests(
                    _higher(bests.best_set, earlier.bests.best_set),
                    _higher(bests.total, earlier.bests.total),
                )
            found[exercise_id] = Best(exercise.name, ExerciseKind(exercise.kind), bests)
    return list(found.values())


def weekly(session: Session, on: date) -> Review:
    """The review of the week containing ``on``."""
    start = week_start(on)
    end = start + timedelta(days=6)
    workouts = list(
        session.scalars(
            select(Workout).where(Workout.local_date >= start, Workout.local_date <= end)
        )
    )
    done = [w for w in workouts if w.status == WorkoutStatus.DONE]
    # Each planned session counts once; doing one again that week is an extra.
    planned_done = len({w.template_id for w in done if w.template_id is not None})
    return Review(
        start=start,
        planned=session.scalar(select(func.count()).select_from(SessionTemplate)) or 0,
        done=planned_done,
        rested=sum(1 for w in workouts if w.status == WorkoutStatus.REST),
        extras=len(done) - planned_done,
        volume=_volume(session, start, end),
        bests=_bests(session, done),
        ready=[s.exercise for s in progress.overview(session) if s.status is Progress.READY],
    )
