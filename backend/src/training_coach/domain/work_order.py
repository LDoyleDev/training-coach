"""The order a session is done in, set by set (#97, ADR-0031). Pure logic, no I/O.

Two neighbouring items with the same pair number alternate: A1, B1, A2, B2, ... When one has
more sets, its extra sets follow on their own. An item without a pair is done straight
through. The result is grouped by pair, so a list can leave a gap between groups.
"""

from collections.abc import Collection, Sequence

SetRef = tuple[int, int]  # (item index, set number from 1)


def work_order(
    sets: Sequence[int], pairs: Sequence[int | None], first: Collection[int] = ()
) -> list[list[SetRef]]:
    """Groups of (item index, set number) in the order they are done.

    ``sets[i]`` is how many sets item ``i`` has today and ``pairs[i]`` its pair number. A pair
    number that doesn't sit on exactly two neighbouring items is ignored (the seed refuses
    such plans; this keeps a bad row from hiding exercises). A pair number in ``first`` starts
    with its second item ("Do this one first", #117)."""
    if len(sets) != len(pairs):
        raise ValueError("sets and pairs must describe the same items")
    groups: list[list[SetRef]] = []
    i = 0
    while i < len(sets):
        partner = i + 1
        paired = (
            pairs[i] is not None
            and partner < len(sets)
            and pairs[partner] == pairs[i]
            and pairs.count(pairs[i]) == 2
        )
        if paired:
            rounds = max(sets[i], sets[partner])
            both = (partner, i) if pairs[i] in first else (i, partner)
            groups.append(
                [(item, n) for n in range(1, rounds + 1) for item in both if n <= sets[item]]
            )
            i += 2
        else:
            groups.append([(i, n) for n in range(1, sets[i] + 1)])
            i += 1
    return [group for group in groups if group]
