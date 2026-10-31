"""Reading and changing a person's settings row (times are local wall-clock, Europe/Berlin)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, FitnessTestDay, UserSettings, Workout
from training_coach.domain.enums import Place, Places, Sound
from training_coach.domain.load import DEFAULTS, INCREMENT, Increments, LoadKit
from training_coach.domain.targets import Pace
from training_coach.services import users

DEFAULT_MORNING = time(7, 30)
DEFAULT_NUDGE = time(20, 0)
DEFAULT_REVIEW = time(19, 0)  # Sundays (D6)


@dataclass(frozen=True)
class Prefs:
    morning_time: time = DEFAULT_MORNING
    nudge_time: time = DEFAULT_NUDGE
    nudges_enabled: bool = True
    paused: bool = False
    review_time: time = DEFAULT_REVIEW
    blocks_started_on: date | None = None  # training blocks on since then (ADR-0028)
    habits_enabled: bool = True  # habit buttons in the evening message (D5)
    protein_g: int | None = None  # daily protein target for the habit
    pace: Pace = Pace.STANDARD  # how big a step the targets take (ADR-0057)
    sound: Sound = Sound.RING  # what every guided timer plays at each change (ADR-0074)
    extra_cardio_min: int = 0  # a week, outside the sessions, added to cardio targets (ADR-0079)
    places: Places = Places.HOME  # where the person trains: home, gym or both (ADR-0071)
    place: Place = Place.HOME  # at both: the last place chosen on Today's switch (Decided 4)
    increments: Increments = DEFAULTS  # their own weight steps (ADR-0072)
    talk_test: bool = False  # cardio effort by the talk test, not heart-rate zones (ADR-0083)
    stop_signs_seen: bool = False  # shown before their first guided session (spec B7)
    session_minutes: int | None = None  # every session's length (ADR-0082); None: as planned


def _increments(old: Increments, change: Mapping[LoadKit, float]) -> Increments:
    """``old`` with ``change`` applied; a step set back to the default is kept as no step of
    their own, so a later change to the default reaches them."""

    def pick(kit: LoadKit, own: float | None) -> float | None:
        new = change.get(kit, own)
        return None if new == INCREMENT[kit] else new

    return Increments(
        barbell=pick(LoadKit.BARBELL, old.barbell),
        dumbbells=pick(LoadKit.DUMBBELLS, old.dumbbells),
        machine=pick(LoadKit.MACHINE, old.machine),
        backpack=pick(LoadKit.BACKPACK, old.backpack),
    )


def load(session: Session) -> Prefs:
    row = users.settings_row(session)
    if row is None:
        return Prefs()
    return Prefs(
        row.morning_time,
        row.nudge_time,
        row.nudges_enabled,
        row.paused,
        row.review_time,
        row.blocks_started_on,
        row.habits_enabled,
        row.protein_g,
        Pace(row.pace),
        Sound(row.sound),
        row.extra_cardio_min,
        Places(row.places),
        Place(row.place),
        Increments(
            row.barbell_increment_kg,
            row.dumbbells_increment_kg,
            row.machine_increment_kg,
            row.backpack_increment_kg,
        ),
        row.talk_test,
        row.stop_signs_seen,
        row.session_minutes,
    )


def update(
    session: Session,
    *,
    morning_time: time | None = None,
    nudge_time: time | None = None,
    review_time: time | None = None,
    nudges_enabled: bool | None = None,
    paused: bool | None = None,
    blocks: bool | None = None,
    habits_enabled: bool | None = None,
    protein_g: int | None = None,
    clear_protein: bool = False,
    pace: Pace | None = None,
    sound: Sound | None = None,
    extra_cardio_min: int | None = None,
    places: Places | None = None,
    place: Place | None = None,
    increments: Mapping[LoadKit, float] | None = None,
    talk_test: bool | None = None,
    stop_signs_seen: bool | None = None,
    session_minutes: int | None = None,
    clear_session_minutes: bool = False,
    today: date | None = None,
) -> Prefs:
    """Change the given settings (creating the row if needed) and log what changed.
    ``increments``: the kits whose weight step changes, each to a valid step (the caller checks).
    ``session_minutes``: 40, 30 or 20 (the caller checks); ``clear_session_minutes`` sets it
    back to as planned.

    ``blocks=True`` starts training blocks on ``today`` unless they are already on (so a
    repeated press never restarts them); ``blocks=False`` turns them off."""
    old = load(session)
    started = old.blocks_started_on
    if blocks is True and started is None:
        if today is None:
            raise ValueError("turning blocks on needs today's date")
        started = today
    elif blocks is False:
        started = None
    prefs = Prefs(
        morning_time=old.morning_time if morning_time is None else morning_time,
        nudge_time=old.nudge_time if nudge_time is None else nudge_time,
        review_time=old.review_time if review_time is None else review_time,
        nudges_enabled=old.nudges_enabled if nudges_enabled is None else nudges_enabled,
        paused=old.paused if paused is None else paused,
        blocks_started_on=started,
        habits_enabled=old.habits_enabled if habits_enabled is None else habits_enabled,
        protein_g=None if clear_protein else old.protein_g if protein_g is None else protein_g,
        pace=old.pace if pace is None else pace,
        sound=old.sound if sound is None else sound,
        extra_cardio_min=old.extra_cardio_min if extra_cardio_min is None else extra_cardio_min,
        places=old.places if places is None else places,
        place=old.place if place is None else place,
        increments=_increments(old.increments, increments or {}),
        talk_test=old.talk_test if talk_test is None else talk_test,
        stop_signs_seen=old.stop_signs_seen if stop_signs_seen is None else stop_signs_seen,
        session_minutes=None
        if clear_session_minutes
        else old.session_minutes
        if session_minutes is None
        else session_minutes,
    )
    changes: dict[str, str | bool | int | float] = {}
    if morning_time is not None:
        changes["morning_time"] = morning_time.isoformat()
    if nudge_time is not None:
        changes["nudge_time"] = nudge_time.isoformat()
    if review_time is not None:
        changes["review_time"] = review_time.isoformat()
    if nudges_enabled is not None:
        changes["nudges_enabled"] = nudges_enabled
    if paused is not None:
        changes["paused"] = paused
    if blocks is not None:
        changes["blocks"] = blocks
    if habits_enabled is not None:
        changes["habits_enabled"] = habits_enabled
    if protein_g is not None or clear_protein:
        changes["protein_g"] = protein_g or 0  # 0: cleared
    if pace is not None:
        changes["pace"] = pace.value
    if sound is not None:
        changes["sound"] = sound.value
    if extra_cardio_min is not None:
        changes["extra_cardio_min"] = extra_cardio_min
    if places is not None:
        changes["places"] = places.value
    if place is not None:
        changes["place"] = place.value
    if talk_test is not None:
        changes["talk_test"] = talk_test
    if stop_signs_seen is not None:
        changes["stop_signs_seen"] = stop_signs_seen
    if session_minutes is not None or clear_session_minutes:
        changes["session_minutes"] = session_minutes or 0  # 0: as planned
    for kit, kg in (increments or {}).items():
        changes[f"{kit.value}_increment_kg"] = kg
    row = users.settings_row(session)
    if row is None:
        row = UserSettings()
        session.add(row)
    row.morning_time = prefs.morning_time
    row.nudge_time = prefs.nudge_time
    row.review_time = prefs.review_time
    row.nudges_enabled = prefs.nudges_enabled
    row.paused = prefs.paused
    row.blocks_started_on = prefs.blocks_started_on
    row.habits_enabled = prefs.habits_enabled
    row.protein_g = prefs.protein_g
    row.pace = prefs.pace.value
    row.sound = prefs.sound.value
    row.extra_cardio_min = prefs.extra_cardio_min
    row.places = prefs.places.value
    row.place = prefs.place.value
    row.barbell_increment_kg = prefs.increments.barbell
    row.dumbbells_increment_kg = prefs.increments.dumbbells
    row.machine_increment_kg = prefs.increments.machine
    row.backpack_increment_kg = prefs.increments.backpack
    row.talk_test = prefs.talk_test
    row.stop_signs_seen = prefs.stop_signs_seen
    row.session_minutes = prefs.session_minutes
    if prefs != old:  # a repeated press changes nothing and logs nothing
        session.add(Event(kind="settings.changed", payload=changes))
    return prefs


def anything_logged(session: Session, on: date) -> bool:
    """Any workout on ``on``, whatever its status (done, rest or skipped, ADR-0014), or a
    test day (ADR-0038)."""
    if session.scalar(select(Workout.id).where(Workout.local_date == on).limit(1)) is not None:
        return True
    tested = select(FitnessTestDay.id).where(FitnessTestDay.local_date == on).limit(1)
    return session.scalar(tested) is not None
