"""Weekly training volume per muscle (docs/specs/training-plan.md). Pure logic, no I/O.

Sets are counted fractionally (ADR-0064): a set counts the weight its exercise gives each
muscle, 1 for a prime mover, 0.5 for a synergist and 0.25 for a small part (pull-ups: 1 for
lats, 0.5 for biceps and upper back). This fitted growth better than counting every muscle
fully (Pelland 2026), so totals are lower than a count of every listed muscle.
"""

from collections.abc import Iterable, Mapping

# Galpin: 10-20 hard sets per muscle group per week.
TARGET_MIN_SETS = 10
TARGET_MAX_SETS = 20


def weekly_sets[M: str](items: Iterable[tuple[Mapping[M, float], int]]) -> list[tuple[M, float]]:
    """``(muscle weights, sets)`` per planned or logged item -> ``(muscle, fractional sets)``,
    largest first. Ties are ordered by name so the result is stable.
    """
    totals: dict[M, float] = {}
    for muscles, sets in items:
        if sets < 0:
            raise ValueError("sets must be >= 0")
        for muscle, weight in muscles.items():
            totals[muscle] = totals.get(muscle, 0) + weight * sets
    return sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))


def shown(sets: float) -> str:
    """Fractional sets as people read them: ``7.5``, ``10``, ``6.25``."""
    return f"{sets:g}"
