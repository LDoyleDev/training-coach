"""Logging any day from the web (ADR-0060): pick a day, today back to 14 days, then what was
done: a planned session, its exercises as an extra, cardio, or (on an earlier day) a rest day.

Sets are entered against the session's exercises and targets, as in the guided session's
check, and saved through ``workout_log.save``: an earlier day is filed as a past-day log
(ADR-0033); today, the session picked is done out of turn unless it is the queue's
(ADR-0016). So a clash with the day's session asks first, /undo takes it back and a repeated
save (same token) changes nothing. The caller owns the transaction.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import SessionTemplate
from training_coach.domain.dates import day_problem
from training_coach.domain.enums import CardioActivity
from training_coach.services import blocks, cardio, guided, workout_log
from training_coach.services.day_clash import Clash, Refused, Resolution
from training_coach.services.today import SessionPlan, session_plan

REST_TODAY = "to rest today, use Rest today on Today"
NO_SETS = "no sets to save"
NO_SESSION = "no such session"

Saving = workout_log.Saved | workout_log.Stale | Clash | Refused | str


@dataclass(frozen=True)
class Choice:
    template_id: int
    name: str
    kind: str  # strength | conditioning | recovery


def choices(session: Session) -> list[Choice]:
    """Every session in the plan, in plan order."""
    rows = session.scalars(select(SessionTemplate).order_by(SessionTemplate.position))
    return [Choice(t.id, t.name, t.kind) for t in rows]


def plan(session: Session, day: date, template_id: int, tz: ZoneInfo) -> SessionPlan | None:
    """The session's exercises and targets, in the training block of ``day`` (ADR-0028)."""
    return session_plan(session, template_id, blocks.current(session, day, tz))


def _saved(found: workout_log.Saving) -> Saving:
    return NO_SETS if found is None else found


def save_sets(
    session: Session,
    day: date,
    today: date,
    tz: ZoneInfo,
    template_id: int,
    sets: Sequence[guided.Done],
    token: str,
    *,
    extra: bool = False,
    answer: Resolution | None = None,
) -> Saving:
    """Save the sets done of a session's exercises on ``day``, as that session or, with
    ``extra``, as an extra that completes nothing. A problem message when it can't be."""
    if (problem := day_problem(day, today)) is not None:
        return problem
    template = session.get(SessionTemplate, template_id)
    found = plan(session, day, template_id, tz) if template is not None else None
    if template is None or found is None:
        return NO_SESSION
    if not sets:
        return NO_SETS
    if (problem := guided.sets_problem(found.items, sets)) is not None:
        return problem
    planned = None if extra else template
    draft = workout_log.Draft(
        token=token,
        on=day,
        template_id=planned.id if planned is not None else None,
        session_name=planned.name if planned is not None else workout_log.EXTRA,
        entries=guided.entries(found.items, sets),
        problems=(),
        strength=workout_log.strength_on(session, day, tz, planned),
        backdated=day < today,
        extra=extra and day == today,
        chosen=planned is not None and day == today,
    )
    return _saved(workout_log.save(session, draft, tz, answer))


def save_rest(
    session: Session,
    day: date,
    today: date,
    tz: ZoneInfo,
    token: str,
    answer: Resolution | None = None,
) -> Saving:
    """A rest day on an earlier day (ADR-0033): no sets, and the queue stays put. Today's rest
    is Rest today, which holds the session for tomorrow (ADR-0022)."""
    if day >= today:
        return REST_TODAY
    if (problem := day_problem(day, today)) is not None:
        return problem
    draft = workout_log.Draft(
        token=token,
        on=day,
        template_id=None,
        session_name="Rest day",
        entries=(),
        problems=(),
        backdated=True,
        rest=True,
    )
    return _saved(workout_log.save(session, draft, tz, answer))


def save_cardio(
    session: Session,
    day: date,
    today: date,
    tz: ZoneInfo,
    kind: str,
    value: int,
    activity: CardioActivity | None,
    token: str,
    answer: Resolution | None = None,
) -> Saving:
    """Cardio on ``day``: today, as on Log cardio (today's planned cardio when it is that
    kind); an earlier day, an extra, as a band workout from then is (ADR-0055)."""
    if (problem := day_problem(day, today) or cardio.problem(kind, value)) is not None:
        return problem
    logged = cardio.log(
        session, day, tz, kind, value, activity, token, extra=day != today, answer=answer
    )
    return logged.saved if isinstance(logged, cardio.Logged) else logged
