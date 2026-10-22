"""The exercise catalogue's fixed vocabulary (program-builder.md B, ADR-0064). Pure logic.

Every exercise names the muscles it trains from one fixed list, each with a weight: a hard set
counts 1 for a prime mover, 0.5 for a meaningful synergist and 0.25 for a small part; a
stabiliser isn't listed (it counts 0). The weights come from growth studies where they exist
and are estimates otherwise (docs/specs/program-builder-research.md, Weights by exercise).
"""

from collections.abc import Iterable
from enum import StrEnum


class Muscle(StrEnum):
    NECK = "neck"
    CHEST = "chest"
    FRONT_DELTS = "front delts"
    SIDE_DELTS = "side delts"
    REAR_DELTS = "rear delts"
    UPPER_BACK = "upper back"
    UPPER_TRAPS = "upper traps"
    LATS = "lats"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    FOREARMS = "forearms"
    ABS = "abs"
    OBLIQUES = "obliques"
    LOWER_BACK = "lower back"
    GLUTES = "glutes"
    HIP_FLEXORS = "hip flexors"
    ADDUCTORS = "adductors"
    QUADS = "quads"
    HAMSTRINGS = "hamstrings"
    CALVES = "calves"
    TIBIALIS = "tibialis"


class Quality(StrEnum):
    """What an exercise trains that isn't a muscle; never counted as sets."""

    POSTURE = "posture"
    POWER = "power"
    MOBILITY = "mobility"
    CONDITIONING = "conditioning"


class Part(StrEnum):
    """A part of a muscle that compounds barely grow, so the map flags it unless an exercise
    reaches it, even when the muscle itself is covered (program-builder.md, Decided 2)."""

    TRICEPS_LONG_HEAD = "triceps long head"  # an overhead extension (Brandão 2020, Maeo 2023)
    RECTUS_FEMORIS = "rectus femoris"  # a leg extension (Kinoshita 2026)


PART_OF = {Part.TRICEPS_LONG_HEAD: Muscle.TRICEPS, Part.RECTUS_FEMORIS: Muscle.QUADS}


class Pattern(StrEnum):
    """The movement an exercise is; a swap offers the same pattern first."""

    SQUAT = "squat"
    HINGE = "hinge"
    LUNGE = "lunge"
    HORIZONTAL_PUSH = "horizontal push"
    VERTICAL_PUSH = "vertical push"
    HORIZONTAL_PULL = "horizontal pull"
    VERTICAL_PULL = "vertical pull"
    CARRY = "carry"
    CORE = "core"
    ISOLATION = "isolation"
    MOBILITY = "mobility"
    CARDIO = "cardio"


class Stress(StrEnum):
    """Load an exercise shares with others beyond its muscles, for the session warnings. A squat
    or lunge loads the spine only on steps that carry a weight (``step_stress``)."""

    SPINE = "spine"
    GRIP = "grip"


class Kit(StrEnum):
    """Equipment a ladder step needs. Household things (a chair, a bed, a wall, a towel, water
    bottles, a stair) need nothing. A kettlebell names its weight: ``kettlebell:16``."""

    KETTLEBELL = "kettlebell"
    DUMBBELLS = "dumbbells"
    PULL_UP_BAR = "pull-up bar"
    DIP_BARS = "dip bars"
    BENCH = "bench"
    BAND = "band"
    BACKPACK = "backpack"
    RINGS = "rings"
    MAT = "mat"


WEIGHTS = (1.0, 0.5, 0.25)
WEIGHED = frozenset({Kit.KETTLEBELL})  # kit that comes in weights, each one owned apart
LOADS = frozenset({Kit.KETTLEBELL, Kit.DUMBBELLS, Kit.BACKPACK})  # kit that is a weight to carry
SQUATS = frozenset({Pattern.SQUAT, Pattern.LUNGE})


def step_stress(stress: Iterable[Stress], pattern: Pattern, needs: Iterable[str]) -> set[Stress]:
    """The stress one ladder step adds. Only loaded squats load the spine (goblet, back and front
    squats, a loaded split squat); bodyweight and jump squats don't (program-builder.md,
    Decided 3). Hinges, swings, back extensions, carries and bent-over rows always do."""
    found = set(stress)
    if pattern in SQUATS and not any(parse_need(n)[0] in LOADS for n in needs):
        found.discard(Stress.SPINE)
    return found


def parse_need(need: str) -> tuple[Kit, int | None]:
    """``"kettlebell:16"`` -> ``(Kit.KETTLEBELL, 16)``; ``"pull-up bar"`` -> ``(..., None)``.

    Raises ValueError for unknown kit, or a weight missing, given where it doesn't belong, or
    not a whole number of kilograms from 1 to 100.
    """
    name, sep, kg = need.partition(":")
    kit = Kit(name)
    if kit not in WEIGHED:
        if sep:
            raise ValueError(f"{need!r}: {kit} has no weight")
        return kit, None
    if not kg.isdigit() or not 1 <= int(kg) <= 100:
        raise ValueError(f"{need!r}: say the weight in kg, like {kit}:16")
    return kit, int(kg)
