"""The app's Groq key is shared (ADR-0059, multi-user-plan.md H1): each member may use it a
number of times a day, so one person can't use up the day for everyone; past that, they type
instead. Admins, the owner, have no cap. A use is a voice note or a fallback reading that Groq
answered: a failed call isn't counted, so an outage can't spend someone's day.

Counted from the person's own ``groq.used`` events since their local midnight; the session is
bound to them, so the count is theirs.
"""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, User
from training_coach.db.session import bound_user
from training_coach.services.users import ADMIN

MEMBER_CAP = 20  # uses a day ("say 20", H1)
USED = "groq.used"


def _admin(session: Session) -> bool:
    """Only a session known to be an admin's goes uncapped: a cost guard fails closed."""
    user = bound_user(session)
    person = session.get(User, user) if user is not None else None
    return person is not None and person.role == ADMIN


def left(session: Session, now: datetime, tz: ZoneInfo) -> bool:
    """Whether this person may use the shared key now; never for a session bound to nobody."""
    if _admin(session):
        return True
    if bound_user(session) is None:
        return False
    midnight = datetime.combine(now.astimezone(tz).date(), time(), tz).astimezone(UTC)
    used = session.scalar(
        select(func.count()).select_from(Event).where(Event.kind == USED, Event.at >= midnight)
    )
    return (used or 0) < MEMBER_CAP


def count(session: Session, now: datetime) -> None:
    """One use Groq answered, for a member; nothing for an admin."""
    if not _admin(session) and bound_user(session) is not None:
        session.add(Event(kind=USED, at=now, payload={}))
        session.flush()
