"""Personal bests per exercise and ladder step (ADR-0025). Pure logic, no I/O.

A session's values are its per-set values from ``progression.combine_sides`` (the weaker side
for unilateral work, a missing set as 0). Two records are kept: the best single set and the
best session total. A record is only new when it beats every earlier session at the same step,
so the first session at a step (or after moving up) is never announced as a best.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class NewBests:
    best_set: int | None = None  # the new record, or None if not beaten
    total: int | None = None

    def __bool__(self) -> bool:
        return self.best_set is not None or self.total is not None


def new_bests(current: Sequence[int], earlier: Iterable[Sequence[int]]) -> NewBests:
    """Which records ``current`` sets, compared with every ``earlier`` session at the step."""
    previous = [list(values) for values in earlier]
    if not previous:
        return NewBests()
    best_set = max(current, default=0)
    total = sum(current)
    return NewBests(
        best_set=best_set if best_set > max(max(v, default=0) for v in previous) else None,
        total=total if total > max(sum(v) for v in previous) else None,
    )
