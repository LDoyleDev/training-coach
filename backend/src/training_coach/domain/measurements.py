"""Body measurements (2-B, #142; the protocol and the estimate, ADR-0074). Pure logic, no I/O.

Values are kept in tenths (83.4 kg is 834), so no floating point creeps into stored data;
resting heart rate is whole beats. Each kind has a range wide enough for anyone and narrow
enough to catch a slip (a waist of 820 cm), and a line on how to take it the same way each
time: the web app, the AI's tools and the AI summary all read it from here.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class Kind(StrEnum):
    BODYWEIGHT = "bodyweight"
    BODY_FAT_SCALE = "body_fat_scale"
    WAIST = "waist"
    NECK = "neck"
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
    how: str  # how to take it; ``{offset}`` is the person's thigh landmark


SPECS: dict[Kind, Spec] = {
    Kind.BODYWEIGHT: Spec(
        "Bodyweight",
        "kg",
        1,
        30,
        250,
        "Same scale, on a hard floor, in minimal clothing. Day to day it moves with water: "
        "the trend is the 7-day average.",
    ),
    Kind.BODY_FAT_SCALE: Spec(
        "Body fat (scale)",
        "%",
        1,
        3,
        60,
        "Same scale, barefoot with dry feet, at the same time of day. Use it for the trend "
        "only: the number itself can be far off.",
    ),
    Kind.WAIST: Spec("Waist", "cm", 1, 40, 200, "Horizontal at the navel, relaxed."),
    Kind.NECK: Spec(
        "Neck",
        "cm",
        1,
        20,
        70,
        "Just below the larynx (Adam's apple), the tape sloping slightly down at the front.",
    ),
    Kind.CHEST: Spec("Chest", "cm", 1, 50, 200, "At the nipple line, arms down at the sides."),
    Kind.UPPER_ARM: Spec(
        "Upper arm",
        "cm",
        1,
        15,
        70,
        "Relaxed and hanging, midway between the tip of the shoulder and the point of the elbow.",
    ),
    Kind.THIGH: Spec(
        "Thigh",
        "cm",
        1,
        25,
        100,
        "Standing, weight on both legs evenly, {offset} above the top of the kneecap.",
    ),
    Kind.RESTING_HR: Spec(
        "Resting heart rate",
        "bpm",
        0,
        25,
        150,
        "One source only: the band's overnight resting heart rate is best.",
    ),
}

# Before any of them: the same conditions every time, so a change is the body's, not the tape's.
CHECKLIST = (
    "In the morning, after the toilet, before food, drink or training.",
    "A tape that doesn't stretch, on skin: snug, not pressing in, level all the way round.",
    "Stand relaxed and read it at the end of a normal breath out.",
    "Measure twice; if they're more than 0.5 cm apart, measure a third time. Enter the average.",
    "Upper arm and thigh: the right side.",
)
CADENCE = "Weight daily or weekly; the tape and photos every 2 to 4 weeks."

# A change from the last earlier entry this big more likely means a different landmark (or
# scale) than a different body: say so, never refuse. Resting heart rate isn't checked.
REMEASURE: dict[Kind, float | None] = {
    Kind.BODYWEIGHT: 2,
    Kind.BODY_FAT_SCALE: 3,
    Kind.WAIST: 3,
    Kind.NECK: 1.5,
    Kind.CHEST: 3,
    Kind.UPPER_ARM: 1.5,
    Kind.THIGH: 2,
    Kind.RESTING_HR: None,
}
SCALE_KINDS = frozenset({Kind.BODYWEIGHT, Kind.BODY_FAT_SCALE})

# Per-person settings (ADR-0074).
HEIGHT_CM = (120, 230)
THIGH_OFFSET_CM = (5, 30)
DEFAULT_THIGH_OFFSET_CM = 15
AVERAGE_DAYS = 7  # bodyweight's trend


class BodyFatEstimate(StrEnum):
    OFF = "off"
    NAVY_MALE = "navy_male"  # the US Navy tape formula for men, from waist, neck and height


ESTIMATE_LABEL = "estimate from waist and neck, ±4%"  # wherever the estimate is shown


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


def how(kind: Kind, thigh_offset_cm: int | None = None) -> str:
    """How to take ``kind``; the thigh at the person's distance above the kneecap, or "a set
    distance" for a reader who doesn't know it (an AI's tool description)."""
    offset = "a set distance" if thigh_offset_cm is None else f"{thigh_offset_cm} cm"
    return SPECS[kind].how.format(offset=offset)


def first_sentence(text: str) -> str:
    head, dot, _ = text.partition(". ")
    return head + "." if dot else text


def amount(kind: Kind, value: float) -> str:
    """``value`` with its unit, as shown: "83.4 kg", "52 bpm", "3.5 points" for a change in %."""
    spec = SPECS[kind]
    unit = "points" if spec.unit == "%" else spec.unit
    return f"{value:.{spec.decimals}f} {unit}"


def _day(on: date, beside: date) -> str:
    return f"{on.day} {on:%b}" if on.year == beside.year else f"{on.day} {on:%b %Y}"


def remeasure(kind: Kind, on: date, value: float, last: tuple[date, float] | None) -> str | None:
    """A warning when ``value`` for ``on`` is far from ``last`` (the day and value of the last
    earlier entry of ``kind``, any age), naming that day; None when it's close or there is no
    threshold or nothing earlier."""
    threshold = REMEASURE[kind]
    if threshold is None or last is None:
        return None
    off = abs(round(value * 10) - round(last[1] * 10))  # in tenths, as stored
    if off < round(threshold * 10):
        return None
    why = "different scale or time of day?" if kind in SCALE_KINDS else "different landmark?"
    return (
        f"{SPECS[kind].label} is {amount(kind, off / 10)} off your last "
        f"({_day(last[0], on)}): {why} Re-measure."
    )


def navy_body_fat(
    height_cm: float | None, neck_cm: float | None, waist_cm: float | None
) -> float | None:
    """Body fat in %, to one decimal, by the US Navy formula for men (all in cm); None when
    anything is missing or the waist isn't bigger than the neck."""
    if height_cm is None or neck_cm is None or waist_cm is None or waist_cm <= neck_cm:
        return None
    density = 1.0324 - 0.19077 * math.log10(waist_cm - neck_cm) + 0.15456 * math.log10(height_cm)
    return round(495 / density - 450, 1)


def averages(
    entries: Iterable[tuple[date, float]], days: int = AVERAGE_DAYS
) -> list[tuple[date, float, int]]:
    """For each day with an entry, newest first: the mean of the entries in the ``days`` days
    ending that day (it and the ``days - 1`` before), to one decimal, and how many there were."""
    found = sorted(entries, reverse=True)
    out = []
    for on, _ in found:
        window = [v for d, v in found if on - timedelta(days=days - 1) <= d <= on]
        out.append((on, round(sum(window) / len(window), 1), len(window)))
    return out


def settings_problem(height_cm: int | None, thigh_offset_cm: int) -> str | None:
    """Why these body settings can't be saved, or None."""
    low, high = HEIGHT_CM
    if height_cm is not None and not low <= height_cm <= high:
        return f"height must be from {low} to {high} cm"
    low, high = THIGH_OFFSET_CM
    if not low <= thigh_offset_cm <= high:
        return f"the thigh is measured from {low} to {high} cm above the kneecap"
    return None
