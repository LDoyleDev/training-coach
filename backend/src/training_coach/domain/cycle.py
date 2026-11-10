"""The person's own cycle, edited as a draft (ADR-0093). Pure logic, no I/O.

A cycle is its sessions in queue order, each with the rest places after it (ADR-0091). A draft
is the cycle as it should be: a saved session by its id, a new one by the draft's own key
("n1") until Save gives it an id. The editor builds the draft a tap at a time (``add``,
``remove``, ``move``, ``with_rest``), each step a suggestion the person can change; Save checks
it (``problem``) and works out the queue after it (``applied``). The web's copy in
``plan/cycleLogic.ts`` reads the same cases (``frontend/src/plan/cycle-cases.json``).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from training_coach.domain.queue import Position

Key = int | str  # a saved session's id, or a new session's key in the draft

MAX_SESSIONS = 10  # Decided 13
MAX_DAYS = 14  # Decided 13: the cycle's days, its rest places included
MAX_REST = 6  # rest places after one session, as session_templates' check


@dataclass(frozen=True)
class Slot:
    """One session of the cycle and the rest places after it."""

    key: Key
    rest_after: int = 0


Cycle = tuple[Slot, ...]


def days(cycle: Sequence[Slot]) -> int:
    """How many days the cycle takes: a day per session and one per rest place."""
    return len(cycle) + sum(s.rest_after for s in cycle)


def suggested_after(cycle: Sequence[Slot]) -> Key:
    """Where a new session goes (Decided 1): after the session with the most rest days after
    it, the later one on a tie, so the last session when none has any."""
    if not cycle:
        raise ValueError("the cycle has no sessions")
    most = max(s.rest_after for s in cycle)
    return next(s.key for s in reversed(cycle) if s.rest_after == most)


def split(rest_after: int) -> tuple[int, int]:
    """The rest places either side of a new session added after one with ``rest_after``
    (Decided 1). With 1 or more it takes one of them, and of the rest the session before keeps
    the larger half, so the cycle keeps its length: 1 gives both 0, 3 gives both 1. With 0 (the
    owner's sessions) both get 0 and the cycle is a day longer."""
    if rest_after < 1:
        return 0, 0
    left = rest_after - 1
    return left - left // 2, left // 2


def add(cycle: Sequence[Slot], key: str, after: Key | None = None) -> Cycle:
    """The cycle with a new session after ``after`` (the suggestion when None), the rest places
    after that session split around it."""
    at = _index(cycle, suggested_after(cycle) if after is None else after)
    before, new = split(cycle[at].rest_after)
    return (
        *cycle[:at],
        replace(cycle[at], rest_after=before),
        Slot(key, new),
        *cycle[at + 1 :],
    )


def remove(cycle: Sequence[Slot], key: Key) -> Cycle:
    """The cycle without ``key`` (Decided 6): its day and rest places go to the session before
    it, the last one if it was first, so the cycle keeps its length up to MAX_REST."""
    at = _index(cycle, key)
    rest = [s for s in cycle if s.key != key]
    if not rest:
        return ()
    before = (at - 1) % len(rest)  # the session before it, wrapping to the last
    gets = min(MAX_REST, rest[before].rest_after + 1 + cycle[at].rest_after)
    rest[before] = replace(rest[before], rest_after=gets)
    return tuple(rest)


def move(cycle: Sequence[Slot], key: Key, by: int) -> Cycle:
    """The cycle with ``key`` moved ``by`` places (-1 Up, +1 Down, Decided 8), its rest places
    with it; held at either end."""
    at = _index(cycle, key)
    to = min(max(at + by, 0), len(cycle) - 1)
    rest = [s for s in cycle if s.key != key]
    rest.insert(to, cycle[at])
    return tuple(rest)


def with_rest(cycle: Sequence[Slot], key: Key, rest_after: int) -> Cycle:
    """The cycle with ``rest_after`` rest places after ``key``."""
    at = _index(cycle, key)
    return (*cycle[:at], replace(cycle[at], rest_after=rest_after), *cycle[at + 1 :])


def problem(cycle: Sequence[Slot]) -> str | None:
    """Why the cycle can't be saved (Decided 13), in words; None when it can."""
    keys = [s.key for s in cycle]
    if not cycle:
        return "Your cycle needs at least one session."
    if len(set(keys)) < len(keys):
        return "A session can be in your cycle only once."
    if len(cycle) > MAX_SESSIONS:
        return f"A cycle can have at most {MAX_SESSIONS} sessions."
    if any(not 0 <= s.rest_after <= MAX_REST for s in cycle):
        return f"Rest days after a session can be 0 to {MAX_REST}."
    if days(cycle) > MAX_DAYS:
        return f"Your cycle would be {days(cycle)} days; it can be at most {MAX_DAYS}."
    return None


def cannot_add(cycle: Sequence[Slot]) -> str | None:
    """Why Add is greyed (Decided 13), in words; None when a session can be added. Only the
    count can stop it: at the suggested place a new session takes a rest place when there is
    one, and a cycle with none is a day per session, at most MAX_SESSIONS."""
    if len(cycle) >= MAX_SESSIONS:
        return f"You have {MAX_SESSIONS} sessions, the most a cycle can have."
    return None


@dataclass(frozen=True)
class Applied:
    """A draft as Save writes it: the sessions in their new order (a position each), and the
    queue after it (Decided 9)."""

    cycle: Cycle
    pointer: Key  # the session the queue offers next; a new one's key until Save gives it an id
    queued: tuple[int, ...]  # a swap's sessions still to come before the cycle resumes
    added: tuple[str, ...]  # new sessions, in cycle order
    removed: tuple[int, ...]  # saved sessions not in the draft, in the old order
    moved: tuple[int, ...]  # saved sessions moved: the fewest that explain the new order
    last_rest: int | None  # the rest places after the session done last; None: none done
    changed: bool  # anything differs: a session added, removed or moved, or a rest place

    @property
    def days(self) -> int:
        return days(self.cycle)

    @property
    def positions(self) -> dict[Key, int]:
        return {s.key: i for i, s in enumerate(self.cycle)}


def applied(
    before: Sequence[Slot], draft: Sequence[Slot], position: Position, last_done: int | None
) -> Applied:
    """``draft`` in place of the saved cycle ``before``, with the queue at ``position`` and
    ``last_done`` the planned session done or rested last (ADR-0091), if any.

    The pointer stays on its session (Decided 8 and 9) except in two cases. Its session is
    removed: it moves to the next session left, the swap's first if one is queued, else the next
    after it in the old order. A new session is added straight after the one done last, where
    the queue stands: the new session is next, or it would wait a whole cycle. ``queued`` drops
    removed sessions."""
    reason = problem(draft)
    if reason is not None:
        raise ValueError(reason)
    old = [s.key for s in before]
    new = [s.key for s in draft]
    unknown = [k for k in new if isinstance(k, int) and k not in old]
    if unknown:
        raise ValueError(f"session {unknown[0]} is not in the plan")
    kept = [k for k in new if isinstance(k, int)]
    queued = tuple(k for k in position.queued if k in kept)
    pointer = _pointer(old, new, position.pointer, queued, last_done)
    if queued and pointer == queued[0] and position.pointer not in new:
        queued = queued[1:]  # the swap's first took the removed session's place
    rests = {s.key: s.rest_after for s in [*before, *draft]}  # the draft's where it has one
    return Applied(
        cycle=tuple(draft),
        pointer=pointer,
        queued=queued,
        added=tuple(k for k in new if isinstance(k, str)),
        removed=tuple(k for k in old if isinstance(k, int) and k not in new),
        moved=_moved([k for k in old if k in kept], kept),
        last_rest=None if last_done is None else rests.get(last_done),
        changed=tuple(before) != tuple(draft),
    )


def _pointer(
    old: Sequence[Key], new: Sequence[Key], pointer: int, queued: Sequence[int], last: int | None
) -> Key:
    if last in new and last in old and pointer == old[(old.index(last) + 1) % len(old)]:
        after = new[(new.index(last) + 1) % len(new)]
        if isinstance(after, str):
            return after
    if pointer in new:
        return pointer
    if queued:
        return queued[0]
    if pointer in old:
        at = old.index(pointer)
        for k in [*old[at + 1 :], *old[:at]]:
            if k in new:
                return k
    return new[0]


def _moved(old: Sequence[int], new: Sequence[int]) -> tuple[int, ...]:
    """The sessions off a longest run kept in the old order: the fewest moves that turn ``old``
    into ``new`` (both the same sessions). On a tie the later-placed session is the one that
    stayed, so A B C to B A C reads as B moved up."""
    ranks = [old.index(k) for k in new]
    none: list[int] = []
    best: list[list[int]] = []  # best[i]: a longest increasing run of ranks ending at i
    for i, rank in enumerate(ranks):
        runs = [best[j] for j in reversed(range(i)) if ranks[j] < rank]
        best.append([*max(runs, key=len, default=none), i])
    stayed = none
    for run in reversed(best):  # the longest, the one ending latest on a tie
        if len(run) > len(stayed):
            stayed = run
    return tuple(k for i, k in enumerate(new) if i not in stayed)


def _index(cycle: Sequence[Slot], key: Key) -> int:
    for i, s in enumerate(cycle):
        if s.key == key:
            return i
    raise ValueError(f"session {key!r} is not in the cycle")
