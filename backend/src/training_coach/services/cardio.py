"""Cardio logged in one step from the web (ux-flow-plan A1-A3): the exact minutes and what it
was, one tap for "done as planned", or the rounds from the HIIT timer.

It saves through ``workout_log.save``, so a log is idempotent by its token, can be undone with
/undo, and moves the queue only when it is today's planned session; any other cardio is an
extra. The caller owns the transaction.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from training_coach.domain.cardio import NO_DETAILS, Details, details_problem
from training_coach.domain.enums import CardioActivity, Side
from training_coach.domain.parser import Entry
from training_coach.services import guided, review, workout_log
from training_coach.services.day_clash import Clash, Refused, Resolution
from training_coach.services.seed import bundled_plan

ZONE2 = review.ZONE2
MODERATE = review.MODERATE
HIIT = "hiit"
KINDS = (ZONE2, MODERATE, HIIT)  # exercise slugs; HIIT counts rounds, the others minutes
MAX_MINUTES = 600
MAX_ROUNDS = 100


@dataclass(frozen=True)
class Planned:
    """Today's planned cardio (``planned``)."""

    kind: str  # one of KINDS
    session: str  # its name, e.g. "Long zone 2"
    target: int  # minutes, or rounds for HIIT


@dataclass(frozen=True)
class Week:
    zone2: int  # minutes this week, Monday to today
    moderate: int
    zone2_target: tuple[int, int] | None  # from plan.toml


@dataclass(frozen=True)
class Logged:
    saved: workout_log.Saved
    planned: bool  # it completed today's planned session


def planned(session: Session, on: date, tz: ZoneInfo) -> Planned | None:
    """Today's planned cardio: a session that is one cardio exercise, or a conditioning
    session with a block after its cardio (ADR-0066), whose cardio is logged in one step and
    leaves the block open. None once that cardio is logged."""
    plan = guided.today(session, on, tz)
    if plan is None or plan.after_run:
        return None
    found = [i for i in plan.items if i.slug in KINDS]
    if len(found) != 1 or (len(plan.items) > 1 and plan.kind != "conditioning"):
        return None
    return Planned(found[0].slug, plan.name, found[0].targets[0])


def week(session: Session, on: date) -> Week:
    minutes = review.cardio_minutes(session, review.week_start(on), on)
    targets = bundled_plan().targets
    return Week(
        minutes.get(ZONE2, 0),
        minutes.get(MODERATE, 0),
        targets.zone2_minutes if targets is not None else None,
    )


def problem(kind: str, value: int, details: Details = NO_DETAILS) -> str | None:
    """Why a log can't be saved, or None."""
    if kind not in KINDS:
        return "unknown kind of cardio"
    top = MAX_ROUNDS if kind == HIIT else MAX_MINUTES
    if not 1 <= value <= top:
        unit = "rounds" if kind == HIIT else "minutes"
        return f"{unit} must be between 1 and {top}"
    return details_problem(details, rounds=kind == HIIT)


def started(on: date, clock: time, tz: ZoneInfo, now: datetime) -> datetime | None:
    """When a log on ``on`` started, from the local clock time typed, in UTC; None when that
    is still to come (a start can't be in the future)."""
    at = datetime.combine(on, clock, tzinfo=tz).astimezone(UTC)
    return at if at <= now else None


def log(
    session: Session,
    on: date,
    tz: ZoneInfo,
    kind: str,
    value: int,
    activity: CardioActivity | None,
    token: str,
    *,
    extra: bool = False,
    answer: Resolution | None = None,
    details: Details = NO_DETAILS,
) -> Logged | workout_log.Stale | Clash | Refused:
    """Save one cardio log for ``on``. The caller checks ``problem`` first. ``extra`` files it
    as an extra whatever is planned (a band workout from an earlier day, ADR-0055). Today's
    planned session asks first when the day already has its session (ADR-0060)."""
    today = None if extra else planned(session, on, tz)
    is_planned = today is not None and today.kind == kind
    template = workout_log.target(session, on, tz) if is_planned else None
    draft = workout_log.Draft(
        token=token,
        on=on,
        template_id=template.id if template is not None else None,
        session_name=template.name if template is not None else workout_log.EXTRA,
        entries=(Entry(kind, ((1, Side.BOTH, value),)),),
        problems=(),
        strength=workout_log.strength_on(session, on, tz, template),
        extra=not is_planned,
        activity=activity.value if activity is not None else None,
        cardio=details,
    )
    result = workout_log.save(session, draft, tz, answer)
    if result is None or isinstance(result, workout_log.Stale):
        return workout_log.Stale()
    if not isinstance(result, workout_log.Saved):
        return result
    return Logged(result, is_planned and not result.already_saved)
