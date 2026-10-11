"""What a connected AI may read (ADR-0047 C, docs/security/mcp-threat-model.md).

C1 is read-only: training, and two health scopes that start unticked on the consent page, so
each connection opts in to them. ``log:propose`` comes with C2.
"""

from collections.abc import Iterable
from enum import StrEnum


class Scope(StrEnum):
    TRAINING = "training:read"
    BODY = "body:read"
    READINESS = "readiness:read"


HEALTH = frozenset({Scope.BODY, Scope.READINESS})

# In plain words, for the consent page and the Account page.
LABELS = {
    Scope.TRAINING: "Your plan, workouts, sets, test days, habits and progress",
    Scope.BODY: "Your body measurements (health data)",
    Scope.READINESS: "Your readiness answers and daily checks (health data)",
}


def parse(text: str | None) -> list[Scope] | None:
    """The scopes in a space-separated ``scope`` parameter, in a fixed order; every scope when
    it is missing or empty; None if any is unknown (refused, never ignored)."""
    words = set((text or "").split())
    if not words:
        return list(Scope)
    if not words <= {s.value for s in Scope}:
        return None
    return [s for s in Scope if s.value in words]


def grant(requested: Iterable[str], ticked: Iterable[str]) -> list[Scope]:
    """What a connection gets: only scopes that were both asked for and ticked."""
    both = set(requested) & set(ticked)
    return [s for s in Scope if s.value in both]


def text(scopes: Iterable[str]) -> str:
    """The ``scope`` value for a token answer."""
    return " ".join(scopes)
