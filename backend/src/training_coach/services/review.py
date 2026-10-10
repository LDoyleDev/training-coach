"""The weekly review (phase 2 step 2-C, #73; D6 in docs/specs/phase-2-decisions.md).

One week is Monday to Sunday in local time. The review counts what was logged: sessions done
against the plan's cycle, hard sets per muscle group against Galpin's 10-20, cardio minutes
against the zone 2 target (#124), the personal bests set that week, what is ready to move up,
and the habits ticked (D5). It only reads; the caller owns the session.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, LadderStep, SessionTemplate, SetLog, Workout
from training_coach.domain.blocks import BlockKind
from training_coach.domain.enums import ExerciseKind, WorkoutStatus
from training_coach.domain.habits import HabitWeek
from training_coach.domain.progression import Progress
from training_coach.domain.records import NewBests
from training_coach.domain.volume import weekly_sets
from training_coach.services import blocks, habits, progress
from training_coach.services.seed import bundled_plan

ZONE2 = "zone2"  # walks, rides and easy runs log as this exercise through its aliases
MODERATE = "moderate-cardio"


@dataclass(frozen=True)
class Best:
    exercise: str
    step: str  # records are per ladder step (ADR-0025)
    kind: ExerciseKind
    bests: NewBests
    strength: bool = False  # set in a strength block (ADR-0028), kept apart from the rest


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
    strength_block: bool = False  # moving up waits for the hypertrophy block (ADR-0028)
    habits: list[HabitWeek] = field(default_factory=list)  # empty in a week with no check-off
    # Cardio minutes from done workouts, whatever logged them (#124).
    zone2_minutes: int = 0
    moderate_minutes: int = 0
    zone2_target: tuple[int, int] | None = None  # from plan.toml


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


def _minutes(session: Session, start: date, end: date) -> dict[str, int]:
    """Minutes logged per cardio exercise in done workouts of the week. Zone 2 is the zone2
    exercise's duration for now; it can become minutes in the zone 2 heart-rate band once that
    data arrives, without changing the review (#124)."""
    rows = session.execute(
        select(Exercise.slug, func.sum(SetLog.value))
        .join(SetLog, SetLog.exercise_id == Exercise.id)
        .join(Workout, Workout.id == SetLog.workout_id)
        .where(
            Workout.local_date >= start,
            Workout.local_date <= end,
            Workout.status == WorkoutStatus.DONE,
            Exercise.slug.in_((ZONE2, MODERATE)),
        )
        .group_by(Exercise.slug)
    )
    return {slug: int(total) for slug, total in rows}


def _higher(a: int | None, b: int | None) -> int | None:
    return max((v for v in (a, b) if v is not None), default=None)


def _bests(session: Session, workouts: list[Workout]) -> list[Best]:
    """The best record per exercise, ladder step and block kind set this week, in the order
    first achieved. Records at different steps or blocks are never merged: they aren't
    comparable."""
    found: dict[tuple[int, int, str | None], Best] = {}
    for workout in sorted(workouts, key=lambda w: (w.local_date, w.created_at, w.id)):
        steps = {(s.exercise_id, s.ladder_step_id) for s in workout.sets}
        for exercise_id, step_id in sorted(steps):
            exercise = session.get(Exercise, exercise_id)
            step = session.get(LadderStep, step_id)
            if exercise is None or step is None:
                continue
            per_side = progress.per_side_for(session, exercise_id, workout.template_id)
            history = progress.workout_history(workout, exercise)
            bests = progress.bests_in(session, workout.id, exercise_id, step_id, per_side, history)
            if not bests:
                continue
            key = (exercise_id, step_id, history)
            earlier = found.get(key)
            if earlier is not None:  # a second record that week: keep the higher of each
                bests = NewBests(
                    _higher(bests.best_set, earlier.bests.best_set),
                    _higher(bests.total, earlier.bests.total),
                )
            found[key] = Best(
                exercise.name,
                step.name,
                ExerciseKind(exercise.kind),
                bests,
                strength=history is BlockKind.STRENGTH,
            )
    return list(found.values())


def weekly(session: Session, on: date, tz: ZoneInfo | None = None) -> Review:
    """The review of the week containing ``on``; with ``tz``, aware of a strength block."""
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
    ticked = habits.week(session, start, on)
    minutes = _minutes(session, start, end)
    targets = bundled_plan().targets
    return Review(
        start=start,
        planned=session.scalar(select(func.count()).select_from(SessionTemplate)) or 0,
        done=planned_done,
        rested=sum(1 for w in workouts if w.status == WorkoutStatus.REST),
        extras=len(done) - planned_done,
        volume=_volume(session, start, end),
        bests=_bests(session, done),
        ready=[s.exercise for s in progress.overview(session) if s.status is Progress.READY],
        strength_block=(
            tz is not None
            and (block := blocks.current(session, on, tz)) is not None
            and block.kind is BlockKind.STRENGTH
        ),
        habits=ticked if any(h.done for h in ticked) else [],
        zone2_minutes=minutes.get(ZONE2, 0),
        moderate_minutes=minutes.get(MODERATE, 0),
        zone2_target=targets.zone2_minutes if targets is not None else None,
    )
