"""ORM models for phase 1 (docs/specs/phase-1-daily-loop.md, step 1-A).

Import every model here so Alembic autogenerate sees it. All timestamps are UTC
(``UTCDateTime``); ``Workout.local_date`` is the calendar date in Europe/Berlin.
"""

from datetime import date, datetime, time
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    Time,
    UniqueConstraint,
    event,
    false,
    select,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from training_coach.db.base import Base
from training_coach.db.types import UTCDateTime, utcnow
from training_coach.domain.blocks import BlockKind
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus
from training_coach.domain.fitness_tests import TimeOfDay
from training_coach.domain.habits import Habit
from training_coach.domain.measurements import Kind as MeasurementKind


def _in(column: str, values: type[StrEnum]) -> str:
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
    # Out of the plan but kept with its history; still loggable (#107, ADR-0034).
    retired: Mapped[bool] = mapped_column(Boolean, server_default=false())
    # One side at a time when no session says (a retired exercise's logs).
    per_side: Mapped[bool] = mapped_column(Boolean, server_default=false())

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
        # Target for composite FKs that guarantee a step belongs to the referenced exercise.
        UniqueConstraint("exercise_id", "id"),
        CheckConstraint("position >= 0", name="position_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    cue: Mapped[str | None] = mapped_column(Text)

    exercise: Mapped[Exercise] = relationship(back_populates="ladder")


class PlanVersion(Base):
    """A version of the plan, in force from ``since`` until the next one (#107, ADR-0034).
    Set by the seed from plan.toml; a workout records the version in force on its date."""

    __tablename__ = "plan_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    since: Mapped[date] = mapped_column(Date, unique=True)
    name: Mapped[str] = mapped_column(String(120))


def version_on(day: Any) -> Any:
    """SQL for the id of the plan version in force on ``day`` (a date or a date column)."""
    return (
        select(PlanVersion.id)
        .where(PlanVersion.since <= day)
        .order_by(PlanVersion.since.desc())
        .limit(1)
        .scalar_subquery()
    )


class SessionTemplate(Base):
    """A session in the cycle. ``position`` is its place in the queue (ADR-0006)."""

    __tablename__ = "session_templates"
    __table_args__ = (
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint("kind IN ('strength', 'conditioning', 'recovery')", name="kind_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, unique=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    focus: Mapped[str] = mapped_column(String(120))
    is_rest_optional: Mapped[bool] = mapped_column(Boolean, server_default=false())
    # strength | conditioning | recovery (plan.toml): strength sessions get the warm-up prompt
    # and, in a strength block, the strength prescription (ADR-0028).
    kind: Mapped[str] = mapped_column(String(16), server_default="strength")

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
    # Items sharing a number are done alternately, set by set (#97); empty means alone.
    pair: Mapped[int | None] = mapped_column(Integer)

    template: Mapped[SessionTemplate] = relationship(back_populates="items")
    exercise: Mapped[Exercise] = relationship()


# ----------------------------------------------------------------------- people


class User(Base):
    """A person using the app (ADR-0026). Per-person rows below carry ``user_id``; the shared
    plan above does not. Phase 1 has one user, linked to the allowed Telegram account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Owned:
    """Marks a per-person table. A session bound to a user (``db.session``) sees and writes
    only that user's rows of every ``Owned`` model."""

    user_id: Mapped[int] | Mapped[int | None]


def _owner() -> Mapped[int]:
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


# ----------------------------------------------------------------------- state


class ExerciseState(Owned, Base):
    """The ladder step each person is currently training for each exercise."""

    __tablename__ = "exercise_state"
    __table_args__ = (
        ForeignKeyConstraint(
            ["exercise_id", "ladder_step_id"],
            ["ladder_steps.exercise_id", "ladder_steps.id"],
            ondelete="RESTRICT",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True
    )
    ladder_step_id: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class PlanState(Owned, Base):
    """One row per person: the next session in the queue (ADR-0006), plus any swapped ones
    (ADR-0022)."""

    __tablename__ = "plan_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    next_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_templates.id", ondelete="RESTRICT")
    )
    # Template ids served after the pointer before the cycle resumes (a swap, ADR-0022).
    queued: Mapped[list[int]] = mapped_column(JSON, default=list, server_default="[]")
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class UserSettings(Owned, Base):
    """One row of settings per person. Times are local (Europe/Berlin) wall-clock times."""

    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint(
            "protein_g IS NULL OR protein_g BETWEEN 40 AND 400", name="protein_g_range"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    morning_time: Mapped[time] = mapped_column(Time, default=time(7, 30))
    nudge_time: Mapped[time] = mapped_column(Time, default=time(20, 0))
    # The weekly review goes out on Sundays at this time (D6, #73).
    review_time: Mapped[time] = mapped_column(
        Time, default=time(19, 0), server_default="19:00:00.000000"
    )
    # The day training blocks were turned on (ADR-0028); empty means blocks are off.
    blocks_started_on: Mapped[date | None] = mapped_column(Date)
    nudges_enabled: Mapped[bool] = mapped_column(Boolean, server_default=true())
    # Habit check-off buttons in the evening message (D5, #91).
    habits_enabled: Mapped[bool] = mapped_column(Boolean, server_default=true())
    # Daily protein target in grams for the protein habit; empty shows the per-kg guide.
    protein_g: Mapped[int | None] = mapped_column(Integer)
    paused: Mapped[bool] = mapped_column(Boolean, server_default=false())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


# ------------------------------------------------------------------------ logs


class Workout(Owned, Base):
    """One training session. Several per day are allowed (ADR-0014).

    ``template_id`` is the planned session this completes; ``None`` means an extra,
    unplanned workout, which never moves the queue.
    """

    __tablename__ = "workouts"
    __table_args__ = (
        CheckConstraint(_in("status", WorkoutStatus), name="status_valid"),
        CheckConstraint(_in("block", BlockKind), name="block_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    local_date: Mapped[date] = mapped_column(Date, index=True)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_templates.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(16))
    # The training block it was logged in (ADR-0028); empty when blocks were off.
    block: Mapped[str | None] = mapped_column(String(16))
    # Set when a confirmed text/voice log is saved: one token per draft, so a repeated Save
    # can never create a second workout or advance the queue twice (step 1-E).
    log_token: Mapped[str | None] = mapped_column(String(32), unique=True)
    # The plan version in force on local_date (ADR-0034), set on insert; empty only when
    # the plan has no versions yet (the seed fills those in once it has).
    plan_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_versions.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    sets: Mapped[list["SetLog"]] = relationship(
        back_populates="workout",
        order_by="(SetLog.exercise_id, SetLog.set_no)",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


@event.listens_for(Workout, "before_insert")
def _plan_version(_mapper: object, _connection: object, workout: Workout) -> None:
    """Every way a workout is saved (today, a past day, the guided session, a rest) gets the
    plan version in force on its date, computed in the INSERT itself."""
    if workout.plan_version_id is None:
        workout.plan_version_id = version_on(workout.local_date)


class SetLog(Owned, Base):
    """One logged set. ``value`` is reps, seconds or minutes depending on the exercise kind.

    Sets are only saved for ``done`` workouts; ``rest``/``skipped`` workouts have none
    (enforced in the logging service, step 1-E).
    """

    __tablename__ = "set_logs"
    __table_args__ = (
        UniqueConstraint("workout_id", "exercise_id", "set_no", "side"),
        CheckConstraint("set_no >= 1", name="set_no_positive"),
        CheckConstraint("value >= 0 AND value <= 3600", name="value_in_range"),
        CheckConstraint(_in("side", Side), name="side_valid"),
        ForeignKeyConstraint(
            ["exercise_id", "ladder_step_id"],
            ["ladder_steps.exercise_id", "ladder_steps.id"],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()  # always the workout's owner (checked on flush)
    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), index=True
    )
    ladder_step_id: Mapped[int] = mapped_column(Integer)
    set_no: Mapped[int] = mapped_column(Integer)
    value: Mapped[int] = mapped_column(Integer)
    side: Mapped[str] = mapped_column(String(8), default=Side.BOTH, server_default=Side.BOTH.value)

    workout: Mapped[Workout] = relationship(back_populates="sets")


class HabitCheck(Owned, Base):
    """A habit ticked for a day (D5, #90). The row's presence means done; unticking deletes it."""

    __tablename__ = "habit_checks"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", "habit"),
        CheckConstraint(_in("habit", Habit), name="habit_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    local_date: Mapped[date] = mapped_column(Date)
    habit: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class FitnessTestDay(Owned, Base):
    """One day of baseline tests or a retest (2-A, #94, ADR-0037): the conditions and the
    results, ``[{"test": slug, "side": "both", "value": 12}, ...]``, checked by
    ``domain.fitness_tests`` before saving. ``token`` makes a repeated Save harmless."""

    __tablename__ = "test_days"
    __table_args__ = (
        CheckConstraint("day IN (1, 2)", name="day_valid"),
        CheckConstraint(_in("time_of_day", TimeOfDay), name="time_of_day_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    local_date: Mapped[date] = mapped_column(Date, index=True)
    day: Mapped[int] = mapped_column(Integer)
    time_of_day: Mapped[str] = mapped_column(String(16))
    fed: Mapped[bool] = mapped_column(Boolean)
    slept_well: Mapped[bool] = mapped_column(Boolean)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    token: Mapped[str] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Measurement(Owned, Base):
    """A body measurement for a day (2-B, #142): one per kind per day, in tenths
    (``domain.measurements``). Personal: never logged, never shared."""

    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", "kind"),
        CheckConstraint(_in("kind", MeasurementKind), name="kind_valid"),
        CheckConstraint("tenths > 0", name="tenths_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    local_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(16))
    tenths: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class SessionProgress(Owned, Base):
    """A guided session in progress (D1, #117): where the person is and the sets confirmed so
    far, kept on the server so it resumes on any device. ``token`` makes saving it idempotent
    (it becomes the workout's ``log_token``)."""

    __tablename__ = "session_progress"
    __table_args__ = (UniqueConstraint("user_id", "local_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    local_date: Mapped[date] = mapped_column(Date)
    template_id: Mapped[int] = mapped_column(ForeignKey("session_templates.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    first: Mapped[list[int]] = mapped_column(JSON, default=list)  # pairs started second-first
    # [{"item": 0, "set_no": 1, "left": 8, "right": null}], in the order confirmed
    sets: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    token: Mapped[str] = mapped_column(String(32))
    # Bumped on every change: a browser must name the revision it saw, so a stale tab
    # on another device can't overwrite newer sets.
    revision: Mapped[int] = mapped_column(Integer, default=1)
    saved_workout_id: Mapped[int | None] = mapped_column(
        ForeignKey("workouts.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


# ----------------------------------------------------------------- web sign-in


class LoginLink(Owned, Base):
    """A one-time sign-in link sent by the bot (ADR-0036). Only the token's SHA-256 is kept."""

    __tablename__ = "login_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class WebSession(Owned, Base):
    """A signed-in browser (ADR-0036). Only the cookie token's SHA-256 is kept."""

    __tablename__ = "web_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(120))  # the browser, so a device can be recognised
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Passkey(Owned, Base):
    """A fingerprint or face key registered for sign-in (WebAuthn, ADR-0036). The private key
    never leaves the device; this is its public half."""

    __tablename__ = "passkeys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    credential_id: Mapped[str] = mapped_column(String(1400), unique=True)  # base64url
    public_key: Mapped[bytes] = mapped_column(LargeBinary)  # COSE
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(120))  # the browser it was made in
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class PasskeyChallenge(Base):
    """A one-time WebAuthn challenge, 5 minutes (ADR-0036). Shared, not per person: a sign-in
    challenge belongs to nobody yet. A registration challenge names who asked for it. The
    browser holds a random handle in a cookie; only its SHA-256 is kept here."""

    __tablename__ = "passkey_challenges"
    __table_args__ = (CheckConstraint("purpose IN ('register', 'sign_in')", name="purpose_valid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle_hash: Mapped[str] = mapped_column(String(64), unique=True)
    challenge: Mapped[bytes] = mapped_column(LargeBinary)
    purpose: Mapped[str] = mapped_column(String(16))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # SHA-256 of the caller's address, so open sign-ins can be capped per client.
    client_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Event(Owned, Base):
    """Audit log. Payloads must never contain secrets, transcripts or measurements.
    ``user_id`` is empty for system events such as ``seed.applied``."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


__all__ = [
    "Base",
    "Event",
    "Exercise",
    "ExerciseState",
    "HabitCheck",
    "LadderStep",
    "LoginLink",
    "Owned",
    "Passkey",
    "PasskeyChallenge",
    "PlanState",
    "SessionProgress",
    "SessionTemplate",
    "SetLog",
    "TemplateItem",
    "User",
    "UserSettings",
    "WebSession",
    "Workout",
]
