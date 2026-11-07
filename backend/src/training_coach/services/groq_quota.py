"""The app's Groq key is shared (ADR-0059, multi-user-plan.md H1): each member may use it a
number of times a day, so one person can't use up the day for everyone; past that, they type
instead. Admins, the owner, have no cap. A use is a voice note or a fallback reading that Groq
answered: a failed call isn't counted, so an outage can't spend someone's day.

Counted from the person's own ``groq.used`` events since their local midnight; the session is
bound to them, so the count is theirs.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, User
from training_coach.db.session import bound_user
from training_coach.services.users import ADMIN

MEMBER_CAP = 20  # uses a day ("say 20", H1)
USED = "groq.used"


def _capped(session: Session) -> bool:
    user = bound_user(session)
    person = session.get(User, user) if user is not None else None
    return person is not None and person.role != ADMIN


def left(session: Session, now: datetime, tz: ZoneInfo) -> bool:
    """Whether this person may use the shared key now."""
    if not _capped(session):
        return True
    midnight = datetime.combine(now.astimezone(tz).date(), time(), tz)
    used = session.scalar(
        select(func.count()).select_from(Event).where(Event.kind == USED, Event.at >= midnight)
    )
    return (used or 0) < MEMBER_CAP


def count(session: Session, now: datetime) -> None:
    """One use Groq answered, for a member; nothing for an admin."""
    if _capped(session):
        session.add(Event(kind=USED, at=now, payload={}))
        session.flush()
