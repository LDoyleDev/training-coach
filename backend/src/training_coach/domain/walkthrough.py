"""The walk-through's answers (ADR-0092). Pure logic, no I/O.

What a new person answers about themselves while their plan is made: their age band, how they
exercise now, four everyday questions, the weekdays they tap and their "can you do...?" answers.
They are kept only with ``walkthrough`` consent (ADR-0090), one set per person, replaced by a
re-run. Never the safety answers (they stay on the device, ADR-0085), the suggested level (it can
be worked out again from these), or the minutes, kit and places (settings hold those).
Every answer can be skipped, so each may be empty.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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
