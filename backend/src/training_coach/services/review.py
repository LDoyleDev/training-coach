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
from training_coach.domain import health
from training_coach.domain.blocks import BlockKind
from training_coach.domain.enums import ExerciseKind, WorkoutStatus
from training_coach.domain.habits import HabitWeek
from training_coach.domain.load import top_weight
from training_coach.domain.muscles import Muscle
from training_coach.domain.records import NewBests
from training_coach.domain.volume import weekly_sets
from training_coach.domain.zones import Split
from training_coach.services import blocks, cardio_totals, habits, progress
from training_coach.services.seed import bundled_plan

ZONE2 = health.ZONE2  # walks, rides and easy runs log as this exercise through its aliases
MODERATE = health.MODERATE
LAST_DAYS = 7  # running totals: today and the six days before (ADR-0077)


@dataclass(frozen=True)
class Best:
    exercise: str
    step: str  # records are per ladder step (ADR-0025)
    kind: ExerciseKind
    bests: NewBests
    strength: bool = False  # set in a strength block (ADR-0028), kept apart from the rest
    # The weight of the session that set the best set, or the total without one (ADR-0072):
    # the review counts every weight, so it says which one.
    load_kg: float | None = None


@dataclass(frozen=True)
class Review:
    start: date  # Monday
    planned: int  # sessions in the plan's cycle
    done: int  # planned sessions completed
    rested: int
    extras: int  # unplanned sessions
    volume: list[tuple[Muscle, float]]  # fractional hard sets logged per muscle, largest first
    bests: list[Best]
    ready: list[progress.Ready]  # exercises ready to move up
    # Reached the top this week and still there, said once per level (ADR-0078); needs ``tz``.
    top: list[progress.Top] = field(default_factory=list)
    strength_block: bool = False  # moving up waits for the hypertrophy block (ADR-0028)
    habits: list[HabitWeek] = field(default_factory=list)  # empty in a week with no check-off
    # Cardio minutes from done workouts, whatever logged them (#124): zone 2 by heart rate, or
    # logged as zone 2 without it; moderate as logged (ADR-0079).
    zone2_minutes: int = 0
    moderate_minutes: int = 0
    zone2_target: tuple[int, int] | None = None  # from the cycle and extra cardio (ADR-0079)


@dataclass(frozen=True)
class Span:
    """What was done in done workouts from one local day to another, both included."""

    done: int  # planned sessions completed, each once
    extras: int  # unplanned sessions, and a planned one done again
    zone2_minutes: int  # in zone 2 (``Split.zone2``)
    moderate_minutes: int  # logged as moderate
    bests: list[Best]
    cardio: Split = field(default_factory=Split)  # all cardio minutes by zone (ADR-0079)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def last_days(on: date, n: int = LAST_DAYS) -> date:
    """The first of the ``n`` local days ending ``on``: today and the ``n - 1`` before. Running
    totals count these, so a Monday still shows the weekend (ADR-0077); the weekly review stays
    a calendar week (``week_start``)."""
    return on - timedelta(days=n - 1)


def _volume(session: Session, start: date, end: date) -> list[tuple[Muscle, float]]:
    """Each logged set counts its exercise's weight for each muscle (ADR-0064); a set done on
    both sides (left and right) is still one set."""
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
    weights = {e.slug: e.muscles for e in bundled_plan().exercises}
    muscles = {e.id: weights.get(e.slug, {}) for e in session.scalars(select(Exercise))}
    return weekly_sets((muscles.get(exercise_id, {}), int(sets)) for exercise_id, sets in rows)


def cardio_minutes(session: Session, start: date, end: date) -> dict[str, int]:
    """Minutes of zone 2 and moderate cardio done from ``start`` to ``end`` (by slug), a
    counted band workout for all its minutes (ADR-0079)."""
    return cardio_totals.by_kind(cardio_totals.logged(session, start, end))


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
            kg = top_weight(
                [
                    (s.set_no, s.load_kg)
                    for s in workout.sets
                    if (s.exercise_id, s.ladder_step_id) == (exercise_id, step_id)
                    and s.load_kg is not None
                ]
            )
            if earlier is not None:  # a second record that week: keep the higher of each
                kept = earlier.bests.best_set
                if kept is not None and (bests.best_set is None or bests.best_set < kept):
                    kg = earlier.load_kg  # the best set is still the earlier session's
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
                load_kg=kg,
            )
    return list(found.values())


def _workouts(session: Session, start: date, end: date) -> list[Workout]:
    return list(
        session.scalars(
            select(Workout).where(Workout.local_date >= start, Workout.local_date <= end)
        )
    )


def _span(session: Session, workouts: list[Workout], start: date, end: date) -> Span:
    done = [w for w in workouts if w.status == WorkoutStatus.DONE]
    # Each planned session counts once; doing one again in the span is an extra.
    planned_done = len({w.template_id for w in done if w.template_id is not None})
    cardio = cardio_totals.logged(session, start, end)
    zones = cardio_totals.split(session, cardio, end)
    return Span(
        done=planned_done,
        extras=len(done) - planned_done,
        zone2_minutes=zones.zone2,
        moderate_minutes=cardio_totals.by_kind(cardio).get(MODERATE, 0),
        bests=_bests(session, done),
        cardio=zones,
    )


def span(session: Session, start: date, end: date) -> Span:
    """Sessions, cardio minutes and personal bests from ``start`` to ``end``."""
    return _span(session, _workouts(session, start, end), start, end)


def planned_sessions(session: Session) -> int:
    """Sessions in the plan's cycle."""
    return session.scalar(select(func.count()).select_from(SessionTemplate)) or 0


def weekly(session: Session, on: date, tz: ZoneInfo | None = None) -> Review:
    """The review of the week containing ``on``; with ``tz``, aware of a strength block."""
    start = week_start(on)
    end = start + timedelta(days=6)
    workouts = _workouts(session, start, end)
    found = _span(session, workouts, start, end)
    ticked = habits.week(session, start, on)
    targets = cardio_totals.targets(session)
    standings = progress.overview(session)
    return Review(
        start=start,
        planned=planned_sessions(session),
        done=found.done,
        rested=sum(1 for w in workouts if w.status == WorkoutStatus.REST),
        extras=found.extras,
        volume=_volume(session, start, end),
        bests=found.bests,
        ready=progress.ready(standings),
        top=progress.tops(session, standings, start, tz) if tz is not None else [],
        strength_block=(
            tz is not None
            and (block := blocks.current(session, on, tz)) is not None
            and block.kind is BlockKind.STRENGTH
        ),
        habits=ticked if any(h.done for h in ticked) else [],
        zone2_minutes=found.zone2_minutes,
        moderate_minutes=found.moderate_minutes,
        zone2_target=targets.zone2,
    )
