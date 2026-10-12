"""Logs a connected AI proposes, and the person saves or discards (ADR-0058; ADR-0047 C2;
mcp-threat-model.md M10 and requirement 15).

``propose_log`` never saves. What it sends is checked as hard as a typed log: strength sets go
through the typed-log model (``groq.Rewrite``) and the rule parser, cardio, habits and body
measurements through the checks of their own save paths; anything else is refused with a short
reason. A valid proposal waits in ``log_proposals`` with a random token, as a card on Today and
a Telegram message, each with Save and Discard. Only the person's web session or their bot
button resolves it, and resolving it in one place resolves it everywhere. Saving goes through
the same service as a log of that kind, so /undo takes a workout back as usual.

At most ``PER_CONNECTION`` wait per connection. Each row is gone ``TTL`` after it was proposed,
saved or not (cleared whenever proposals are read or written, like the OAuth codes), and
revoking the connection discards its waiting ones. Events name the proposal and its connection,
never what it held. The caller owns the transaction and passes a session bound to the person.
"""

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal, get_args
from zoneinfo import ZoneInfo

import structlog
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, LogProposal, McpConnection
from training_coach.db.session import ALL_USERS
from training_coach.domain.dates import MAX_DAYS_BACK
from training_coach.domain.enums import CardioActivity, ExerciseKind, Side
from training_coach.domain.habits import LABELS as HABIT_LABELS
from training_coach.domain.habits import Habit, can_change
from training_coach.domain.measurements import SPECS, to_tenths
from training_coach.domain.measurements import Kind as Measure
from training_coach.domain.parser import Entry, sets_text
from training_coach.domain.queue import local_date
from training_coach.services import cardio, habits, measurements, workout_log
from training_coach.services.cardio import MAX_MINUTES
from training_coach.services.groq import Rewrite, RewriteLine

log = structlog.get_logger(__name__)

STRENGTH, CARDIO, HABITS, BODY = "strength", "cardio", "habits", "body"
PENDING, SAVED, DISCARDED = "pending", "saved", "discarded"
PER_CONNECTION = 3
TTL = timedelta(hours=24)
SUMMARY_LENGTH = 1000  # the column's size: a bigger proposal is refused, never cut
NAME_LENGTH = 40  # of the app's claimed name, as shown on the card and in Telegram
REASONS = 3  # problems named in one refusal


# ------------------------------------------------------------------ what may be proposed


class _Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date | None = None  # today when left out


class StrengthProposal(_Proposal):
    kind: Literal["strength"]
    exercises: list[RewriteLine] = Field(min_length=1, max_length=30)


class CardioProposal(_Proposal):
    kind: Literal["cardio"]
    cardio: Literal["zone2", "moderate-cardio"]
    minutes: int = Field(ge=1, le=MAX_MINUTES)
    activity: CardioActivity | None = None


class HabitsProposal(_Proposal):
    kind: Literal["habits"]
    habits: list[Habit] = Field(min_length=1, max_length=len(Habit))


# Body weight and girths: resting heart rate comes from the band or the Body page.
BodyKind = Literal["bodyweight", "waist", "chest", "upper_arm", "thigh"]


class BodyProposal(_Proposal):
    kind: Literal["body"]
    measurements: dict[BodyKind, Annotated[float, Field(allow_inf_nan=False)]] = Field(
        min_length=1, max_length=5
    )


Proposal = Annotated[
    StrengthProposal | CardioProposal | HabitsProposal | BodyProposal, Field(discriminator="kind")
]
_PROPOSAL: TypeAdapter[Proposal] = TypeAdapter(Proposal)

