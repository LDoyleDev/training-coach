"""The walk-through's answers (ADR-0092). Pure logic, no I/O.

What a new person answers about themselves while their plan is made: their age band, how they
exercise now, four everyday questions, the weekdays they tap and their "can you do...?" answers.
They are kept only with ``walkthrough`` consent (ADR-0090), one set per person, replaced by a
re-run. Never the safety answers (they stay on the device, ADR-0085), the suggested level (it can
be worked out again from these), or the minutes, kit and places (settings hold those).
Every answer can be skipped, so each may be empty.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

WEEKDAYS = range(7)  # 0 is Monday, as date.weekday()


class AgeBand(StrEnum):
    UNDER_35 = "18-34"
    UNDER_50 = "35-49"
    UNDER_65 = "50-64"
    UNDER_75 = "65-74"
    OVER_75 = "75+"


class Often(StrEnum):
    """How often they exercise now."""

    NOT_NOW = "not_now"  # not at the moment
    UNDER_WEEKLY = "under_weekly"
    ONE_TWO = "one_two"  # 1-2 times a week
    THREE_PLUS = "three_plus"


class Effort(StrEnum):
    """How hard: able to talk in sentences, or sometimes out of breath."""

    TALK = "talk"
    BREATHLESS = "breathless"


class HowLong(StrEnum):
    UNDER_10 = "under_10"
    TEN_TO_30 = "10_30"
    OVER_30 = "over_30"


class CanDo(StrEnum):
    """An answer to one step's "Can you do...?" question."""

    YES = "yes"
    NO = "no"
    NOT_SURE = "not_sure"
    SKIP = "skip"


# Per exercise slug, the steps asked in order: (ladder step id, answer).
Placement = Mapping[str, Sequence[tuple[int, CanDo]]]


@dataclass(frozen=True)
class Answers:
    age_band: AgeBand | None = None
    often: Often | None = None
    effort: Effort | None = None
    how_long: HowLong | None = None
    # The everyday questions (B5.2): True yes, False no, None skipped.
    chair: bool | None = None  # stand up from a chair without your hands
    stairs: bool | None = None  # climb a flight of stairs without stopping
    walk: bool | None = None  # walk 10 minutes without stopping
    floor: bool | None = None  # get down to the floor and up again
    weekdays: tuple[int, ...] = ()
    placement: Placement = field(default_factory=dict)

    def __post_init__(self) -> None:
        if any(day not in WEEKDAYS for day in self.weekdays):
            raise ValueError("a weekday is 0 (Monday) to 6 (Sunday)")
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("a weekday tapped twice")


def placement_json(placement: Placement) -> dict[str, list[list[int | str]]]:
    """The placement as stored: ``{slug: [[step id, answer], ...]}``."""
    return {
        slug: [[step, answer.value] for step, answer in asked] for slug, asked in placement.items()
    }


def placement_from_json(stored: Mapping[str, Sequence[Sequence[int | str]]]) -> Placement:
    """The placement back from ``placement_json``."""
    return {
        slug: tuple((int(step), CanDo(str(answer))) for step, answer in asked)
        for slug, asked in stored.items()
    }


def placement_problem(placement: Placement, ladders: Mapping[str, Collection[int]]) -> str | None:
    """Why the placement answers can't be kept, or None: each names one of the walk-through's
    ladders (``ladders``: slug -> its step ids) and asks only its steps, at most once a step."""
    for slug, asked in placement.items():
        steps = ladders.get(slug)
        if steps is None:
            return f"{slug} isn't one of the walk-through's exercises"
        if len(asked) > len(steps) or not {step for step, _ in asked} <= set(steps):
            return f"{slug}: only the steps of its ladder, each asked once"
    return None


# ------------------------------------------------------------------- the starter and its start


def starter_days(tapped: int) -> int:
    """The days a week of the starter for ``tapped`` weekdays (ADR-0092, How the plan is made 3):
    1 or 2 the 2-day, 3 the 3-day, 4 or more the 4-day; none the 3-day, starting tomorrow."""
    if tapped == 0:
        return 3
    return min(max(tapped, 2), 4)


def landing(start: date, rest_after: Sequence[int]) -> tuple[date, ...]:
    """The day each of a starter's sessions lands on, the first on ``start`` and each next one
    after the rest places before it (ADR-0091). A starter is a week, so the pattern repeats."""
    days, day = [], start
    for rest in rest_after:
        days.append(day)
        day += timedelta(days=1 + rest)
    return tuple(days)


@dataclass(frozen=True)
class Start:
    on: date
    missed: tuple[int, ...]  # tapped weekdays no session lands on, Monday first


def start_day(today: date, weekdays: Collection[int], rest_after: Sequence[int]) -> Start:
    """The day the plan starts (ADR-0092, How the plan is made 8): of the next week's tapped
    days, today included, the first from which the starter's rest places land the most sessions
    on tapped days; with the tapped days no session lands on. None tapped: tomorrow."""
    if not weekdays:
        return Start(today + timedelta(days=1), ())
    tapped = set(weekdays)
    week = (today + timedelta(days=k) for k in range(7))
    candidates = [day for day in week if day.weekday() in tapped]

    def hits(start: date) -> int:
        return sum(day.weekday() in tapped for day in landing(start, rest_after))

    best = max(candidates, key=hits)  # the earliest of equals
    landed = {day.weekday() for day in landing(best, rest_after)}
    return Start(best, tuple(sorted(tapped - landed)))
