"""Choosing a stretching routine after a resistance session (#98, ADR-0032). Pure logic.

Static stretches held about 30 s at a gentle effort, a few rounds each (Huberman Lab, the
flexibility episode). The routine fills the chosen time without going over, in three steps:
1. two rounds of a stretch for each muscle the session worked, most-worked first;
2. a third round of those, in the same order;
3. two rounds of stretches for the rest of the body.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

HOLD_SECONDS = 30
SWITCH_SECONDS = 10  # getting into position, or changing sides
ROUNDS = 2
MAX_ROUNDS = 3
CHOICES = (10, 20, 30)  # minutes offered


@dataclass(frozen=True)
class Stretch:
    slug: str
    name: str
    muscles: frozenset[str]
    per_side: bool
    cue: str


@dataclass(frozen=True)
class Step:
    stretch: Stretch
    rounds: int

    @property
    def seconds(self) -> int:
        return seconds(self.stretch, self.rounds)


def seconds(stretch: Stretch, rounds: int) -> int:
    """Time for ``rounds`` holds of ``stretch``, on each side when it's one-sided."""
    sides = 2 if stretch.per_side else 1
    return rounds * sides * (HOLD_SECONDS + SWITCH_SECONDS)


def routine(catalogue: Sequence[Stretch], worked: Mapping[str, int], minutes: int) -> list[Step]:
    """The stretches to do in ``minutes``, in order. ``worked`` is sets per muscle group in the
    session; the most-worked muscles come first, each stretch at most once."""
    budget = minutes * 60
    rounds: dict[Stretch, int] = {}
    covered: set[str] = set()

    def pick(useful: bool) -> None:
        """Add two rounds of the best stretch that still fits, until none does. ``useful``:
        only stretches for worked muscles not yet covered; otherwise any new muscle."""
        nonlocal budget
        while True:
            options = [
                s
                for s in catalogue
                if s not in rounds
                and seconds(s, ROUNDS) <= budget
                and (_new_work(s, worked, covered) > 0 if useful else s.muscles - covered)
            ]
            if not options:
                return
            best = max(
                options,
                key=lambda s: (
                    _new_work(s, worked, covered),
                    len(s.muscles - covered),
                    -catalogue.index(s),
                ),
            )
            rounds[best] = ROUNDS
            budget -= seconds(best, ROUNDS)
            covered.update(best.muscles)

    pick(useful=True)
    for stretch in list(rounds):  # a third round for the session's muscles, if it fits
        extra = seconds(stretch, MAX_ROUNDS) - seconds(stretch, ROUNDS)
        if extra <= budget:
            rounds[stretch] = MAX_ROUNDS
            budget -= extra
    pick(useful=False)
    return [Step(stretch, n) for stretch, n in rounds.items()]


def _new_work(stretch: Stretch, worked: Mapping[str, int], covered: set[str]) -> int:
    """Sets the session did for muscles this stretch would cover for the first time."""
    return sum(worked.get(m, 0) for m in stretch.muscles - covered)
