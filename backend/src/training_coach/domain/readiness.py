"""When the health questions are due (ADR-0085, superseding ADR-0046's stored answers). Pure
logic, no I/O.

Ten yes-or-no questions, asked in the browser (``frontend/src/readiness/questions.ts``): the
answers and the note they lead to stay on the device. The server keeps only when they were last
answered and which version, so it asks again after a year or when the questions change, and
reminds before a hard session. It never knows what anyone answered.
"""

from datetime import datetime, timedelta

VERSION = 2  # bump with the questions in questions.ts: everyone is asked again (a test checks)
RENEW = timedelta(days=365)  # "We'll ask again in a year" (ADR-0085)

# The hardest work: all-out intervals, and test days (max efforts, the 12-minute run).
HARD_SESSIONS = frozenset({"hiit"})


def due(version: int | None, answered: datetime | None, now: datetime) -> bool:
    """Never answered, a year ago or more, or an older version of the questions."""
    return answered is None or version != VERSION or now - answered >= RENEW


DUE_NOTE = (
    "Today is a hard session. Before you go all out, answer the health questions on the "
    "Readiness page: ten yes-or-no questions, and the answers stay on your device."
)
HARD_NOTE = (
    "Today is a hard session. If your health answers suggested asking a doctor first, we "
    "suggest doing that before you go all out. You decide."
)


def note(is_due: bool, hard: bool) -> str | None:
    """What Today says on a hard day, if anything: answer the questions, or the general line."""
    if not hard:
        return None
    return DUE_NOTE if is_due else HARD_NOTE
