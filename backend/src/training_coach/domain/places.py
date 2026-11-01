"""Where today's session is done (ADR-0071; program-builder Decided 4; ADR-0086): pure rules."""

from collections.abc import Sequence

from training_coach.domain.enums import Place, Places


def day_place(places: Places, last: Place) -> Place:
    """At one place, that place; at both, ``last``, the one last chosen on Today's switch."""
    if places is Places.HOME:
        return Place.HOME
    if places is Places.GYM:
        return Place.GYM
    return last


def choices(places: Places, has_gym_version: bool, has_away_version: bool) -> tuple[Place, ...]:
    """The places Today's switch offers for a session: Home | Gym for someone at both when it
    has a gym version, else the one place it is done at (home when it has no gym version); and
    Away when it has an away version, for anyone (ADR-0086). The switch is theirs: nothing picks
    a place for them."""
    if has_gym_version and places is not Places.HOME:
        base = (Place.HOME, Place.GYM) if places is Places.BOTH else (Place.GYM,)
    else:
        base = (Place.HOME,)
    return (*base, Place.AWAY) if has_away_version else base


def no_kit_step(free: Sequence[bool], at: int) -> int:
    """The step an away session trains (ADR-0086): ``at`` when it needs no kit, else the highest
    step below it that needs none; ``at`` itself when none does. ``free`` says, easiest first,
    whether each step needs no kit and takes no load. Never above the person's level."""
    return next((i for i in range(at, -1, -1) if free[i]), at)
