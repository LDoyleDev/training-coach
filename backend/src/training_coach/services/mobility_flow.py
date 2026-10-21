"""The guided mobility flow (ADR-0062), read from the bundled plan like the stretches: nothing
logged refers to a movement, only to the mobility exercise it is logged as."""

from training_coach.domain.mobility_flow import Flow
from training_coach.services.seed import bundled_plan


def flow_for(exercise: str) -> Flow | None:
    """The flow to guide when ``exercise`` (a slug) comes up in a session, or None."""
    found = bundled_plan().mobility
    return found.flow() if found is not None and found.exercise == exercise else None
