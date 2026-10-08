"""A date on the first line of a log, for logging a past day (#104, ADR-0033). Pure logic.

Accepted: ``yesterday``, a weekday (the most recent one before today), ``29 Sep`` or
``Tue 29 Sep`` (the most recent such date), ``29/9`` (day/month) and ``2026-09-29``. Whatever
follows the date on that line ("Legs", "rest", "- Day 1 Legs") is returned for the caller.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

MAX_DAYS_BACK = 14
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_WEEKDAY = (
    r"(?P<wd>mon(?:day)?|tue(?:s|sday)?|wed(?:s|nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?"
    r"|sat(?:urday)?|sun(?:day)?)\b\.?,?"
)
_DATE = (
    rf"^\s*(?:{_WEEKDAY}\s+)?"
    r"(?:(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<month>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
    r"|(?P<d>\d{1,2})/(?P<m>\d{1,2})(?![/\d])"
    r"|(?P<iso>\d{4}-\d{2}-\d{2}))"
    r"(?P<rest>(?:\W.*)?)$"
)
DATE = re.compile(_DATE, re.IGNORECASE)
WORD = re.compile(
    rf"^\s*(?:(?P<yesterday>yesterday)|{_WEEKDAY})(?P<rest>(?:\W.*)?)$", re.IGNORECASE
)
LEAD = re.compile(r"^[\s:,\-\u2013\u2014]+")  # separators after the date, dashes too


@dataclass(frozen=True)
class DateLine:
    day: date
    rest: str  # the rest of the line, e.g. "Legs" or "rest"


def _recent(month: int, day: int, today: date) -> date | None:
    """The most recent ``day``/``month`` on or before today (last year's, early in January)."""
    try:
        found = date(today.year, month, day)
        return found if found <= today else date(today.year - 1, month, day)
    except ValueError:  # no such day, or 29 Feb in a year without one
        return None


def date_line(line: str, today: date) -> DateLine | str | None:
    """The day a log's first line names, a problem message, or None when it isn't a date."""
    found = DATE.match(line)
    word = None if found else WORD.match(line)
    if found is None and word is None:
        return None
    match = found or word
    assert match is not None  # noqa: S101 - one of them matched
    rest = LEAD.sub("", match["rest"] or "").strip()
    named = match["wd"].lower()[:3] if match["wd"] else None
    if word is not None:
        if any(c.isdigit() for c in rest):  # "sun salutation 5" is a log, not Sunday
            return None
        if word["yesterday"]:
            return DateLine(today - timedelta(days=1), rest)
        back = (today.weekday() - WEEKDAYS.index(str(named))) % 7 or 7
        return DateLine(today - timedelta(days=back), rest)
    if match["iso"]:
        try:
            day: date | None = date.fromisoformat(match["iso"])
        except ValueError:
            day = None
    elif match["month"]:
        month = match["month"].lower()
        day = _recent(MONTHS.index(month) + 1, int(match["day"]), today)
    else:
        day = (
            _recent(int(match["m"]), int(match["d"]), today) if 1 <= int(match["m"]) <= 12 else None
        )
    shown = line.strip()[:40]
    if day is None:
        return f"'{shown}' isn't a date I can read"
    if named is not None and WEEKDAYS[day.weekday()] != named:
        return f"{day:%d %b} was a {day:%A}, not what '{shown}' says"
    if day > today:
        return f"{day:%a %d %b} hasn't happened yet"
    if (today - day).days > MAX_DAYS_BACK:
        return f"{day:%a %d %b} is more than {MAX_DAYS_BACK} days ago"
    return DateLine(day, rest)