# The tool's input, for the AI: one flat object, checked above by kind.
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": [STRENGTH, CARDIO, HABITS, BODY]},
        "day": {
            "type": "string",
            "format": "date",
            "description": "YYYY-MM-DD: today (the default) or an earlier day, never the future",
        },
        "exercises": {
            "type": "array",
            "description": "strength: each exercise by its name in the plan, with one number "
            "per set, in reps (unit '') or seconds (unit 's')",
            "items": {
                "type": "object",
                "properties": {
                    "exercise": {"type": "string"},
                    "sets": {"type": "array", "items": {"type": "integer", "minimum": 0}},
                    "unit": {"type": "string", "enum": ["", "s", "min"]},
                },
                "required": ["exercise", "sets", "unit"],
                "additionalProperties": False,
            },
        },
        "cardio": {"type": "string", "enum": ["zone2", "moderate-cardio"]},
        "minutes": {"type": "integer", "minimum": 1, "maximum": MAX_MINUTES},
        "activity": {"type": "string", "enum": [a.value for a in CardioActivity]},
        "habits": {"type": "array", "items": {"type": "string", "enum": [h.value for h in Habit]}},
        "measurements": {
            "type": "object",
            "description": "body: kg for bodyweight, cm for the girths",
            "properties": {k: {"type": "number"} for k in get_args(BodyKind)},
            "additionalProperties": False,
        },
    },
    "required": ["kind"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Refused:
    reason: str  # short, for the AI to read and fix


@dataclass(frozen=True)
class Proposed:
    id: int
    summary: str


@dataclass(frozen=True)
class _Checked:
    kind: str
    day: date
    payload: dict[str, Any]
    summary: str


def _reason(error: ValidationError) -> str:
    """Pydantic's complaints as one short line, without echoing the input."""
    found = error.errors(include_url=False, include_input=False, include_context=False)
    parts = []
    for item in found[:REASONS]:
        loc = item["loc"]
        loc = loc[1:] if loc[:1] in ((STRENGTH,), (CARDIO,), (HABITS,), (BODY,)) else loc
        where = ".".join(str(p) for p in loc)  # without the kind pydantic puts first
        parts.append(f"{where}: {item['msg']}" if where else str(item["msg"]))
    return "; ".join(parts)


def _when(day: date) -> str:
    return f"{day:%a %d %b}"


def _day_problem(day: date, today: date, days_back: int) -> str | None:
    if day > today:
        return "that day hasn't happened yet: propose today or an earlier day"
    if (today - day).days > days_back:
        return f"that's more than {days_back} days ago"
    return None


def _strength(
    session: Session, found: StrengthProposal, day: date, today: date, tz: ZoneInfo
) -> _Checked | Refused:
    if problem := _day_problem(day, today, MAX_DAYS_BACK):
        return Refused(problem)
    if any(not line.sets for line in found.exercises):
        return Refused("every exercise needs at least one set")
    if any(not line.exercise.isprintable() for line in found.exercises):
        return Refused("exercise names are plain text on one line")
    if day < today and workout_log.day_saved(session, day):
        return Refused(f"a session is already saved for {_when(day)}")
    # Always under a date line of our own (ADR-0033: today's date on top is an ordinary log),
    # so nothing the AI wrote can be read as one.
    text = f"{day.isoformat()}\n{workout_log.rewrite_text(Rewrite(lines=found.exercises))}"
    draft = workout_log.draft(session, text, today, tz)
    if draft.problems or not draft.entries or draft.rest or draft.on != day:
        return Refused("; ".join(draft.problems[:REASONS]) or "nothing to log")
    labels = workout_log.exercise_labels(session)
    for entry in draft.entries:
        name, kind = labels[entry.slug]
        if kind is ExerciseKind.DURATION_MIN:
            return Refused(f"{name} is cardio: propose it with kind cardio")
    shown = "; ".join(
        f"{labels[e.slug][0]} {sets_text(e, labels[e.slug][1])}" for e in draft.entries
    )
    payload = {
        "template_id": draft.template_id,
        "session_name": draft.session_name,
        "entries": [[e.slug, [[n, side.value, v] for n, side, v in e.sets]] for e in draft.entries],
        "strength": draft.strength,
        "backdated": draft.backdated,
    }
    return _Checked(STRENGTH, day, payload, f"{draft.session_name} on {_when(day)}: {shown}")


def _cardio(session: Session, found: CardioProposal, day: date, today: date) -> _Checked | Refused:
    if problem := _day_problem(day, today, MAX_DAYS_BACK):
        return Refused(problem)
    if problem := cardio.problem(found.cardio, found.minutes):
        return Refused(problem)
    name = workout_log.exercise_labels(session).get(found.cardio, (found.cardio,))[0]
    what = f" ({found.activity.value})" if found.activity is not None else ""
    payload = {
        "cardio": found.cardio,
        "minutes": found.minutes,
        "activity": found.activity.value if found.activity is not None else None,
    }
    return _Checked(CARDIO, day, payload, f"{name}, {found.minutes} min{what}, on {_when(day)}")


def _habits(found: HabitsProposal, day: date, today: date) -> _Checked | Refused:
    if day > today:
        return Refused("that day hasn't happened yet: propose today or an earlier day")
    if not can_change(day, today):
        return Refused("habits can only be ticked for today and the two days before")
    ticked = list(dict.fromkeys(found.habits))  # in the order given, once each
    names = ", ".join(HABIT_LABELS[h] for h in ticked)
    payload = {"habits": [h.value for h in ticked]}
    return _Checked(HABITS, day, payload, f"Done on {_when(day)}: {names}")


def _body(found: BodyProposal, day: date, today: date) -> _Checked | Refused:
    if problem := _day_problem(day, today, MAX_DAYS_BACK):
        return Refused(problem)
    shown = []
    for name, value in found.measurements.items():
        kind = Measure(name)
        tenths = to_tenths(kind, value)
        if isinstance(tenths, str):
            return Refused(tenths)
        spec = SPECS[kind]
        shown.append(f"{spec.label} {tenths / 10:.{spec.decimals}f} {spec.unit}")
    payload = {"measurements": dict(found.measurements)}
    return _Checked(BODY, day, payload, f"Measured on {_when(day)}: {', '.join(shown)}")


def check(
    session: Session, arguments: Mapping[str, Any], today: date, tz: ZoneInfo
) -> _Checked | Refused:
    """What saving the proposal would write, or why it can't be proposed. Never writes."""
    try:
        found = _PROPOSAL.validate_python(dict(arguments))
    except ValidationError as error:
        return Refused(_reason(error))
    day = found.day or today
    checked: _Checked | Refused
    if isinstance(found, StrengthProposal):
        checked = _strength(session, found, day, today, tz)
    elif isinstance(found, CardioProposal):
        checked = _cardio(session, found, day, today)
    elif isinstance(found, HabitsProposal):
        checked = _habits(found, day, today)
    else:
        checked = _body(found, day, today)
    if isinstance(checked, _Checked) and len(checked.summary) > SUMMARY_LENGTH:
        return Refused("that's too much for one proposal: split it into smaller ones")
    return checked


# ------------------------------------------------------------------------- proposing


def _event(session: Session, kind: str, row: LogProposal, **more: str) -> None:
    payload = {"connection_id": row.connection_id, "proposal_id": row.id, **more}
    session.add(Event(kind=kind, payload=payload, user_id=row.user_id))
    log.info(kind, **payload)


def sweep(session: Session, now: datetime) -> None:
    """Remove rows past their 24 hours; a waiting one is noted as expired."""
    for row in session.scalars(select(LogProposal).where(LogProposal.expires_at <= now)):
        if row.status == PENDING:
            _event(session, "mcp.draft_expired", row)
        session.delete(row)
    session.flush()


def propose(
    session: Session,
    connection_id: int,
    arguments: Mapping[str, Any],
    tz: ZoneInfo,
    now: datetime,
) -> Proposed | Refused:
    """A proposal from a connection, waiting for the person; or why it was refused."""
    sweep(session, now)
    waiting = session.scalar(
        select(func.count())
        .select_from(LogProposal)
        .where(LogProposal.connection_id == connection_id, LogProposal.status == PENDING)
    )
    if (waiting or 0) >= PER_CONNECTION:
        return Refused(
            f"{PER_CONNECTION} proposals are already waiting for the person: wait until they "
            "save or discard one"
        )
    checked = check(session, arguments, local_date(now, tz), tz)
    if isinstance(checked, Refused):
        return checked
    row = LogProposal(
        connection_id=connection_id,
        token=secrets.token_hex(16),
        kind=checked.kind,
        local_date=checked.day,
        payload=checked.payload,
        summary=checked.summary,
        created_at=now,
        expires_at=now + TTL,
    )
    session.add(row)
    session.flush()
    return Proposed(row.id, row.summary)


# -------------------------------------------------------------- what the person sees


@dataclass(frozen=True)
class Pending:
    id: int
    token: str
    kind: str
    on: date
    summary: str  # exactly what Save writes, in our words
    source: str  # the app's name as it claimed it, cut to NAME_LENGTH
    expires_at: datetime

    @property
    def text(self) -> str:
        return f"From “{self.source}”: {self.summary}"


def _source(name: str) -> str:
    clean = " ".join("".join(c if c.isprintable() else " " for c in name).split())
    return clean if len(clean) <= NAME_LENGTH else clean[: NAME_LENGTH - 1] + "…"


def _pending(row: LogProposal, name: str) -> Pending:
    return Pending(
        row.id, row.token, row.kind, row.local_date, row.summary, _source(name), row.expires_at
    )


def pending(session: Session, now: datetime, *, unannounced: bool = False) -> list[Pending]:
    """Proposals waiting for the person, oldest first; with ``unannounced``, only those not
    yet sent to Telegram (the caller marks each one once it is sent)."""
    sweep(session, now)
    query = (
        select(LogProposal, McpConnection.client_name)
        .join(McpConnection, LogProposal.connection_id == McpConnection.id)
        .where(LogProposal.status == PENDING)
        .order_by(LogProposal.id)
    )
    if unannounced:
        query = query.where(LogProposal.announced_at.is_(None))
    return [_pending(row, name) for row, name in session.execute(query)]


def announced(session: Session, proposal_id: int, now: datetime) -> None:
    row = session.get(LogProposal, proposal_id)
    if row is not None:
        row.announced_at = now
        session.flush()


# -------------------------------------------------------------------- save or discard


@dataclass(frozen=True)
class Saved:
    summary: str
    workout: bool  # a workout was saved: /undo can take it back


@dataclass(frozen=True)
class Already:
    status: str  # "saved" or "discarded"


@dataclass(frozen=True)
class Gone:
    """No such proposal: expired, or never there."""


@dataclass(frozen=True)
class Changed:
    """It can't be saved as proposed any more (today's session changed, the day is too long
    ago now): it was discarded, nothing was written."""

    reason: str


@dataclass(frozen=True)
class Discarded:
    pass


Resolved = Saved | Discarded | Already | Gone | Changed


def _find(session: Session, token: str, now: datetime) -> LogProposal | None:
    sweep(session, now)
    return session.scalar(select(LogProposal).where(LogProposal.token == token))


def _resolve(
    session: Session, row: LogProposal, status: str, now: datetime, by: str, why: str = "tap"
) -> None:
    row.status, row.resolved_at = status, now
    kind = "mcp.draft_saved" if status == SAVED else "mcp.draft_discarded"
    _event(session, kind, row, by=by, why=why)
    session.flush()


def _write(session: Session, row: LogProposal, tz: ZoneInfo, today: date) -> str | None:
    """Save through the service of the proposal's kind; why not, when it no longer fits."""
    data, day = row.payload, row.local_date
    if row.kind == STRENGTH:
        if data["backdated"] and workout_log.day_saved(session, day):
            return f"a session was saved for {_when(day)} meanwhile"
        draft = workout_log.Draft(
            token=row.token,
            on=day,
            template_id=data["template_id"],
            session_name=data["session_name"],
            entries=tuple(
                Entry(slug, tuple((n, Side(side), v) for n, side, v in sets))
                for slug, sets in data["entries"]
            ),
            problems=(),
            strength=data["strength"],
            backdated=data["backdated"],
        )
        result = workout_log.save(session, draft, tz)
        return None if isinstance(result, workout_log.Saved) else "today's session changed"
    if row.kind == CARDIO:
        activity = CardioActivity(data["activity"]) if data["activity"] else None
        logged = cardio.log(
            session,
            day,
            tz,
            data["cardio"],
            data["minutes"],
            activity,
            row.token,
            extra=day != today,
        )
        return "today's session changed" if isinstance(logged, workout_log.Stale) else None
    if row.kind == HABITS:
        if not can_change(day, today):
            return "that day is too long ago to tick now"
        for habit in data["habits"]:
            habits.mark(session, day, Habit(habit), True, today)
        return None
    values = {Measure(k): float(v) for k, v in data["measurements"].items()}
    return measurements.save(session, day, today, values)


def save(
    session: Session, token: str, tz: ZoneInfo, now: datetime, by: str
) -> Saved | Already | Gone | Changed:
    """Save a waiting proposal, once. ``by`` is where the person tapped (web or telegram)."""
    row = _find(session, token, now)
    if row is None:
        return Gone()
    if row.status != PENDING:
        return Already(row.status)
    problem = _write(session, row, tz, local_date(now, tz))
    if problem is not None:  # nothing was written: each service checks before it writes
        _resolve(session, row, DISCARDED, now, by, "changed")
        return Changed(problem)
    _resolve(session, row, SAVED, now, by)
    return Saved(row.summary, workout=row.kind in (STRENGTH, CARDIO))


def discard(session: Session, token: str, now: datetime, by: str) -> Discarded | Already | Gone:
    row = _find(session, token, now)
    if row is None:
        return Gone()
    if row.status != PENDING:
        return Already(row.status)
    _resolve(session, row, DISCARDED, now, by)
    return Discarded()


def discard_for(session: Session, connection_id: int, now: datetime) -> None:
    """Discard a connection's waiting proposals: it was revoked. ``session`` may be unbound
    (``/recover`` revokes every connection)."""
    for row in session.scalars(
        select(LogProposal).where(
            LogProposal.connection_id == connection_id, LogProposal.status == PENDING
        ),
        execution_options={ALL_USERS: True},
    ):
        _resolve(session, row, DISCARDED, now, "connection", "revoked")
