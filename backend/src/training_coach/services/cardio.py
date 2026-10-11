"""Cardio logged in one step from the web (ux-flow-plan A1-A3): the exact minutes and what it
was, one tap for "done as planned", or the rounds from the HIIT timer.

It saves through ``workout_log.save``, so a log is idempotent by its token, can be undone with
/undo, and moves the queue only when it is today's planned session; any other cardio is an
extra. The caller owns the transaction.
"""

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from training_coach.domain.enums import CardioActivity, Side
from training_coach.domain.parser import Entry
from training_coach.services import guided, review, workout_log
from training_coach.services.seed import bundled_plan

ZONE2 = review.ZONE2
MODERATE = review.MODERATE
HIIT = "hiit"
KINDS = (ZONE2, MODERATE, HIIT)  # exercise slugs; HIIT counts rounds, the others minutes
MAX_MINUTES = 600
MAX_ROUNDS = 100


@dataclass(frozen=True)
class Planned:
    """Today's planned session, when it is a single cardio exercise."""

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
    plan = guided.today(session, on, tz)
    if plan is None or len(plan.items) != 1 or plan.items[0].slug not in KINDS:
        return None
    item = plan.items[0]
    return Planned(item.slug, plan.name, item.targets[0])


def week(session: Session, on: date) -> Week:
    minutes = review.cardio_minutes(session, review.week_start(on), on)
    targets = bundled_plan().targets
    return Week(
        minutes.get(ZONE2, 0),
        minutes.get(MODERATE, 0),
        targets.zone2_minutes if targets is not None else None,
    )


def problem(kind: str, value: int) -> str | None:
    """Why a log can't be saved, or None."""
    if kind not in KINDS:
        return "unknown kind of cardio"
    top = MAX_ROUNDS if kind == HIIT else MAX_MINUTES
    if not 1 <= value <= top:
        unit = "rounds" if kind == HIIT else "minutes"
        return f"{unit} must be between 1 and {top}"
    return None


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
) -> Logged | workout_log.Stale:
    """Save one cardio log for ``on``. The caller checks ``problem`` first. ``extra`` files it
    as an extra whatever is planned (a band workout from an earlier day, ADR-0054)."""
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
    )
    result = workout_log.save(session, draft, tz)
    if result is None or isinstance(result, workout_log.Stale):
        return workout_log.Stale()
    return Logged(result, is_planned and not result.already_saved)
