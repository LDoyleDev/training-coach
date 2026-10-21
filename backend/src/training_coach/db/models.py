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
from training_coach.domain.band_watch import Feed
from training_coach.domain.blocks import BlockKind
from training_coach.domain.daily_check import Energy, Sleep, Soreness
from training_coach.domain.enums import CardioActivity, ExerciseKind, Side, Sound, WorkoutStatus
from training_coach.domain.fitness_tests import TimeOfDay
from training_coach.domain.habits import Habit
from training_coach.domain.measurements import Kind as MeasurementKind
from training_coach.domain.photos import Pose
from training_coach.domain.targets import Pace


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
        CheckConstraint(
            "birth_year IS NULL OR birth_year BETWEEN 1920 AND 2020", name="birth_year_range"
        ),
        CheckConstraint("max_hr IS NULL OR max_hr BETWEEN 120 AND 230", name="max_hr_range"),
        CheckConstraint(_in("pace", Pace), name="pace_valid"),
        CheckConstraint(_in("sound", Sound), name="sound_valid"),
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
    # Heart-rate zones (ADR-0055): the age for the max estimate, and a max of their own.
    birth_year: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    # How big a step the targets take (ADR-0057).
    pace: Mapped[str] = mapped_column(String(16), server_default=Pace.STANDARD.value)
    # What the guided timers play at each change (ADR-0062).
    sound: Mapped[str] = mapped_column(String(16), server_default=Sound.CHIME.value)
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
        CheckConstraint(_in("activity", CardioActivity), name="activity_valid"),
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
    # What a cardio log was (walk, bike...), from the web's Log activity; empty otherwise.
    activity: Mapped[str | None] = mapped_column(String(16))
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


class ReplacedWorkout(Owned, Base):
    """A workout a log replaced (ADR-0060), kept so /undo can put it back: the row's values,
    its sets and what pointed at it, as written by ``services.day_clash``. It comes back as a
    new row, since SQLite may have given its id to the workout that replaced it. Gone after the
    undo window (24 hours) or once it is put back."""

    __tablename__ = "replaced_workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    local_date: Mapped[date] = mapped_column(Date)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


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
    # When a guided session showed the set and when it was confirmed (ADR-0061); both sides of
    # a one-sided set share them. Empty for every other way of logging.
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    done_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

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


