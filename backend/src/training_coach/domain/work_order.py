"""The order a session is done in, set by set (#97, ADR-0031). Pure logic, no I/O.

Two neighbouring items with the same pair number alternate: A1, B1, A2, B2, ... When one has
more sets it starts, so it ends the pair too and no exercise comes twice in a row; only a
difference of two or more sets leaves extra sets on their own at the end. An item without a
pair is done straight through. The result is grouped by pair, so a list can leave a gap
between groups.
"""

from collections.abc import Collection, Sequence
from itertools import pairwise, product

SetRef = tuple[int, int]  # (item index, set number from 1)

REPEAT = 3  # the same exercise twice running: what the order avoids first
SHARED = 1  # a main muscle again straight after, across a pair's edge or inside one
MOST_PAIRS = 10  # beyond this the order isn't searched (2 ** 10 tries); no session comes near


def _alternate(lead: int, follow: int, sets: Sequence[int]) -> list[SetRef]:
    rounds = max(sets[lead], sets[follow])
    return [(item, n) for n in range(1, rounds + 1) for item in (lead, follow) if n <= sets[item]]


def _cost(groups: list[list[SetRef]], primes: Sequence[frozenset[str]]) -> int:
    flat = [item for group in groups for item, _ in group]
    cost = 0
    for a, b in pairwise(flat):
        if a == b:
            cost += REPEAT
        elif primes and primes[a] & primes[b]:
            cost += SHARED
    return cost


def work_order(
    sets: Sequence[int],
    pairs: Sequence[int | None],
    first: Collection[int] = (),
    primes: Sequence[frozenset[str]] = (),
) -> list[list[SetRef]]:
    """Groups of (item index, set number) in the order they are done.

    ``sets[i]`` is how many sets item ``i`` has today and ``pairs[i]`` its pair number. A pair
    number that doesn't sit on exactly two neighbouring items is ignored (the seed refuses
    such plans; this keeps a bad row from hiding exercises).

    Each pair starts with whichever of its two exercises gives the fewest sets of the same
    exercise in a row and then the fewest of the same main muscles (``primes[i]``) in a row,
    across the whole session; on a tie, the plan's order. So a pair of 4 and 3 sets starts with
    the 4 (ADR-0031, addendum 2026-10-25). A pair number in ``first`` starts the other way
    round ("Do this one first", #117)."""
    if len(sets) != len(pairs):
        raise ValueError("sets and pairs must describe the same items")
    if primes and len(primes) != len(sets):
        raise ValueError("primes must describe the same items")
    units: list[tuple[int, ...]] = []
    i = 0
    while i < len(sets):
        partner = i + 1
        paired = (
            pairs[i] is not None
            and partner < len(sets)
            and pairs[partner] == pairs[i]
            and pairs.count(pairs[i]) == 2
        )
        units.append((i, partner) if paired else (i,))
        i += 2 if paired else 1

    def build(flips: Sequence[bool]) -> list[list[SetRef]]:
        turns = iter(flips)
        groups: list[list[SetRef]] = []
        for unit in units:
            if len(unit) == 2:
                lead, follow = unit[::-1] if next(turns) else unit
                groups.append(_alternate(lead, follow, sets))
            else:
                groups.append([(unit[0], n) for n in range(1, sets[unit[0]] + 1)])
        return [group for group in groups if group]

    paired_units = [unit for unit in units if len(unit) == 2]
    if len(paired_units) > MOST_PAIRS:
        best: tuple[bool, ...] = (False,) * len(paired_units)
    else:  # fewest repeats, then the fewest changes from the plan's order, earlier pairs first
        best = min(
            product((False, True), repeat=len(paired_units)),
            key=lambda flips: (_cost(build(flips), primes), sum(flips)),
        )
    swapped = [
        flip != (pairs[unit[0]] in first) for flip, unit in zip(best, paired_units, strict=True)
    ]
    return build(swapped)
