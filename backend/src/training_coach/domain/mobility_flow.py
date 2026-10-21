"""The guided mobility flow on the Recovery day (ADR-0062). Pure logic.

Eight movements, standing to lying, timed one screen at a time: mostly slow controlled reps with
short end-range holds, which loosen without the strength dip of long static holds. A one-sided
movement's time is per side.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Move:
    slug: str  # also names its picture
    name: str
    seconds: int  # per side when ``per_side``
    per_side: bool
    target: str
    start: str  # the starting position, in a sentence
    end: str  # the end position
    cues: tuple[str, ...]
    breathing: str
    easier: str
    pacing: str

    @property
    def total(self) -> int:
        return self.seconds * (2 if self.per_side else 1)


@dataclass(frozen=True)
class Flow:
    exercise: str  # the plan's exercise it is logged as
    safety: str
    moves: tuple[Move, ...]

    @property
    def seconds(self) -> int:
        return sum(m.total for m in self.moves)