class ProgressPhoto(Owned, Base):
    """A progress photo (2-B, #143, ADR-0039): one per pose per day, a JPEG with its metadata
    removed. Kept in the database so backups include it. Personal: never logged or shared."""

    __tablename__ = "progress_photos"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", "pose"),
        CheckConstraint(_in("pose", Pose), name="pose_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    local_date: Mapped[date] = mapped_column(Date)
    pose: Mapped[str] = mapped_column(String(8))
    # Loaded only when the picture itself is asked for, never by a listing.
    jpeg: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    size: Mapped[int] = mapped_column(Integer)
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
    # "start": the first sign-in, refused once a passkey exists; "recover": signs in without a
    # passkey and signs out every other browser (ADR-0040).
    purpose: Mapped[str] = mapped_column(String(8), default="start", server_default="start")


class WebSession(Owned, Base):
    """A signed-in browser (ADR-0036). Only the cookie token's SHA-256 is kept."""

    __tablename__ = "web_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(120))  # the browser, so a device can be recognised
    # The passkey that started it, if one did: removing the key ends its sessions too.
    passkey_id: Mapped[int | None] = mapped_column(
        ForeignKey("passkeys.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Last time the person confirmed it's them with their fingerprint, without signing in again
    # (ADR-0049): it makes the session fresh, like a new sign-in.
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # The passkey that confirmed it: a connection approved on the strength of that
    # confirmation ends when the key is removed (ADR-0047 C).
    confirmed_passkey_id: Mapped[int | None] = mapped_column(
        ForeignKey("passkeys.id", ondelete="SET NULL")
    )


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


class ReadinessAnswers(Owned, Base):
    """A person's answers to the readiness questions (ADR-0046): the latest only, one row each.
    Health data: never logged, never shared."""

    __tablename__ = "readiness_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    version: Mapped[int] = mapped_column(Integer)  # which questions (domain.readiness.VERSION)
    answers: Mapped[dict[str, bool]] = mapped_column(JSON)
    answered_at: Mapped[datetime] = mapped_column(UTCDateTime)


class DailyCheck(Owned, Base):
    """A person's daily check for a day (ADR-0053): sleep, soreness and energy, one row per
    local day, replaced when answered again. Health data: never logged, never shared; rows
    older than a year are deleted as new ones come in."""

    __tablename__ = "daily_checks"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date"),
        CheckConstraint(_in("sleep", Sleep), name="sleep_valid"),
        CheckConstraint(_in("soreness", Soreness), name="soreness_valid"),
        CheckConstraint(_in("energy", Energy), name="energy_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    local_date: Mapped[date] = mapped_column(Date)  # the day in settings.tz
    sleep: Mapped[str] = mapped_column(String(8))
    soreness: Mapped[str] = mapped_column(String(8))
    energy: Mapped[str] = mapped_column(String(8))
    answered_at: Mapped[datetime] = mapped_column(UTCDateTime)


# ------------------------------------------------------------- band data (ADR-0055)


class IngestKey(Owned, Base):
    """The secret a person's phone sends with band data (ADR-0055): one each, shown once,
    only its SHA-256 kept."""

    __tablename__ = "ingest_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # last sync stored
    # The last sync that took a record, and when a gap in band data was told (ADR-0055).
    last_taken_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    alerted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class BandFeed(Owned, Base):
    """One daily kind of band data (steps, sleep, heart rate): the last sync that took a record
    of it, and when a gap in it was told (ADR-0055). Gone with the secret that fed it."""

    __tablename__ = "band_feeds"
    __table_args__ = (
        UniqueConstraint("user_id", "feed"),
        CheckConstraint(_in("feed", Feed), name="feed_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    feed: Mapped[str] = mapped_column(String(16))
    last_taken_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    alerted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class HealthDay(Owned, Base):
    """A day's steps and resting heart rate from the band (ADR-0055). Health data: never
    logged, never shared."""

    __tablename__ = "health_days"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date"),
        CheckConstraint("steps IS NULL OR steps BETWEEN 0 AND 200000", name="steps_range"),
        CheckConstraint(
            "resting_hr IS NULL OR resting_hr BETWEEN 25 AND 150", name="resting_hr_range"
        ),
        CheckConstraint(
            "resting_source IS NULL OR resting_source IN ('record', 'derived')",
            name="resting_source_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    local_date: Mapped[date] = mapped_column(Date)  # the day in settings.tz
    steps: Mapped[int | None] = mapped_column(Integer)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    # "record": Health Connect had a resting heart rate; "derived": the night's lowest minute.
    resting_source: Mapped[str | None] = mapped_column(String(8))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class HeartRateSample(Owned, Base):
    """Heart rate in one minute (ADR-0055), kept 8 days: long enough for a workout whose heart
    rate arrived in an earlier sync, and for resting heart rate."""

    __tablename__ = "heart_rate_samples"
    __table_args__ = (
        UniqueConstraint("user_id", "at"),
        CheckConstraint("bpm BETWEEN 25 AND 250", name="bpm_range"),
        CheckConstraint("low BETWEEN 25 AND 250 AND high BETWEEN 25 AND 250", name="span_range"),
        CheckConstraint("low <= bpm AND bpm <= high", name="span_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    at: Mapped[datetime] = mapped_column(UTCDateTime)  # the minute's start
    bpm: Mapped[int] = mapped_column(Integer)
    low: Mapped[int] = mapped_column(Integer)
    high: Mapped[int] = mapped_column(Integer)


class SleepSession(Owned, Base):
    """A night (or nap) from the band (ADR-0055), with minutes per stage. Identified by where it
    came from and when it started; sent again, it is updated."""

    __tablename__ = "sleep_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "start_at"),
        CheckConstraint(
            "asleep_min BETWEEN 0 AND 1440 AND awake_min BETWEEN 0 AND 1440"
            " AND light_min BETWEEN 0 AND 1440 AND deep_min BETWEEN 0 AND 1440"
            " AND rem_min BETWEEN 0 AND 1440",
            name="minutes_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    source: Mapped[str] = mapped_column(String(128))  # the app that wrote it, e.g. com.mi.health
    start_at: Mapped[datetime] = mapped_column(UTCDateTime)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime)
    local_date: Mapped[date] = mapped_column(Date, index=True)  # the day it ended on
    asleep_min: Mapped[int] = mapped_column(Integer)
    awake_min: Mapped[int] = mapped_column(Integer)
    light_min: Mapped[int] = mapped_column(Integer)
    deep_min: Mapped[int] = mapped_column(Integer)
    rem_min: Mapped[int] = mapped_column(Integer)


class ImportedWorkout(Owned, Base):
    """A workout the band recorded (ADR-0055). A cardio one is offered to count; once counted
    it points at the workout it was logged as."""

    __tablename__ = "imported_workouts"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "start_at"),
        CheckConstraint("minutes BETWEEN 0 AND 1440", name="minutes_range"),
        CheckConstraint("avg_hr IS NULL OR avg_hr BETWEEN 25 AND 250", name="avg_hr_range"),
        CheckConstraint("max_hr IS NULL OR max_hr BETWEEN 25 AND 250", name="max_hr_range"),
        CheckConstraint(_in("activity", CardioActivity), name="activity_valid"),
        CheckConstraint("status IN ('new', 'counted', 'dismissed')", name="status_valid"),
        CheckConstraint(
            "zone1_min IS NULL OR (zone1_min BETWEEN 0 AND 1440 AND zone2_min BETWEEN 0 AND 1440"
            " AND zone3_min BETWEEN 0 AND 1440 AND zone4_min BETWEEN 0 AND 1440"
            " AND zone5_min BETWEEN 0 AND 1440)",
            name="zone_minutes_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    source: Mapped[str] = mapped_column(String(128))
    start_at: Mapped[datetime] = mapped_column(UTCDateTime)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime)
    local_date: Mapped[date] = mapped_column(Date, index=True)  # the day it started on
    exercise_type: Mapped[int] = mapped_column(Integer)  # AndroidX EXERCISE_TYPE_*
    activity: Mapped[str | None] = mapped_column(String(16))  # empty: not cardio
    minutes: Mapped[int] = mapped_column(Integer)
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    # Minutes in Karvonen zones 1-5 (ADR-0055); empty without heart rate.
    zone1_min: Mapped[int | None] = mapped_column(Integer)
    zone2_min: Mapped[int | None] = mapped_column(Integer)
    zone3_min: Mapped[int | None] = mapped_column(Integer)
    zone4_min: Mapped[int | None] = mapped_column(Integer)
    zone5_min: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="new", server_default="new")
    workout_id: Mapped[int | None] = mapped_column(ForeignKey("workouts.id", ondelete="SET NULL"))
    # When it was offered in Telegram: each offer is sent once.
    announced_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class AiConnection(Owned, Base):
    """A person's own AI key for comments (ADR-0047 B): one row each. The key is stored only
    encrypted (``services.secret_box``) and is binary, so the export leaves it out; only its
    last four characters are kept in the clear, to show which key it is."""

    __tablename__ = "ai_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    groq_key: Mapped[bytes] = mapped_column(LargeBinary)  # Fernet token
    key_ends: Mapped[str] = mapped_column(String(4))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=true())
    share_body: Mapped[bool] = mapped_column(Boolean, server_default=false())
    share_readiness: Mapped[bool] = mapped_column(Boolean, server_default=false())
    # When the key last failed (revoked, quota, unreadable): the person is told once.
    failed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class AiComment(Owned, Base):
    """The weekly AI comment as sent (ADR-0056), so the web review can show it: one per week,
    kept 7 days. Untrusted LLM text, already cleaned (``services.ai_comment.clean``); shown
    only as plain text, never in a share picture."""

    __tablename__ = "ai_comments"
    __table_args__ = (
        UniqueConstraint("user_id", "week"),
        # ai_comment.LIMIT (1200) plus the " …" a cut comment ends with.
        CheckConstraint("length(text) BETWEEN 1 AND 1202", name="text_length"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    week: Mapped[date] = mapped_column(Date)  # the Monday of the week it reviewed
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# ------------------------------------------- connect my AI (MCP, ADR-0047 C)
# docs/security/mcp-threat-model.md is the spec. Every secret below (codes, tokens, consent
# handles) is 32 random bytes handed out once and kept only as its SHA-256.


class OAuthClient(Base):
    """An AI app that registered itself (RFC 7591). Shared: it belongs to nobody until a person
    approves it with their passkey, and until then it expires. Its name is its own claim."""

    __tablename__ = "oauth_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), unique=True)  # public, not a secret
    name: Mapped[str] = mapped_column(String(60))
    redirect_uris: Mapped[list[str]] = mapped_column(JSON)
    # SHA-256 of the registering address, so pending registrations can be capped per client.
    client_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)  # unless approved
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class OAuthConsent(Base):
    """An open consent page: the authorization request it was made for, then (once the person
    proves their passkey on it) the signed-in browser it is bound to. Single use, 10 minutes."""

    __tablename__ = "oauth_consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle_hash: Mapped[str] = mapped_column(String(64), unique=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True
    )
    redirect_uri: Mapped[str] = mapped_column(String(200))
    scopes: Mapped[list[str]] = mapped_column(JSON)  # as requested
    state: Mapped[str | None] = mapped_column(String(500))
    code_challenge: Mapped[str] = mapped_column(String(128))
    resource: Mapped[str] = mapped_column(String(200))
    # SHA-256 of the address that opened it, so open consent pages can be capped per client.
    client_hash: Mapped[str] = mapped_column(String(64), index=True)
    web_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("web_sessions.id", ondelete="CASCADE")
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class McpConnection(Owned, Base):
    """An AI app a person approved: what it may read, until it is revoked or 90 days after the
    approval, whatever the refreshes. The client's name and redirect address are kept as
    approved, to show on the Account page."""

    __tablename__ = "mcp_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    client_id: Mapped[int] = mapped_column(
        ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True
    )
    client_name: Mapped[str] = mapped_column(String(60))
    redirect_uri: Mapped[str] = mapped_column(String(200))
    scopes: Mapped[list[str]] = mapped_column(JSON)  # as granted
    # The passkey that approved it: removing the key revokes the connection.
    passkey_id: Mapped[int | None] = mapped_column(
        ForeignKey("passkeys.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class OAuthCode(Base):
    """An authorization code: single use, 60 seconds, for one client's redirect address and
    PKCE challenge. Reached only through its connection."""

    __tablename__ = "oauth_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("mcp_connections.id", ondelete="CASCADE"), index=True
    )
    redirect_uri: Mapped[str] = mapped_column(String(200))
    code_challenge: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class OAuthToken(Base):
    """An access token (1 hour) or refresh token (30 days, single use: each refresh rotates
    it) for one connection and one resource. Used refresh tokens are kept until they expire,
    so presenting one again is noticed."""

    __tablename__ = "oauth_tokens"
    __table_args__ = (CheckConstraint("kind IN ('access', 'refresh')", name="kind_valid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(8))
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("mcp_connections.id", ondelete="CASCADE"), index=True
    )
    resource: Mapped[str] = mapped_column(String(200))
    scopes: Mapped[list[str]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class LogProposal(Owned, Base):
    """A log a connected AI proposed (ADR-0058): checked like a typed log, then waiting for the
    person's Save or Discard, on Today or in Telegram. ``payload`` holds what saving writes and
    ``summary`` says it in our own words; both were built from validated values, never from the
    AI's text. Gone 24 hours after it was proposed, saved or not."""

    __tablename__ = "log_proposals"
    __table_args__ = (
        CheckConstraint("kind IN ('strength', 'cardio', 'habits', 'body')", name="kind_valid"),
        CheckConstraint("status IN ('pending', 'saved', 'discarded')", name="status_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _owner()
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("mcp_connections.id", ondelete="CASCADE"), index=True
    )
    # Random, in the Telegram buttons and the web's calls; for a workout it is also the log's
    # token, so saving twice saves once.
    token: Mapped[str] = mapped_column(String(32), unique=True)
    kind: Mapped[str] = mapped_column(String(16))
    local_date: Mapped[date] = mapped_column(Date)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    announced_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # sent to Telegram
    # Telegram refused it for good (not a network failure): not tried again; Today still shows it.
    announce_refused_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


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
    "AiConnection",
    "Base",
    "Event",
    "Exercise",
    "ExerciseState",
    "HabitCheck",
    "HealthDay",
    "HeartRateSample",
    "ImportedWorkout",
    "IngestKey",
    "LadderStep",
    "LogProposal",
    "LoginLink",
    "McpConnection",
    "OAuthClient",
    "OAuthCode",
    "OAuthConsent",
    "OAuthToken",
    "Owned",
    "Passkey",
    "PasskeyChallenge",
    "PlanState",
    "SessionProgress",
    "SessionTemplate",
    "SetLog",
    "SleepSession",
    "TemplateItem",
    "User",
    "UserSettings",
    "WebSession",
    "Workout",
]
