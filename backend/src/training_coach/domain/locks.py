"""Why a ladder step is locked for one person (ADR-0071, ADR-0083). Pure logic, no I/O.

A step locks when it needs kit the person hasn't listed (ADR-0071), or asks something of the
body they've chosen to avoid: one of its marks under "Keep me off the floor", "No kneeling", "No
jumping or running" or "No hanging" (ADR-0083). Either way it locks the same way: Move up skips
it to the next open step, it shows locked with the reason in words, and it can still be chosen
by hand, with a warning. The person decides; nothing asks why.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from training_coach.domain import kit as kit_rules
from training_coach.domain.kit import Item
from training_coach.domain.step_levels import Mark

# The marks a person can choose to avoid, in the order Account shows them. Balance marks a fall
# risk and has no switch: its cue names something to hold.
AVOIDABLE = (Mark.FLOOR, Mark.KNEELING, Mark.IMPACT, Mark.HANGING)

# What a step with the mark needs, then the person's choice, in words.
AVOIDED = {
    Mark.FLOOR: "needs the floor — you've chosen to keep off it",
    Mark.KNEELING: "needs kneeling — you've chosen not to kneel",
    Mark.IMPACT: "needs jumping or running — you've chosen not to jump or run",
    Mark.HANGING: "needs hanging from a bar — you've chosen not to hang",
}


@dataclass(frozen=True)
class Asks:
    """What one ladder step asks for: the kit it needs (the catalogue's) and its marks."""

    needs: Sequence[str] = ()
    marks: Sequence[Mark] = ()


@dataclass(frozen=True)
class Limits:
    """What locks steps for one person: their home kit (None: not listed yet, so kit locks
    nothing) and the marks they've chosen to avoid."""

    kit: Sequence[Item] | None = None
    avoid: frozenset[Mark] = frozenset()


@dataclass(frozen=True)
class Lock:
    """Why a step is locked, in words; open when both are empty."""

    missing: tuple[str, ...] = ()  # the kit it needs that isn't listed: "a 16 kg kettlebell"
    avoided: tuple[str, ...] = ()  # what it asks that the person avoids, as ``AVOIDED`` says

    @property
    def open(self) -> bool:
        return not self.missing and not self.avoided

    def reasons(self) -> list[str]:
        """Each reason as a phrase after the step's name: "needs ..., not in your kit"."""
        kit = [f"needs {' and '.join(self.missing)}, not in your kit"] if self.missing else []
        return [*kit, *self.avoided]


def lock(asks: Asks, limits: Limits) -> Lock:
    """Why ``asks``'s step is locked for this person; open when nothing locks it."""
    return Lock(
        tuple(kit_rules.missing(limits.kit, asks.needs)),
        tuple(AVOIDED[m] for m in AVOIDABLE if m in asks.marks and m in limits.avoid),
    )


def warning(step: str, found: Lock) -> str | None:
    """A locked step chosen by hand, in words: "Standard needs the floor — you've chosen to keep
    off it." None when it is open. Chosen anyway: the person decides."""
    return None if found.open else f"{step} {'; '.join(found.reasons())}."


def next_open(ladder: Sequence[Asks], at: int, limits: Limits) -> int | None:
    """The first step after ``at`` that isn't locked (Move up skips locked ones), or None.
    ``ladder`` is what each step asks, easiest first."""
    return next((i for i in range(at + 1, len(ladder)) if lock(ladder[i], limits).open), None)


def previous_open(ladder: Sequence[Asks], at: int, limits: Limits) -> int | None:
    """The nearest step before ``at`` that isn't locked (a step down skips locked ones,
    ADR-0084), or None at the first step, or when every step below is locked."""
    return next((i for i in range(at - 1, -1, -1) if lock(ladder[i], limits).open), None)


def unlocks_next(ladder: Sequence[Asks], at: int, limits: Limits) -> tuple[int, list[str]] | None:
    """At the top of the open steps (harder steps exist, none of them open): the first harder
    step that only kit locks, and the kit it lacks. No kit opens a step the person avoids, so
    those are passed over. None when a harder open step exists, the ladder ends here, or every
    harder step is one they avoid."""
    if next_open(ladder, at, limits) is not None:
        return None
    for i in range(at + 1, len(ladder)):
        found = lock(ladder[i], limits)
        if not found.avoided:
            return i, list(found.missing)
    return None
