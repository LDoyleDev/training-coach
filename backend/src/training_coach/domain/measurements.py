"""Body measurements (2-B, #142). Pure logic, no I/O.

Values are kept in tenths (83.4 kg is 834), so no floating point creeps into stored data;
resting heart rate is whole beats. Each kind has a range wide enough for anyone and narrow
enough to catch a slip (a waist of 820 cm).
"""

from dataclasses import dataclass
from enum import StrEnum


class Kind(StrEnum):
    BODYWEIGHT = "bodyweight"
    WAIST = "waist"
    CHEST = "chest"
    UPPER_ARM = "upper_arm"
    THIGH = "thigh"
    RESTING_HR = "resting_hr"


@dataclass(frozen=True)
class Spec:
    label: str
    unit: str
    decimals: int  # 1: tenths; 0: whole numbers
    low: float
    high: float


SPECS: dict[Kind, Spec] = {
    Kind.BODYWEIGHT: Spec("Bodyweight", "kg", 1, 30, 250),
    Kind.WAIST: Spec("Waist", "cm", 1, 40, 200),
    Kind.CHEST: Spec("Chest", "cm", 1, 50, 200),
    Kind.UPPER_ARM: Spec("Upper arm", "cm", 1, 15, 70),
    Kind.THIGH: Spec("Thigh", "cm", 1, 25, 100),
    Kind.RESTING_HR: Spec("Resting heart rate", "bpm", 0, 25, 150),
}


def to_tenths(kind: Kind, value: float) -> int | str:
    """The stored value, or why ``value`` can't be one."""
    spec = SPECS[kind]
    if not spec.low <= value <= spec.high:
        return f"{spec.label} must be from {spec.low:g} to {spec.high:g} {spec.unit}"
    tenths = round(value * 10)
    if spec.decimals == 0 and tenths % 10:
        return f"{spec.label} is a whole number"
    return tenths


def from_tenths(tenths: int) -> float:
    return tenths / 10
