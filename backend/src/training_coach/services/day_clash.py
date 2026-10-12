"""A log for a day that already has its session (ADR-0060).

Saving a planned session or a rest day for a day that already holds a planned session (done
or rested) or a rest day is a clash: nothing is saved, and the person sees what is there and
chooses to replace it, move it to another day or add the new log beside it. Extras, cardio
extras among them, never clash.

The answer names the workouts the person was shown. If the day holds anything else by the
time it is saved (another device, a log in Telegram), the question is asked again rather than
replacing what nobody saw. A replaced workout is set aside, sets and all, so /undo can put it
back (ADR-0048); a moved one keeps its sets, ladder steps and block. The caller owns the
transaction.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import (
    Exercise,
    ImportedWorkout,
    LadderStep,
    ReplacedWorkout,
    SessionProgress,
    SessionTemplate,
    SetLog,
    Workout,
    version_on,
)
from training_coach.domain.dates import day_problem
from training_coach.domain.enums import ExerciseKind, WorkoutStatus
from training_coach.domain.queue import ADVANCING, DoneOn

REPLACE, MOVE, ADD = "replace", "move", "add"
ANSWER = re.compile(r"^(?:(replace|add)|move:(\d{4}-\d{2}-\d{2}))$")
SAME_DAY = "pick a different day to move it to"
SHOWN = 3  # exercises named in a summary


@dataclass(frozen=True)
class Recorded:
    workout_id: int
    name: str  # "Legs", "Rest day"
    summary: str  # "12 sets: Squat, Lunge, Calf raise", "45 min", "rested"


@dataclass(frozen=True)
class Clash:
    """What is already saved for ``day``. ``moving``: ``day`` is where the old workout would
    have moved to, and it holds a session too, so pick another day."""

    day: date
    recorded: tuple[Recorded, ...]
    moving: bool = False

    @property
    def ids(self) -> tuple[int, ...]:
        return tuple(r.workout_id for r in self.recorded)


@dataclass(frozen=True)
class Resolution:
    action: str  # REPLACE, MOVE or ADD
    seen: tuple[int, ...]  # the workouts the person was shown
    to: date | None = None  # MOVE: the day the old workout moves to


@dataclass(frozen=True)
class Refused:
    """The answer can't be carried out (a move to the future, or too far back)."""

    reason: str


@dataclass(frozen=True)
class Resolved:
    """What answering did, for the save's event and /undo."""

    action: str
    removed: tuple[int, ...] = ()  # ReplacedWorkout ids
    moved: tuple[int, ...] = ()  # Workout ids, now on ``to``
    moved_from: date | None = None
    to: date | None = None

    def undo(self) -> dict[str, Any]:
        """What /undo needs, beside the queue: ids and dates only."""
        found: dict[str, Any] = {}
        if self.removed:
            found["removed"] = list(self.removed)
        if self.moved and self.moved_from is not None and self.to is not None:
            found["moved"] = {
                "ids": list(self.moved),
                "from": self.moved_from.isoformat(),
                "to": self.to.isoformat(),
            }
        return found


def parse(answer: str, seen: Sequence[int]) -> Resolution | None:
    """``replace``, ``add`` or ``move:YYYY-MM-DD``, or None when it is none of those."""
    found = ANSWER.match(answer)
    if found is None:
        return None
    if found[1] is not None:
        return Resolution(found[1], tuple(seen))
    try:
        return Resolution(MOVE, tuple(seen), date.fromisoformat(found[2]))
    except ValueError:
        return None


def can_clash(template_id: int | None, rest: bool) -> bool:
    """Only a planned session or a rest day can clash; an extra never does."""
    return template_id is not None or rest


def _counted() -> Any:
    return or_(
        Workout.template_id.is_not(None) & Workout.status.in_(ADVANCING),
        Workout.status == WorkoutStatus.REST,
    )


def _summary(workout: Workout, kinds: dict[int, tuple[str, ExerciseKind]]) -> str:
    if workout.status == WorkoutStatus.REST:
        return "rested"
    if not workout.sets:
        return "no sets"
    names = list(dict.fromkeys(kinds[s.exercise_id][0] for s in workout.sets))
    timed = {s.exercise_id for s in workout.sets}
    if len(timed) == 1 and kinds[next(iter(timed))][1] is ExerciseKind.DURATION_MIN:
        return f"{sum(s.value for s in workout.sets)} min"
    count = len({(s.exercise_id, s.set_no) for s in workout.sets})
    more = f" +{len(names) - SHOWN}" if len(names) > SHOWN else ""
    return f"{count} sets: {', '.join(names[:SHOWN])}{more}"


def recorded(session: Session, day: date, *, moving: bool = False) -> Clash | None:
    """What a planned session or rest day saved for ``day`` would clash with, if anything."""
    workouts = list(
        session.scalars(
            select(Workout)
            .where(Workout.local_date == day, _counted())
            .order_by(Workout.id)
            .options(selectinload(Workout.sets))
        )
    )
    if not workouts:
        return None
    names = dict(session.execute(select(SessionTemplate.id, SessionTemplate.name)).all())
    kinds = {e.id: (e.name, ExerciseKind(e.kind)) for e in session.scalars(select(Exercise))}
    found = tuple(
        Recorded(
            w.id,
            names.get(w.template_id, "A session") if w.template_id is not None else "Rest day",
            _summary(w, kinds),
        )
        for w in workouts
    )
    return Clash(day, found, moving)


