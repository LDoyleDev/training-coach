"""ORM models for phase 1 (docs/specs/phase-1-daily-loop.md, step 1-A).

Import every model here so Alembic autogenerate sees it. All timestamps are UTC
(``UTCDateTime``); ``Workout.local_date`` is the calendar date in Europe/Berlin.
"""

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from training_coach.db.base import Base
from training_coach.db.types import UTCDateTime, utcnow
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus


def _in(column: str, values: type[ExerciseKind | WorkoutStatus | Side]) -> str:
    allowed = ", ".join(f"'{v.value}'" for v in values)
    return f"{column} IN ({allowed})"


# --------------------------------------------------------------------- the plan


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (CheckConstraint(_in("kind", ExerciseKind), name="kind_valid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16))
    muscle_groups: Mapped[list[str]] = mapped_column(JSON, default=list)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)

    ladder: Mapped[list["LadderStep"]] = relationship(
        back_populates="exercise",
        order_by="LadderStep.position",
        cascade="all, delete-orphan",
    )


class LadderStep(Base):
    """One variation of an exercise; position 0 is the easiest."""

    __tablename__ = "ladder_steps"
    __table_args__ = (
        UniqueConstraint("exercise_id", "position"),
        CheckConstraint("position >= 0", name="position_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    cue: Mapped[str | None] = mapped_column(Text)

    exercise: Mapped[Exercise] = relationship(back_populates="ladder")


class SessionTemplate(Base):
    """A session in the cycle. ``position`` is its place in the queue (ADR-0006)."""

    __tablename__ = "session_templates"
    __table_args__ = (CheckConstraint("position >= 0", name="position_non_negative"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, unique=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    focus: Mapped[str] = mapped_column(String(120))
    is_rest_optional: Mapped[bool] = mapped_column(Boolean, server_default=false())

    items: Mapped[list["TemplateItem"]] = relationship(
        back_populates="template",
        order_by="TemplateItem.position",
        cascade="all, delete-orphan",
    )


class TemplateItem(Base):
    """A planned exercise within a session. For duration exercises the range is minutes."""

    __tablename__ = "template_items"
    __table_args__ = (
        UniqueConstraint("template_id", "position"),
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint("sets >= 1", name="sets_positive"),
        CheckConstraint("rep_min >= 1", name="rep_min_positive"),
        CheckConstraint("rep_max >= rep_min", name="rep_range_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("session_templates.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="RESTRICT"))
    sets: Mapped[int] = mapped_column(Integer)
    rep_min: Mapped[int] = mapped_column(Integer)
    rep_max: Mapped[int] = mapped_column(Integer)
    per_side: Mapped[bool] = mapped_column(Boolean, server_default=false())

    template: Mapped[SessionTemplate] = relationship(back_populates="items")
    exercise: Mapped[Exercise] = relationship()


# ----------------------------------------------------------------------- state


class ExerciseState(Base):
    """The ladder step currently being trained for each exercise."""

    __tablename__ = "exercise_state"

    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True
    )
    ladder_step_id: Mapped[int] = mapped_column(ForeignKey("ladder_steps.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class PlanState(Base):
    """Single row: the next session in the queue (ADR-0006)."""

    __tablename__ = "plan_state"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    next_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_templates.id", ondelete="RESTRICT")
    )
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class UserSettings(Base):
    """Single row of user settings. Times are local (Europe/Berlin) wall-clock times."""

    __tablename__ = "settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    morning_time: Mapped[time] = mapped_column(Time, default=time(7, 30))
    nudge_time: Mapped[time] = mapped_column(Time, default=time(20, 0))
    nudges_enabled: Mapped[bool] = mapped_column(Boolean, server_default=true())
    paused: Mapped[bool] = mapped_column(Boolean, server_default=false())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


# ------------------------------------------------------------------------ logs


class Workout(Base):
    """One training session. Several per day are allowed (ADR-0014).

    ``template_id`` is the planned session this completes; ``None`` means an extra,
    unplanned workout, which never moves the queue.
    """

    __tablename__ = "workouts"
    __table_args__ = (CheckConstraint(_in("status", WorkoutStatus), name="status_valid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, index=True)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_templates.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    sets: Mapped[list["SetLog"]] = relationship(
        back_populates="workout",
        order_by="(SetLog.exercise_id, SetLog.set_no)",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SetLog(Base):
    """One logged set. ``value`` is reps, seconds or minutes depending on the exercise kind."""

    __tablename__ = "set_logs"
    __table_args__ = (
        UniqueConstraint("workout_id", "exercise_id", "set_no", "side"),
        CheckConstraint("set_no >= 1", name="set_no_positive"),
        CheckConstraint("value >= 0 AND value <= 3600", name="value_in_range"),
        CheckConstraint(f"side IS NULL OR {_in('side', Side)}", name="side_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), index=True
    )
    ladder_step_id: Mapped[int] = mapped_column(ForeignKey("ladder_steps.id", ondelete="RESTRICT"))
    set_no: Mapped[int] = mapped_column(Integer)
    value: Mapped[int] = mapped_column(Integer)
    side: Mapped[str | None] = mapped_column(String(8))

    workout: Mapped[Workout] = relationship(back_populates="sets")


class Event(Base):
    """Audit log. Payloads must never contain secrets, transcripts or measurements."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


__all__ = [
    "Base",
    "Event",
    "Exercise",
    "ExerciseState",
    "LadderStep",
    "PlanState",
    "SessionTemplate",
    "SetLog",
    "TemplateItem",
    "UserSettings",
    "Workout",
]
