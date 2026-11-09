"""The walk-through's answers (ADR-0092): kept only with ``walkthrough`` consent (ADR-0090), one
row per person, replaced by a re-run, and deleted when the consent is withdrawn
(``consent.withdraw``). Callers pass a session bound to the person (ADR-0029), whose consent
is the one checked. Health data: the answers are never logged."""

from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import WalkthroughAnswers
from training_coach.db.session import bound_user
from training_coach.domain.consent import VERSIONS, Category
from training_coach.domain.walkthrough import (
    AgeBand,
    Answers,
    Effort,
    HowLong,
    Often,
    placement_from_json,
    placement_json,
)
from training_coach.services import consent

log = structlog.get_logger(__name__)


def kept(session: Session) -> Answers | None:
    """The person's answers, or None when none are kept or the category isn't open to them now
    (a yes to older wording no longer counts, though only a withdrawal erases)."""
    row = session.scalar(select(WalkthroughAnswers))
    if row is None or not _open(session):
        return None
    return Answers(
        age_band=AgeBand(row.age_band) if row.age_band else None,
        often=Often(row.often) if row.often else None,
        effort=Effort(row.effort) if row.effort else None,
        how_long=HowLong(row.how_long) if row.how_long else None,
        chair=row.chair,
        stairs=row.stairs,
        walk=row.walk,
        floor=row.floor,
        weekdays=tuple(row.weekdays),
        placement=placement_from_json(row.placement),
    )


def keep(session: Session, answers: Answers, now: datetime) -> bool:
    """Keep ``answers`` in place of any kept before, if the person has the category open; False,
    keeping nothing, if not."""
    if not _open(session):
        return False
    row = session.scalar(select(WalkthroughAnswers))
    if row is None:
        row = WalkthroughAnswers()
        session.add(row)
    row.version = VERSIONS[Category.WALKTHROUGH]
    row.answered_at = now
    row.age_band = answers.age_band.value if answers.age_band else None
    row.often = answers.often.value if answers.often else None
    row.effort = answers.effort.value if answers.effort else None
    row.how_long = answers.how_long.value if answers.how_long else None
    row.chair, row.stairs, row.walk, row.floor = (
        answers.chair,
        answers.stairs,
        answers.walk,
        answers.floor,
    )
    row.weekdays = sorted(answers.weekdays)
    row.placement = placement_json(answers.placement)
    session.flush()
    log.info("walkthrough.answers_kept")  # never the answers themselves
    return True


def _open(session: Session) -> bool:
    """Whether the person the session is bound to has ``walkthrough`` open: by the session, so
    the consent checked is always the person whose row is read or written (security review)."""
    user_id = bound_user(session)
    if user_id is None:
        raise PermissionError("the walk-through's answers need a session bound to the person")
    return consent.opened(session, user_id, Category.WALKTHROUGH)
