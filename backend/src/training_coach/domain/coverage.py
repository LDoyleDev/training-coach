"""What a week of the plan gives each muscle, against its own band (program-builder.md, Decided 3
and F; the evidence is in program-builder-research.md). Pure logic, no I/O.

Sets are fractional (ADR-0064). A muscle's band comes from its weekly sets; green also needs
the muscle on two days a week. The warnings are the ones a read-only map can show: too much in
one session, the same muscle hard on two days running, a muscle part compounds miss, and
sessions heavy on the spine or the grip.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from training_coach.domain.muscles import PART_OF, Muscle, Part, Stress


class Band(StrEnum):
    GREY = "grey"  # not trained
    AMBER = "amber"  # below the effective minimum
    LIGHT_GREEN = "light green"  # the minimum; enough to maintain
    GREEN = "green"  # the target
    BLUE = "blue"  # high: diminishing returns
    WARNING = "warning"  # past where more showed no extra growth


class Evidence(StrEnum):
    """How well a muscle's own band is supported; the app marks the weak ones."""

    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very low"


@dataclass(frozen=True)
class Target:
    low: float
    high: float
    evidence: Evidence | None = None  # None: the general band


GENERAL = Target(10, 20)  # Schoenfeld 2017; ACSM 2026: 10 or more
OWN = {
    Muscle.NECK: Target(3, 9, Evidence.LOW),  # per direction in the spec; counted together here
    Muscle.TIBIALIS: Target(2, 6, Evidence.VERY_LOW),
    Muscle.FOREARMS: Target(4, 10, Evidence.LOW),
    Muscle.CALVES: Target(8, 16, Evidence.MODERATE),
    Muscle.SIDE_DELTS: Target(8, 20, Evidence.LOW),
    Muscle.REAR_DELTS: Target(8, 20, Evidence.LOW),
    Muscle.FRONT_DELTS: Target(4, 20, Evidence.LOW),  # covered by presses; no direct work
    # The trunk and hips work in every compound and no growth trial sets their dose: own bands,
    # estimates (program-builder-research.md, "Core and hips").
    Muscle.ABS: Target(6, 12, Evidence.LOW),
    Muscle.OBLIQUES: Target(4, 10, Evidence.LOW),
    Muscle.LOWER_BACK: Target(4, 10, Evidence.LOW),  # once a week suffices for strength
    Muscle.HIP_FLEXORS: Target(3, 8, Evidence.LOW),
    Muscle.ADDUCTORS: Target(4, 10, Evidence.LOW),
}
MAIN = (
    Muscle.QUADS,
    Muscle.GLUTES,
    Muscle.HAMSTRINGS,
    Muscle.CHEST,
    Muscle.LATS,
    Muscle.UPPER_BACK,
    Muscle.TRICEPS,
    Muscle.BICEPS,
    Muscle.SIDE_DELTS,
    Muscle.CALVES,
)

MINIMUM = 4  # the effective minimum (Iversen 2021)
CEILING = 30  # past this, more showed no extra growth (Pelland 2026)
DAY_SETS = 2  # a session counts as a day for a muscle from 2 sets
TWO_DAYS = 2  # green needs this many days a week (ACSM 2026)
SESSION_CAP = 11  # one muscle, one session (a preprint's plateau)
BACK_TO_BACK = 4  # this much for one muscle on two days running is no rest between
SPINE_CAP = 8  # spine-loading hard sets in one session (no study: a rule of thumb)
GRIP_CAP = 8  # grip-heavy sets in one session (no study: a rule of thumb)


def target(muscle: Muscle) -> Target:
    return OWN.get(muscle, GENERAL)


def needs_two_days(muscle: Muscle) -> bool:
    """The two-day rule is for the main muscles and those on the general band; the small
    muscles with their own band count as covered on one day."""
    return muscle in MAIN or muscle not in OWN


def band(sets: float, goal: Target) -> Band:
    if sets <= 0:
        return Band.GREY
    if sets > CEILING:
        return Band.WARNING
    if sets > goal.high:
        return Band.BLUE
    if sets >= goal.low:
        return Band.GREEN
    return Band.LIGHT_GREEN if sets >= MINIMUM else Band.AMBER


@dataclass(frozen=True)
class Item:
    """One exercise in a session, as planned."""

    exercise: str  # its name
    sets: int
    muscles: Mapping[Muscle, float]
    parts: frozenset[Part] = frozenset()
    stress: frozenset[Stress] = frozenset()  # at the step being trained (``step_stress``)


