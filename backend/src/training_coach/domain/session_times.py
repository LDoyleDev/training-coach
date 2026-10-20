"""How long a guided session's sets take (ADR-0061).

Each set of a guided session carries two times from the phone: when its screen appeared and
when it was confirmed. They are checked here before they are kept.
"""

from datetime import datetime, timedelta

SLACK = timedelta(minutes=1)  # a phone's clock a little ahead of the server's
MAX_AGE = timedelta(hours=36)  # a session resumed the next morning still has its times


def plausible(started_at: datetime, done_at: datetime, now: datetime) -> bool:
    """Whether a set's times can be kept: the start before the end, neither in the future
    (beyond ``SLACK``) and both within ``MAX_AGE``. Times failing this are dropped, never the
    set, so a phone with a wrong clock never stops a log."""
    return now - MAX_AGE <= started_at <= done_at <= now + SLACK
