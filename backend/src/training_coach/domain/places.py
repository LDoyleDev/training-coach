"""Where today's session is done (ADR-0071; program-builder Decided 4): pure rules."""

from training_coach.domain.enums import Place, Places


def day_place(places: Places, last: Place) -> Place:
    """At one place, that place; at both, ``last``, the one last chosen on Today's switch."""
    if places is Places.HOME:
        return Place.HOME
    if places is Places.GYM:
        return Place.GYM
    return last


def can_switch(places: Places, has_gym_version: bool) -> bool:
    """Today offers Home | Gym when the person trains at both and the session has a gym
    version. The switch is theirs: nothing picks a place for them."""
    return places is Places.BOTH and has_gym_version
