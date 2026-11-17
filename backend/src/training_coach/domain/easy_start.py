"""The easy start (ADR-0094). Pure logic, no I/O.

A per-person switch. While it runs, a day's plan changes before the trim (ADR-0082) in two
phases:

- **The light start:** one set of every exercise, each set's target the bottom of its range, a
  timed item at most 10 minutes, and Move up held. It ends at the later of 4 sessions and 14 days
  from the start.
- **One set lower:** one set fewer of every exercise (a single set stays one). It ends at the
  later of 8 more sessions and 28 days from the end of the light start.

The start is the first counted workout on or after ``since`` (the day the switch was first turned
on, or the easy start restarted). A day's phase counts the sessions of the days before it, so a
day keeps its phase while its own session is logged. "One more easy week" adds 7 days to the
phase that just ended, at most twice in all; it can bring that phase back. After 14 days without
a workout while it runs, a restart is offered.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

LIGHT_SESSIONS = 4
LIGHT_DAYS = timedelta(days=14)
LOWER_SESSIONS = 8
LOWER_DAYS = timedelta(days=28)
EXTRA_WEEK = timedelta(days=7)
MOST_EXTRA_WEEKS = 2  # "One more easy week", in all (Decided 17)
GAP = timedelta(days=14)  # days without a workout before a restart is offered (Decided 9)
LIGHT_MOST_MINUTES = 10  # a timed item in the light start (ICFSR 2021: 5-10 minutes at first)
ENDING_WITHIN = timedelta(days=3)  # the line names what comes next this close to a phase's end


class Phase(StrEnum):
    OFF = "off"  # the switch is off
    WAITING = "waiting"  # on, nothing logged yet: the light start begins with the first workout
    LIGHT = "light"
    LOWER = "lower"
    DONE = "done"


_ORDER = (Phase.OFF, Phase.WAITING, Phase.LIGHT, Phase.LOWER, Phase.DONE)


@dataclass(frozen=True)
class Setting:
    """The person's easy-start settings as stored."""

    on: bool
    since: date | None = None  # workouts before it don't count
    weeks_light: int = 0  # "One more easy week" taps, per phase
    weeks_lower: int = 0


@dataclass(frozen=True)
class State:
    """Where a person's easy start stands on a day."""

    phase: Phase
    count: int = 0  # sessions done in this phase before the day
    of: int = 0  # the sessions the phase runs at least (4 or 8; 0 outside them)
    until: date | None = None  # the phase runs at least until this day (the day it can end)
    over_from: date | None = None  # the whole easy start can be over from this day at the soonest
    fresh: bool = False  # the day is the phase's first with no session in it yet
    ending: bool = False  # the next session can be the phase's last
    restart: bool = False  # offer "Start the easy start again"
    extend: Phase | None = None  # the phase "One more easy week" would bring back


def _ended(start: date, floor: date, days: Sequence[date], sessions: int) -> date | None:
    """The day a phase that began on ``start`` is over: the later of ``floor`` and the day
    after its ``sessions``-th session (``days`` all its sessions' days, in order). None: not
    yet known, too few sessions."""
    inside = [d for d in days if d >= start]
    if len(inside) < sessions:
        return None
    return max(floor, inside[sessions - 1] + timedelta(days=1))


def state(setting: Setting, done: Sequence[date], today: date) -> State:
    """The easy start on ``today``: ``done`` holds the day of every counted workout, any order,
    a day once per workout."""
    if not setting.on:
        return State(Phase.OFF)
    days = sorted(d for d in done if setting.since is None or d >= setting.since)
    before = [d for d in days if d < today]
    if not before:
        return State(Phase.WAITING)
    start = days[0]
    light_floor = start + LIGHT_DAYS + EXTRA_WEEK * setting.weeks_light
    light_end = _ended(start, light_floor, before, LIGHT_SESSIONS)
    used = setting.weeks_light + setting.weeks_lower
    gap = today - before[-1] >= GAP
    if light_end is None or today < light_end:
        count = len(before)
        light_soonest = max(light_floor, today + timedelta(days=1))
        lower_soonest = light_soonest + LOWER_DAYS + EXTRA_WEEK * setting.weeks_lower
        return State(
            Phase.LIGHT,
            count=count,
            of=LIGHT_SESSIONS,
            until=light_floor,
            over_from=lower_soonest,
            ending=count + 1 >= LIGHT_SESSIONS and light_floor - today <= ENDING_WITHIN,
            restart=gap,
        )
    left = used < MOST_EXTRA_WEEKS
    lower_floor = light_end + LOWER_DAYS + EXTRA_WEEK * setting.weeks_lower
    lower_end = _ended(light_end, lower_floor, before, LOWER_SESSIONS)
    if lower_end is None or today < lower_end:
        count = sum(1 for d in before if d >= light_end)
        return State(
            Phase.LOWER,
            count=count,
            of=LOWER_SESSIONS,
            until=lower_floor,
            over_from=lower_floor,
            fresh=count == 0,
            ending=count + 1 >= LOWER_SESSIONS and lower_floor - today <= ENDING_WITHIN,
            restart=gap,
            extend=Phase.LIGHT if left and today < light_end + EXTRA_WEEK else None,
        )
    return State(
        Phase.DONE,
        over_from=lower_end,
        fresh=not any(d >= lower_end for d in before),
        extend=Phase.LOWER if left and today < lower_end + EXTRA_WEEK else None,
    )


def sets(phase: Phase, planned: int) -> int:
    """The sets an exercise runs today: one in the light start (a WAITING day is the light start's
    first), one fewer in one set lower (never under one), else as planned."""
    if phase in (Phase.WAITING, Phase.LIGHT):
        return min(planned, 1)
    if phase is Phase.LOWER:
        return max(planned - 1, min(planned, 1))
    return planned


def minutes(phase: Phase, planned: int | None) -> int | None:
    """A timed item's minutes today: at most 10 in the light start, else as planned."""
    if planned is not None and phase in (Phase.WAITING, Phase.LIGHT):
        return min(planned, LIGHT_MOST_MINUTES)
    return planned


def target(phase: Phase, value: int, bottom: int) -> int:
    """A set's target today: no more than the bottom of its range in the light start."""
    if phase in (Phase.WAITING, Phase.LIGHT):
        return min(value, bottom)
    return value


def holds_move_up(phase: Phase) -> bool:
    """Whether Move up waits today: in the light start (Decided 10)."""
    return phase in (Phase.WAITING, Phase.LIGHT)


def notice(phase: Phase, told: Phase | None) -> Phase | None:
    """The phase a notice is due for, once each: one set lower and the end (Decided 8)."""
    if phase not in (Phase.LOWER, Phase.DONE):
        return None
    if told is not None and _ORDER.index(told) >= _ORDER.index(phase):
        return None
    return phase


def extended(setting: Setting, phase: Phase) -> Setting:
    """``setting`` after "One more easy week" for ``phase`` (the one ``State.extend`` names)."""
    if setting.weeks_light + setting.weeks_lower >= MOST_EXTRA_WEEKS:
        raise ValueError("no easy week left")
    if phase is Phase.LIGHT:
        return Setting(setting.on, setting.since, setting.weeks_light + 1, setting.weeks_lower)
    if phase is Phase.LOWER:
        return Setting(setting.on, setting.since, setting.weeks_light, setting.weeks_lower + 1)
    raise ValueError(f"{phase} can't be extended")


def restarted(today: date) -> Setting:
    """``setting`` after "Start the easy start again": counted from ``today``, no weeks used."""
    return Setting(True, today)