def latest_done(session: Session) -> DoneOn | None:
    """The planned session done or rested last, by date and then by when it was logged."""
    found = session.execute(
        select(Workout.local_date, Workout.template_id, Workout.id)
        .where(Workout.template_id.is_not(None), Workout.status.in_(ADVANCING))
        .order_by(Workout.local_date.desc(), Workout.id.desc())
        .limit(1)
    ).first()
    if found is None or found[1] is None:
        return None
    return DoneOn(found[0], found[1], found[2])


def resolve(
    session: Session, clash: Clash, answer: Resolution, today: date
) -> Resolved | Clash | Refused:
    """Carry out the person's answer to ``clash``, or ask again: the day changed since they
    saw it, or the day to move to holds a session too. Writes nothing unless it resolves."""
    if set(answer.seen) != set(clash.ids):
        return clash
    if answer.action == ADD:
        return Resolved(ADD)
    workouts = [session.get_one(Workout, workout_id) for workout_id in clash.ids]
    if answer.action == REPLACE:
        return Resolved(REPLACE, removed=tuple(_set_aside(session, w) for w in workouts))
    to = answer.to
    if to is None or to == clash.day:
        return Refused(SAME_DAY)
    if (problem := day_problem(to, today)) is not None:
        return Refused(problem)
    if (there := recorded(session, to, moving=True)) is not None:
        return there
    for workout in workouts:
        _date(session, workout, to)
    session.flush()
    return Resolved(MOVE, moved=clash.ids, moved_from=clash.day, to=to)


def _date(session: Session, workout: Workout, day: date) -> None:
    """Put ``workout`` on ``day``, under the plan version in force then (ADR-0034). A guided
    session's progress for the old day is dropped: its sets are in the workout."""
    _drop_progress(session, workout.id)
    workout.local_date = day
    workout.plan_version_id = version_on(day)


def _drop_progress(session: Session, workout_id: int) -> None:
    for progress in session.scalars(
        select(SessionProgress).where(SessionProgress.saved_workout_id == workout_id)
    ):
        session.delete(progress)


def _set_aside(session: Session, workout: Workout) -> int:
    """Delete ``workout``, keeping what /undo needs to put it back as it was."""
    imports = session.scalars(
        select(ImportedWorkout.id).where(ImportedWorkout.workout_id == workout.id)
    )
    kept = ReplacedWorkout(
        local_date=workout.local_date,
        data={
            "template_id": workout.template_id,
            "status": workout.status,
            "block": workout.block,
            "log_token": workout.log_token,
            "activity": workout.activity,
            "plan_version_id": workout.plan_version_id,
            "created_at": workout.created_at.isoformat(),
            "sets": [
                [s.exercise_id, s.ladder_step_id, s.set_no, s.side, s.value] for s in workout.sets
            ],
            "imports": list(imports),
        },
    )
    session.add(kept)
    _drop_progress(session, workout.id)
    session.delete(workout)
    session.flush()
    return kept.id


# ---------------------------------------------------------------------- for /undo


def _exists(session: Session, where: Any) -> bool:
    """Asked of the database: a workout deleted in this transaction is still in the session."""
    return session.scalar(select(Workout.id).where(where).limit(1)) is not None


def can_put_back(session: Session, undo: dict[str, Any]) -> bool:
    """Whether what a log replaced or moved can still be put back as it was."""
    for kept_id in undo.get("removed", []):
        kept = session.get(ReplacedWorkout, kept_id)
        if kept is None:
            return False
        token = kept.data["log_token"]
        if token is not None and _exists(session, Workout.log_token == token):
            return False
        steps = {(e, s) for e, s, *_ in kept.data["sets"]}
        found = {
            (e, s)
            for e, s in session.execute(
                select(LadderStep.exercise_id, LadderStep.id).where(
                    LadderStep.id.in_({s for _, s in steps})
                )
            )
        }
        if not steps <= found:  # the plan changed since: a set's step is gone
            return False
    moved = undo.get("moved")
    if moved is not None:
        to = date.fromisoformat(moved["to"])
        for workout_id in moved["ids"]:
            workout = session.get(Workout, workout_id)
            if workout is None or workout.local_date != to:
                return False
    return True


def put_back(session: Session, undo: dict[str, Any]) -> None:
    """Undo a replace or a move: the moved workouts go back, the replaced ones return."""
    moved = undo.get("moved")
    if moved is not None:
        back = date.fromisoformat(moved["from"])
        for workout_id in moved["ids"]:
            _date(session, session.get_one(Workout, workout_id), back)
    for kept_id in undo.get("removed", []):
        kept = session.get_one(ReplacedWorkout, kept_id)
        data = kept.data
        workout = Workout(
            local_date=kept.local_date,
            template_id=data["template_id"],
            status=data["status"],
            block=data["block"],
            log_token=data["log_token"],
            activity=data["activity"],
            plan_version_id=data["plan_version_id"],
            created_at=datetime.fromisoformat(data["created_at"]).astimezone(UTC),
        )
        workout.sets.extend(
            SetLog(exercise_id=e, ladder_step_id=s, set_no=n, side=side, value=v)
            for e, s, n, side, v in data["sets"]
        )
        session.add(workout)
        session.flush()
        for row in session.scalars(
            select(ImportedWorkout).where(ImportedWorkout.id.in_(data["imports"]))
        ):
            if row.workout_id is None:
                row.workout_id = workout.id
        session.delete(kept)
    session.flush()


def sweep(session: Session, before: datetime) -> None:
    """Forget replaced workouts set aside before ``before``: past the undo window."""
    for kept in session.scalars(select(ReplacedWorkout).where(ReplacedWorkout.created_at < before)):
        session.delete(kept)
