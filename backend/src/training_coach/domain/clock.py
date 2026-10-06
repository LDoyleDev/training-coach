"""Wall-clock times typed by the user. Pure logic, no I/O."""

import re
from datetime import time

_HHMM = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*$")


def parse_hhmm(text: str) -> time | None:
    """``07:30``, ``7:30`` or ``7.30`` as a time; None for anything else."""
    match = _HHMM.match(text)
    if match is None:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)
