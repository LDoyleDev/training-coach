"""How long to rest after each set of a session (ADR-0065). Pure logic, no I/O.

Inside a pair, the move to the other exercise is the rest: 15 s. After both exercises of a
round, 60 s, or 90 s when the two share a prime mover: a muscle one counts fully for and the
other at least half (pistol squat + single-leg RDL, both glutes); same-muscle pairs lose volume
(Zhang 2025). A set done on its own, an unpaired exercise or a pair's extra set, rests by what
it is: 90 s for a compound (short rest costs most on multi-joint sets), 60 s for a small
muscle. The last set rests 0: the session is over. Evidence:
docs/specs/program-builder-research.md, Time efficiency.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from training_coach.domain.muscles import Muscle, Pattern
from training_coach.domain.work_order import SetRef

SWITCH_SECONDS = 15
AFTER_PAIR_SECONDS = 60
SHARED_PAIR_SECONDS = 90
COMPOUND_SECONDS = 90
SMALL_SECONDS = 60

# The catalogue keeps the neck as one muscle, though flexion, extension and side bends work
# opposite sides of it: a neck pair is an opposing pair, not a shared one.
ONE_FOR_ALL_DIRECTIONS = frozenset({Muscle.NECK})

COMPOUNDS = frozenset(
    {
        Pattern.SQUAT,
        Pattern.HINGE,
        Pattern.LUNGE,
        Pattern.HORIZONTAL_PUSH,
        Pattern.VERTICAL_PUSH,
        Pattern.HORIZONTAL_PULL,
        Pattern.VERTICAL_PULL,
        Pattern.CARRY,
    }
)


@dataclass(frozen=True)
class Kind:
    """What the rest rules need to know about an exercise."""

    pattern: Pattern
    primes: frozenset[Muscle]  # the muscles it counts 1 for
    involved: frozenset[Muscle] = frozenset()  # the muscles it counts 0.5 or more for


@dataclass(frozen=True)
class Rest:
    seconds: int
    switch: bool = False  # the move to the other exercise of a pair, not a rest


def straight(kind: Kind | None) -> int:
    """The rest after a set done on its own; an exercise the catalogue doesn't know is small."""
    return COMPOUND_SECONDS if kind is not None and kind.pattern in COMPOUNDS else SMALL_SECONDS


def shares_prime_mover(a: Kind, b: Kind) -> bool:
    shared = (a.primes & (b.involved | b.primes)) | (b.primes & (a.involved | a.primes))
    return bool(shared - ONE_FOR_ALL_DIRECTIONS)


def after_pair(a: Kind | None, b: Kind | None) -> int:
    shared = a is not None and b is not None and shares_prime_mover(a, b)
    return SHARED_PAIR_SECONDS if shared else AFTER_PAIR_SECONDS


def rests(groups: Sequence[Sequence[SetRef]], kinds: Sequence[Kind | None]) -> list[Rest]:
    """The rest after each set, in the order ``groups`` lists them (``work_order``'s result).

    ``kinds[i]`` describes item ``i``. A group with two items is a pair, done in rounds by set
    number: the first set of a round switches to the second; the round's last set rests by the
    pair. A round with one set left (the longer exercise's extra sets) rests as a straight set.
    """
    out: list[Rest] = []
    for group in groups:
        items = list(dict.fromkeys(item for item, _ in group))
        for i, (item, set_no) in enumerate(group):
            following = group[i + 1] if i + 1 < len(group) else None
            if following is not None and following[1] == set_no and following[0] != item:
                out.append(Rest(SWITCH_SECONDS, switch=True))
                continue
            in_round = sum(1 for _, n in group if n == set_no)
            if len(items) == 2 and in_round == 2:
                out.append(Rest(after_pair(kinds[items[0]], kinds[items[1]])))
            else:
                out.append(Rest(straight(kinds[item])))
    if out:
        out[-1] = Rest(0)
    return out
