"""Weekly training volume per muscle group (docs/specs/training-plan.md). Pure logic, no I/O.

Every planned set counts once for each muscle group its exercise lists, primary or secondary
(pull-ups count for lats, upper back and biceps), so totals are an upper estimate of Galpin's
direct-set count.
"""

from collections.abc import Iterable, Sequence

# Tags in the plan that describe a quality, not a muscle.
NON_MUSCLE_TAGS = frozenset({"conditioning", "mobility", "power", "posture"})

# Galpin: 10-20 hard sets per muscle group per week.
TARGET_MIN_SETS = 10
TARGET_MAX_SETS = 20


def weekly_sets(items: Iterable[tuple[Sequence[str], int]]) -> list[tuple[str, int]]:
    """``(muscle groups, sets)`` per planned item -> ``(group, total sets)``, largest first.

    Ties are ordered by name so the result is stable.
    """
    totals: dict[str, int] = {}
    for groups, sets in items:
        if sets < 0:
            raise ValueError("sets must be >= 0")
        for group in groups:
            if group in NON_MUSCLE_TAGS:
                continue
            totals[group] = totals.get(group, 0) + sets
    return sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
