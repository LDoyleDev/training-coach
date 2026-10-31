"""Settings on the web (ux-flow-plan C6): everything /settings changes in the bot, with the
same rules. Owner-only. Times are local wall-clock in ``settings.tz``; changing one moves the
bot's jobs straight away, as a /settings button does."""

from collections.abc import Callable
from datetime import UTC, datetime, time
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import AfterValidator, BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.cardio import EXTRA_CARDIO
from training_coach.domain.clock import parse_hhmm
from training_coach.domain.enums import Places, Sound
from training_coach.domain.habits import PROTEIN_GRAMS
from training_coach.domain.load import DEFAULTS, INCREMENT_KG, Increments, LoadKit, valid_increment
from training_coach.domain.queue import local_date
from training_coach.domain.targets import Pace
from training_coach.services import last_set, user_settings
from training_coach.services.user_settings import Prefs

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Set by the app's lifespan when the bot runs: moves the person's morning, nudge and review jobs.
Reschedule = Callable[[int, Prefs], None]


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _hhmm(text: str) -> str:
    """The bot's rule for a typed time: 07:30, 7:30 or 7.30; kept as HH:MM."""
    at = parse_hhmm(text)
    if at is None:
        raise ValueError("a time like 07:30")
    return f"{at:%H:%M}"


def _grams(grams: int) -> int:
    """The bot's rule for the protein target; 0 clears it, as in /settings."""
    if grams != 0 and not PROTEIN_GRAMS[0] <= grams <= PROTEIN_GRAMS[1]:
        raise ValueError(f"0, or between {PROTEIN_GRAMS[0]} and {PROTEIN_GRAMS[1]} grams")
    return grams


def _step(kg: float) -> float:
    if not valid_increment(kg):
        low, high = INCREMENT_KG
        raise ValueError(f"from {low:g} to {high:g} kg, in steps of 0.25")
    return kg


Clock = Annotated[str, AfterValidator(_hhmm)]
Grams = Annotated[int, AfterValidator(_grams)]
Step = Annotated[float, AfterValidator(_step)]


class IncrementsView(BaseModel):
    """The smallest weight step for each loaded kit (ADR-0072); dumbbells: per hand."""

    barbell: float
    dumbbells: float
    machine: float  # a cable's stack too
    backpack: float  # a weighted vest or backpack


class IncrementsChange(BaseModel):
    """Only the kits sent change; the default value goes back to the default."""

    barbell: Step | None = None
    dumbbells: Step | None = None
    machine: Step | None = None
    backpack: Step | None = None


class SettingsView(BaseModel):
    morning_time: str  # "07:30"
    nudge_time: str
    nudges_enabled: bool
    review_time: str  # Sundays
    habits_enabled: bool  # habit buttons in the evening message
    protein_g: int | None
    blocks_since: str | None  # training blocks on since this day (ADR-0028)
    pace: Pace  # how big a step the targets take (ADR-0057)
    sound: Sound  # what every guided timer plays at each change (ADR-0062, ADR-0074)
    extra_cardio_min: int  # a week, outside the sessions, added to cardio targets (ADR-0079)
    places: Places  # where the person trains: home, gym or both (ADR-0071)
    increments: IncrementsView  # their own weight steps, or the defaults (ADR-0072)
    default_increments: IncrementsView
    talk_test: bool  # cardio effort by the talk test, not heart-rate zones (ADR-0083)
    stop_signs_seen: bool  # shown before their first guided session (spec B7)
    # Last set: as many good reps as you can, where it's safe (ADR-0084); locked while the
    # person is new ("Available after your first 8 weeks"), when it can't be turned on.
    last_set_amrap: bool
    last_set_locked: bool
    paused: bool
    timezone: str  # the server's, for every time above


