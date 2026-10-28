"""Load on a set (ADR-0072): the kit a loaded step uses, its increment, and the weight each set
starts at on the set screen. Pure logic, no I/O.

A step takes load when the catalogue says so (``plan.toml``, ``[exercises.loads]``): one step,
and the weight goes up. Each set records its weight in kilograms; empty for bodyweight.

The set screen starts at the weight of the same set last time (the carry-over), with - and +
in the kit's increment (the person's own, or the default), so nothing is typed. With no
history it starts at the kit's first weight, which the person changes to theirs.

Double progression: reps go up within the range (ADR-0027) at one weight. When every planned
set of the last session at that weight reached the top of the range, the next weight up is
suggested, with reps starting again at the bottom; a missed target holds. The person decides:
a suggestion is a tap on the set screen, never a change made for them.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from training_coach.domain.progression import session_met_top
from training_coach.domain.targets import Prescription

MAX_KG = 500.0  # a bound for a typed or kept value, far above anyone's lift


class LoadKit(StrEnum):
    """What carries the weight on a loaded step: its increment and first weight follow."""

    BARBELL = "barbell"
    DUMBBELLS = "dumbbells"  # the weight of one, per hand
    MACHINE = "machine"  # a machine's or a cable's stack


# The smallest step up or down by default (program-builder.md, Decided 6); each person can
# set their own (``Increments``).
INCREMENT: dict[LoadKit, float] = {
    LoadKit.BARBELL: 2.5,
    LoadKit.DUMBBELLS: 2.0,
    LoadKit.MACHINE: 5.0,
}
INCREMENT_KG = (0.25, 20.0)  # a person's own: from a pair of small plates to a big jump


@dataclass(frozen=True)
class Increments:
    """A person's own smallest step for each kit; None keeps the default."""

    barbell: float | None = None
    dumbbells: float | None = None
    machine: float | None = None

    def of(self, kit: LoadKit) -> float:
        """The step - and + move by and the next weight adds, for ``kit``."""
        own = {
            LoadKit.BARBELL: self.barbell,
            LoadKit.DUMBBELLS: self.dumbbells,
            LoadKit.MACHINE: self.machine,
        }[kit]
        return INCREMENT[kit] if own is None else own


DEFAULTS = Increments()


def valid_increment(kg: float) -> bool:
    """A step a person can set: within the bounds, in quarters of a kilogram."""
    return INCREMENT_KG[0] <= kg <= INCREMENT_KG[1] and (kg * 4).is_integer()


# Where a first set starts: the empty bar, a light pair, a light stack. A starting point for
# - and +, never a suggestion of what to lift.
FIRST_KG: dict[LoadKit, float] = {
    LoadKit.BARBELL: 20.0,
    LoadKit.DUMBBELLS: 8.0,
    LoadKit.MACHINE: 20.0,
}


@dataclass(frozen=True)
class NextWeight:
    """The weight suggested next, and the targets it starts from: the bottom of the range."""

    kg: float
    targets: tuple[int, ...]


@dataclass(frozen=True)
class Load:
    """A loaded item in a session: its kit, the increment - and + move by, and the weight each
    set starts at. ``carried`` is False when nothing was logged at this step yet."""

    kit: LoadKit
    increment: float
    kg: tuple[float, ...]  # one per planned set
    carried: bool
    suggested: NextWeight | None = None  # every set reached the top last time (double progression)


def carried(
    kit: LoadKit,
    sets: int,
    last: Sequence[tuple[int, float]],
    increments: Increments = DEFAULTS,
) -> Load:
    """Each planned set's starting weight from ``last``, the (set number, kg) pairs of the
    last session at this step: the same set's weight, else that of the nearest set before it,
    else the first set's. With no history, every set starts at the kit's first weight. - and +
    move by the person's own increment for the kit."""
    step = increments.of(kit)
    by_set = dict(last)
    if not by_set:
        return Load(kit, step, (FIRST_KG[kit],) * sets, carried=False)
    first = by_set[min(by_set)]
    kg: list[float] = []
    for number in range(1, sets + 1):
        before = [n for n in by_set if n <= number]
        kg.append(by_set[max(before)] if before else first)
    return Load(kit, step, tuple(kg), carried=True)


def top_weight(last: Sequence[tuple[int, float]]) -> float | None:
    """A session's weight, for its targets and bests: the heaviest set's. None with none."""
    return max((kg for _, kg in last), default=None)


def next_weight(
    item: Prescription,
    last: Sequence[int] | None,
    loads: Sequence[tuple[int, float]],
    increment: float,
) -> NextWeight | None:
    """The next weight up when the last session, ``last`` its values and ``loads`` its (set
    number, kg), did every planned set at one weight and every one reached the top of the
    range; None otherwise, or past the bound. A pyramid (one heavy set, the rest lighter) is
    not a session at the heavy weight, so it suggests nothing."""
    kg = top_weight(loads)
    by_set = dict(loads)
    at_weight = all(by_set.get(n) == kg for n in range(1, item.sets + 1))
    if kg is None or last is None or not at_weight or not session_met_top(item, last):
        return None
    if not valid_kg(kg + increment):
        return None
    return NextWeight(round(kg + increment, 2), (item.rep_min,) * item.sets)


def valid_kg(kg: float) -> bool:
    """A weight a set can record: above nothing, within the bound."""
    return 0 < kg <= MAX_KG


def kg_text(kg: float) -> str:
    """``20.0`` -> ``"20"``, ``22.5`` -> ``"22.5"``: as a person writes it."""
    return f"{kg:g}"


NO_WEIGHT = chr(0x2013)  # an en dash, for a set without a weight among sets with one


def weights_text(weights: Sequence[float | None]) -> str:
    """What follows a line's sets, one weight per set in set order: " at 16 kg" for one
    weight, " at 16 / 18 kg" when they differ (``NO_WEIGHT`` for a set without one), and
    nothing when none has a weight. As the confirm step, the day's log and the AI's summary
    write it."""
    first = weights[0] if weights else None
    if all(kg is None for kg in weights):
        return ""
    if first is not None and all(kg == first for kg in weights):
        return f" at {kg_text(first)} kg"
    shown = " / ".join(kg_text(kg) if kg is not None else NO_WEIGHT for kg in weights)
    return f" at {shown} kg"
