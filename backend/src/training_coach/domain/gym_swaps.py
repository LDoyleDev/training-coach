"""The starters' gym versions (any-level-any-time.md S1, Decided 2 and 5): which home exercise
is done as which gym exercise, from the step the person is placed on. Pure rules."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Swap:
    exercise: str  # the home exercise's slug
    at: int  # the ladder position from which it is done as ``gym``
    gym: str  # the gym exercise's slug
    rep_min: int
    rep_max: int
    # Only in these sessions; empty: in every session no other swap of the exercise names
    sessions: frozenset[str] = frozenset()


def swap_for(swaps: Sequence[Swap], session: str, exercise: str, placed: int) -> Swap | None:
    """The gym exercise for one item of ``session``, the person being on step ``placed`` of its
    ladder: the swap naming the session, else the exercise's own; None below its step, where the
    home exercise stays (a machine or a barbell lift would be too much on day one)."""
    mine = [s for s in swaps if s.exercise == exercise]
    found = next((s for s in mine if session in s.sessions), None) or next(
        (s for s in mine if not s.sessions), None
    )
    if found is None or placed < found.at:
        return None
    return found