class SettingsChange(BaseModel):
    """Only the fields sent change."""

    morning_time: Clock | None = None
    nudge_time: Clock | None = None
    review_time: Clock | None = None
    nudges_enabled: bool | None = None
    habits_enabled: bool | None = None
    protein_g: Grams | None = None
    blocks: bool | None = None
    pace: Pace | None = None
    sound: Sound | None = None
    extra_cardio_min: int | None = Field(default=None, ge=EXTRA_CARDIO[0], le=EXTRA_CARDIO[1])
    places: Places | None = None
    increments: IncrementsChange | None = None
    talk_test: bool | None = None
    stop_signs_seen: bool | None = None
    last_set_amrap: bool | None = None  # true is refused with 409 while locked
    paused: bool | None = None


def _steps(increments: Increments) -> IncrementsView:
    return IncrementsView(
        barbell=increments.of(LoadKit.BARBELL),
        dumbbells=increments.of(LoadKit.DUMBBELLS),
        machine=increments.of(LoadKit.MACHINE),
        backpack=increments.of(LoadKit.BACKPACK),
    )


def _changed(body: IncrementsChange | None) -> dict[LoadKit, float] | None:
    if body is None:
        return None
    return {LoadKit(k): kg for k, kg in body.model_dump(exclude_none=True).items()}


def _time(text: str | None) -> time | None:
    return None if text is None else time.fromisoformat(text)


def _view(prefs: Prefs, settings: Settings, locked: bool) -> SettingsView:
    started = prefs.blocks_started_on
    return SettingsView(
        morning_time=f"{prefs.morning_time:%H:%M}",
        nudge_time=f"{prefs.nudge_time:%H:%M}",
        nudges_enabled=prefs.nudges_enabled,
        review_time=f"{prefs.review_time:%H:%M}",
        habits_enabled=prefs.habits_enabled,
        protein_g=prefs.protein_g,
        blocks_since=started.isoformat() if started is not None else None,
        pace=prefs.pace,
        sound=prefs.sound,
        extra_cardio_min=prefs.extra_cardio_min,
        places=prefs.places,
        increments=_steps(prefs.increments),
        default_increments=_steps(DEFAULTS),
        talk_test=prefs.talk_test,
        stop_signs_seen=prefs.stop_signs_seen,
        last_set_amrap=prefs.last_set_amrap,
        last_set_locked=locked,
        paused=prefs.paused,
        timezone=settings.timezone,
    )


@router.get("", response_model=SettingsView)
def get_settings(request: Request, user: Owner) -> SettingsView:
    settings: Settings = request.app.state.settings
    with session_scope(_bound(request, user)) as session:
        prefs = user_settings.load(session)
        locked = not last_set.available(session, local_date(datetime.now(UTC), settings.tz))
    return _view(prefs, settings, locked)


@router.patch("", response_model=SettingsView)
def patch_settings(body: SettingsChange, request: Request, user: Owner) -> SettingsView:
    settings: Settings = request.app.state.settings
    today = local_date(datetime.now(UTC), settings.tz)
    with session_scope(_bound(request, user)) as session:
        locked = not last_set.available(session, today)
        if body.last_set_amrap and locked:  # nothing else changes either
            raise HTTPException(status.HTTP_409_CONFLICT, last_set.LOCKED)
        prefs = user_settings.update(
            session,
            morning_time=_time(body.morning_time),
            nudge_time=_time(body.nudge_time),
            review_time=_time(body.review_time),
            nudges_enabled=body.nudges_enabled,
            paused=body.paused,
            blocks=body.blocks,
            habits_enabled=body.habits_enabled,
            protein_g=body.protein_g or None,
            clear_protein=body.protein_g == 0,
            pace=body.pace,
            sound=body.sound,
            extra_cardio_min=body.extra_cardio_min,
            places=body.places,
            increments=_changed(body.increments),
            talk_test=body.talk_test,
            stop_signs_seen=body.stop_signs_seen,
            last_set_amrap=body.last_set_amrap,
            today=today,
        )
    moved = (body.morning_time, body.nudge_time, body.review_time) != (None, None, None)
    reschedule: Reschedule | None = getattr(request.app.state, "reschedule", None)
    if moved and reschedule is not None:
        reschedule(user, prefs)
    log.info("api.settings_changed", what=sorted(body.model_dump(exclude_none=True)))
    return _view(prefs, settings, locked)
