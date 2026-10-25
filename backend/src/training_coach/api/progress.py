"""Each exercise's standing for the web Progress page, as /progress in the bot, how long each
session takes (ADR-0061), and moving along a ladder from the Plan page: Move up, Not yet, and
choosing a level by hand (ADR-0075). Owner-only."""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.api.session import UNITS
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import equipment, progress, session_times

router = APIRouter(prefix="/api/progress", tags=["progress"])


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


class PointView(BaseModel):
    day: date
    best: int  # the session's best set
    step_number: int  # a change from the point before is a move up


class RungView(BaseModel):
    id: int
    name: str
    cue: str | None
    # The kit it needs that isn't in the person's kit, in plain words ("a 16 kg kettlebell");
    # empty when they can do it, or before they list a kit (ADR-0071).
    missing: list[str]


class ReadyView(BaseModel):
    """An exercise ready to move up; ``slug`` links to its ladder on /plan (ADR-0075)."""

    exercise: str
    slug: str


class StandingView(BaseModel):
    exercise: str
    slug: str
    unit: Literal["reps", "seconds", "minutes"]
    step: str
    step_id: int  # the current step, sent back by Move up and Not yet
    step_number: int
    steps: int
    ladder: list[RungView]  # every step, easiest first
    last: list[int]  # the latest session at this step, per set; empty if none yet
    best_set: int | None
    status: Literal["hold", "ready", "top_of_ladder"]
    retired: bool
    trend: list[PointView]  # the last six weeks, oldest first, across ladder steps
    # On the last step the kit allows: "a 16 kg kettlebell unlocks One-arm, 16 kg". Shown as
    # "top for your kit" in place of "top of the ladder" (ADR-0071).
    unlock: str | None


class StandingsView(BaseModel):
    today: date  # the trends' last day, so the graphs use the server's window, not the device's
    strength_block: bool  # moving up waits for the hypertrophy block (ADR-0028)
    kit_listed: bool  # false: no kit listed yet, so no step is locked ("add your kit")
    standings: list[StandingView]


@router.get("", response_model=StandingsView)
def standings(request: Request, user: Owner) -> StandingsView:
    """Every exercise in plan order: its step, last session, best set and whether it's ready."""
    settings: Settings = request.app.state.settings
    on = local_date(datetime.now(UTC), settings.tz)
    with session_scope(_bound(request, user)) as session:
        found = progress.overview(session, on)
        strength = progress.in_strength_block(session, on, settings.tz)
        listed = equipment.saved_at(session) is not None
    return StandingsView(
        today=on,
        strength_block=strength,
        kit_listed=listed,
        standings=[
            StandingView(
                exercise=s.exercise,
                slug=s.slug,
                unit=UNITS[s.kind],
                step=s.step,
                step_id=s.step_id,
                step_number=s.step_number,
                steps=s.steps,
                ladder=[
                    RungView(id=r.id, name=r.name, cue=r.cue, missing=list(r.missing))
                    for r in s.ladder
                ],
                last=list(s.last),
                best_set=s.best_set,
                status=s.status.value,
                retired=s.retired,
                trend=[
                    PointView(day=p.day, best=p.best, step_number=p.step_number) for p in s.trend
                ],
                unlock=s.unlock,
            )
            for s in found
        ],
    )


class SessionTimeView(BaseModel):
    """A session's times in whole minutes, from its timed guided sessions (ADR-0061)."""

    session: str
    usual: int  # the median of the last five
    last: int
    fastest: int
    timed: int  # how many were timed


@router.get("/times", response_model=list[SessionTimeView])
def times(request: Request, user: Owner) -> list[SessionTimeView]:
    """Each session that has been timed, in plan order: how long it usually takes."""
    with session_scope(_bound(request, user)) as session:
        found = session_times.by_session(session)
    return [
        SessionTimeView(
            session=t.session, usual=t.usual, last=t.last, fastest=t.fastest, timed=t.timed
        )
        for t in found
    ]


class MoveUpBody(BaseModel):
    from_step_id: int  # the step the page showed; a move from any other changes nothing


class StepBody(BaseModel):
    step_id: int


class MovedView(BaseModel):
    """What a press did. Anything but ``moved``, ``stayed`` or ``level_set`` changed nothing."""

    outcome: Literal[
        "moved",
        "already_moved",
        "not_ready",
        "no_next_step",
        "strength_block",
        "stayed",
        "level_set",
        "same_level",
    ]
    exercise: str
    step: str | None  # the step trained from now on, when it changed or stayed
    # A level chosen by hand that the kit doesn't allow: chosen anyway, the person decides
    # ("Two-hand, 16 kg needs a 16 kg kettlebell, not in your kit.", ADR-0071).
    warning: str | None


def _exercise(session: Session, slug: str) -> int:
    exercise_id = progress.exercise_id_for(session, slug)
    if exercise_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such exercise.")
    return exercise_id


def _moved(found: progress.Move | None) -> MovedView:
    if found is None:  # a step that isn't on this exercise's ladder
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Not a step of that exercise.")
    return MovedView(
        outcome=found.outcome.value, exercise=found.exercise, step=found.step, warning=found.warning
    )


@router.post("/{slug}/move-up", response_model=MovedView)
def move_up(slug: str, body: MoveUpBody, request: Request, user: Owner) -> MovedView:
    """Move up, as the bot's button: checked again now, so a stale or forged press changes
    nothing, and held in a strength block (ADR-0025, ADR-0028)."""
    settings: Settings = request.app.state.settings
    on = local_date(datetime.now(UTC), settings.tz)
    with session_scope(_bound(request, user)) as session:
        found = progress.move_up(
            session,
            _exercise(session, slug),
            body.from_step_id,
            strength_block=progress.in_strength_block(session, on, settings.tz),
        )
        return _moved(found)


@router.post("/{slug}/not-yet", response_model=MovedView)
def not_yet(slug: str, body: StepBody, request: Request, user: Owner) -> MovedView:
    """Not yet: stay on the step the page showed; asked again after the next session that still
    meets the rule."""
    with session_scope(_bound(request, user)) as session:
        return _moved(progress.stay(session, _exercise(session, slug), body.step_id))


@router.post("/{slug}/level", response_model=MovedView)
def set_level(slug: str, body: StepBody, request: Request, user: Owner) -> MovedView:
    """Choose any step of the exercise's own ladder, up or down; never needs "ready"."""
    with session_scope(_bound(request, user)) as session:
        return _moved(progress.set_level(session, _exercise(session, slug), body.step_id))
