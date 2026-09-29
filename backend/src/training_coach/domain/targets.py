"""Per-set targets for the next session of an exercise. Pure logic, no I/O.

Rule (product spec): start from the last session at the same ladder step. If every set was
equal, aim one more on every set. Otherwise aim one more on every set below the best set, so
the weaker sets catch up. Never above the top of the range. Below the bottom of the range the
targets still grow one rep at a time (no jump to the minimum). With no history, aim for the
bottom of the range.

Example: last 8/7/6/5 in a 5-12 range -> 8/8/7/6.
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Prescription:
    """What the plan asks for one exercise in a session."""

    sets: int
    rep_min: int
    rep_max: int

    def __post_init__(self) -> None:
        if self.sets < 1 or self.rep_min < 1 or self.rep_max < self.rep_min:
            raise ValueError(f"invalid prescription: {self}")


def _cap(value: int, item: Prescription) -> int:
    return max(0, min(item.rep_max, value))


def targets(item: Prescription, last: Sequence[int] | None) -> tuple[int, ...]:
    """Target value per planned set. ``last`` is the previous session's values, in set order."""
    if not last:
        return (item.rep_min,) * item.sets

    values = [_cap(v, item) for v in last[: item.sets]]
    # Fewer sets logged last time than planned: missing sets start from the weakest logged set.
    values += [min(values)] * (item.sets - len(values))

    best = max(values)
    if all(v == best for v in values):
        return tuple(_cap(v + 1, item) for v in values)
    return tuple(v if v == best else min(best, v + 1) for v in values)