@dataclass(frozen=True)
class Day:
    """One session of the cycle, in queue order; the cycle is a week."""

    name: str
    items: Sequence[Item]


@dataclass(frozen=True)
class Source:
    session: str
    exercise: str
    sets: int
    weight: float  # what one set counts for this muscle


@dataclass(frozen=True)
class MuscleCoverage:
    muscle: Muscle
    main: bool
    sets: float  # fractional, a week
    days: int  # sessions with at least DAY_SETS for it
    most: float  # the most in one session
    most_in: str | None  # that session
    band: Band
    target: Target
    one_day: bool  # trained, but on fewer days than the two-day rule needs
    back_to_back: tuple[str, str] | None  # two sessions running with BACK_TO_BACK or more
    missing_parts: tuple[Part, ...]  # parts no exercise in the week reaches
    sources: tuple[Source, ...]

    @property
    def over_session_cap(self) -> bool:
        return self.most > SESSION_CAP


@dataclass(frozen=True)
class DayLoad:
    name: str
    spine_sets: int
    grip_sets: int

    @property
    def spine_heavy(self) -> bool:
        return self.spine_sets > SPINE_CAP

    @property
    def grip_heavy(self) -> bool:
        return self.grip_sets > GRIP_CAP


@dataclass(frozen=True)
class Coverage:
    muscles: tuple[MuscleCoverage, ...]  # every muscle, main ones first, then the fixed order
    days: tuple[DayLoad, ...]

    @property
    def main_on_target(self) -> int:
        return sum(1 for m in self.muscles if m.main and m.band is Band.GREEN)


def coverage(week: Sequence[Day]) -> Coverage:
    """Each muscle's week, and each session's shared load, from the cycle in queue order."""
    reached = {part for day in week for item in day.items for part in item.parts}
    per_day: list[dict[Muscle, float]] = []
    sources: dict[Muscle, list[Source]] = {}
    for day in week:
        totals: dict[Muscle, float] = {}
        for item in day.items:
            for muscle, weight in item.muscles.items():
                if weight <= 0:
                    continue
                totals[muscle] = totals.get(muscle, 0) + weight * item.sets
                sources.setdefault(muscle, []).append(
                    Source(day.name, item.exercise, item.sets, weight)
                )
        per_day.append(totals)

    found = [_muscle(m, week, per_day, sources.get(m, []), reached) for m in _ordered(Muscle)]
    loads = tuple(
        DayLoad(
            day.name,
            spine_sets=sum(i.sets for i in day.items if Stress.SPINE in i.stress),
            grip_sets=sum(i.sets for i in day.items if Stress.GRIP in i.stress),
        )
        for day in week
    )
    return Coverage(tuple(found), loads)


def _ordered(muscles: Iterable[Muscle]) -> list[Muscle]:
    rest = [m for m in muscles if m not in MAIN]
    return [*MAIN, *rest]


def _muscle(
    muscle: Muscle,
    week: Sequence[Day],
    per_day: Sequence[Mapping[Muscle, float]],
    sources: Sequence[Source],
    reached: set[Part],
) -> MuscleCoverage:
    daily = [d.get(muscle, 0.0) for d in per_day]
    sets = sum(daily)
    days = sum(1 for n in daily if n >= DAY_SETS)
    most = max(daily, default=0.0)
    most_in = week[daily.index(most)].name if most > 0 else None
    goal = target(muscle)
    found = band(sets, goal)
    one_day = needs_two_days(muscle) and sets > 0 and days < TWO_DAYS
    if found is Band.GREEN and one_day:
        found = Band.LIGHT_GREEN  # green needs two days a week (ACSM 2026)
    missing = (
        tuple(p for p, of in PART_OF.items() if of is muscle and p not in reached)
        if sets > 0
        else ()
    )
    return MuscleCoverage(
        muscle=muscle,
        main=muscle in MAIN,
        sets=sets,
        days=days,
        most=most,
        most_in=most_in,
        band=found,
        target=goal,
        one_day=one_day,
        back_to_back=_back_to_back(week, daily),
        missing_parts=missing,
        sources=tuple(sources),
    )


def _back_to_back(week: Sequence[Day], daily: Sequence[float]) -> tuple[str, str] | None:
    """The first two sessions running, the last wrapping to the first (the cycle repeats),
    that both give the muscle BACK_TO_BACK sets or more."""
    if len(week) < 2:
        return None
    for i, n in enumerate(daily):
        j = (i + 1) % len(week)
        if n >= BACK_TO_BACK and daily[j] >= BACK_TO_BACK:
            return week[i].name, week[j].name
    return None
