"""Today's guided session for the web app (D1, #117). Owner-only."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.api.clash import CLASH, ClashReply, conflict, resolution
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.daily_check import summary as daily_summary
from training_coach.domain.enums import ExerciseKind, Place
from training_coach.domain.load import MAX_KG, Load
from training_coach.domain.mobility_flow import Flow
from training_coach.domain.queue import local_date
from training_coach.domain.readiness import HARD_SESSIONS
from training_coach.domain.readiness import note as readiness_note
from training_coach.domain.session_times import Timing, minutes
from training_coach.domain.stretching import HOLD_SECONDS, POSITION_SECONDS, RELEASE_SECONDS
from training_coach.services import (
    daily_check,
    guided,
    mobility_flow,
    queue_actions,
    readiness,
    retests,
    session_levels,
    session_times,
    stretching,
    workout_log,
)
from training_coach.services import progress as feedback
from training_coach.services.day_clash import Clash, Refused
from training_coach.services.today import ItemPlan, position

router = APIRouter(prefix="/api/session", tags=["session"])


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _settings_and_day(request: Request) -> tuple[Settings, date]:
    settings: Settings = request.app.state.settings
    return settings, local_date(datetime.now(UTC), settings.tz)


UNITS: dict[ExerciseKind, Literal["reps", "seconds", "minutes"]] = {
    ExerciseKind.REPS: "reps",
    ExerciseKind.SECONDS: "seconds",
    ExerciseKind.DURATION_MIN: "minutes",
}


class MoveView(BaseModel):
    """One movement of the guided mobility flow (ADR-0062)."""

    slug: str  # also names its picture
    name: str
    seconds: int  # per side when per_side
    per_side: bool
    target: str
    start: str
    end: str
    cues: list[str]
    breathing: str
    easier: str
    pacing: str


class FlowView(BaseModel):
    seconds: int  # the whole flow, both sides counted
    safety: str
    moves: list[MoveView]


def flow_view(flow: Flow | None) -> FlowView | None:
    if flow is None:
        return None
    return FlowView(
        seconds=flow.seconds,
        safety=flow.safety,
        moves=[
            MoveView(
                slug=m.slug,
                name=m.name,
                seconds=m.seconds,
                per_side=m.per_side,
                target=m.target,
                start=m.start,
                end=m.end,
                cues=list(m.cues),
                breathing=m.breathing,
                easier=m.easier,
                pacing=m.pacing,
            )
            for m in flow.moves
        ],
    )


class ItemMuscleView(BaseModel):
    muscle: str  # domain/muscles.py's names
    weight: float  # 1 prime mover, 0.5 synergist, 0.25 a small part (ADR-0064)


class NextWeightView(BaseModel):
    """Every set reached the top of the range last time: this weight next, with these targets
    (the bottom of the range). A suggestion the person taps to take (ADR-0072)."""

    kg: float
    targets: list[int]


class LoadView(BaseModel):
    """A loaded step (ADR-0072): - and + move the weight by ``increment``, or at home through
    the weights ``owned``; each set starts at its ``kg``, the same set's weight last time when
    ``carried``, else the kit's first weight (at home, the lightest owned)."""

    # dumbbells: the weight of one; backpack: the weight a vest or backpack adds
    kit: Literal["barbell", "dumbbells", "machine", "backpack"]
    increment: float
    kg: list[float]  # one per planned set
    carried: bool
    suggested: NextWeightView | None = None
    owned: list[float] | None = None  # at home, the weights owned for this kit, lightest first
    unlock: str | None = None  # ready for more at home, none heavier owned: "18 kg dumbbells"


def load_view(load: Load | None) -> LoadView | None:
    if load is None:
        return None
    up = load.suggested
    return LoadView(
        kit=load.kit.value,
        increment=load.increment,
        kg=list(load.kg),
        carried=load.carried,
        suggested=NextWeightView(kg=up.kg, targets=list(up.targets)) if up is not None else None,
        owned=list(load.owned) if load.owned is not None else None,
        unlock=load.unlock,
    )


class LevelView(BaseModel):
    """One step of an exercise's ladder, to change the level on the set screen (ADR-0080)."""

    id: int
    name: str
    cue: str | None
    missing: list[str]  # the kit it needs that isn't listed: locked, still choosable (ADR-0071)


class ItemLevelView(BaseModel):
    """Changing the level on the set screen (ADR-0080): the step trained today, whether it was
    chosen for today only, and the exercise's ladder, easiest first."""

    step_id: int
    for_today: bool
    ladder: list[LevelView]


class ItemView(BaseModel):
    slug: str
    name: str
    step: str
    summary: str | None
    cue: str | None
    unit: Literal["reps", "seconds", "minutes"]
    per_side: bool
    pair: int | None
    targets: list[int]
    baseline: bool  # first session at this step (ADR-0034)
    muscles: list[ItemMuscleView]  # what it works, the most worked first; [] for cardio, mobility
    parts: list[str]  # muscle parts it reaches: "triceps long head", "rectus femoris"
    flow: FlowView | None = None  # guided one movement at a time (ADR-0062)
    load: LoadView | None = None  # a loaded step: the set screen records a weight (ADR-0072)
    level: ItemLevelView | None = None  # empty for an exercise with one step: none to change


def muscle_views(item: ItemPlan) -> list[ItemMuscleView]:
    return [ItemMuscleView(muscle=m, weight=w) for m, w in item.muscles]


class SetView(BaseModel):
    item: int  # index into items
    set_no: int
    target: int
    rest_seconds: int = 0  # the rest after this set; 0 after the last (ADR-0065)
    switch: bool = False  # that rest is the move to the other exercise of a pair


class BlockView(BaseModel):
    kind: Literal["strength", "hypertrophy"]
    week: int


class LengthView(BaseModel):
    """Short on time today (ADR-0082): the minutes chosen (empty: as planned), the ones on
    offer, the exercises pinned with Keep, about how long as planned, what the chosen length
    drops (exercise names, in the order they went) and the warm-up it keeps: the 5-minute one,
    ramp sets (easy sets of the first exercise, not logged) or none. ``shortest``: the
    chosen minutes can't be met and this is the shortest the session gets. ``fixed``: a set is
    kept, so the length no longer changes."""

    minutes: int | None
    options: list[int]
    keep: list[str]
    planned_minutes: int
    dropped: list[str]
    warm_up: Literal["none", "full", "ramp"]
    shortest: int | None
    fixed: bool


def length_view(plan: guided.Guided) -> LengthView | None:
    found = plan.length
    if found is None:
        return None
    trimmed = found.trimmed
    return LengthView(
        minutes=found.minutes,
        options=list(guided.OPTIONS),
        keep=list(found.keep),
        planned_minutes=found.planned,
        dropped=[plan.items[i].exercise for i in trimmed.dropped],
        warm_up=trimmed.warm_up.value,
        shortest=trimmed.shortest,
        fixed=found.fixed,
    )


class GuidedView(BaseModel):
    day: str  # ISO date, local
    template_id: int
    name: str
    focus: str
    kind: Literal["strength", "conditioning", "recovery"]
    warm_up: bool
    block: BlockView | None
    minutes: int  # the estimate at today's length, warm-up included
    usual_minutes: int | None = None  # how long this session usually takes (ADR-0061)
    rest_seconds: int  # the rest after a pair, for pages from before ADR-0065
    items: list[ItemView]
    order: list[SetView]
    # What's left of a conditioning session once its cardio is logged (ADR-0066): offered
    # "after your run", saved into that day's workout.
    after_run: bool = False
    # Where it is done, and so which version (ADR-0071); ``place_choice``: show Home | Gym.
    place: Place = Place.HOME
    place_choice: bool = False
    # Short on time today (ADR-0082); empty for a session that always runs as planned.
    length: LengthView | None = None


class DoneView(BaseModel):
    """A confirmed set; ``right`` only for one-sided exercises (empty: same as left).
    ``started_at`` and ``done_at``: when the set's screen appeared and when it was confirmed,
    from the phone's clock (ADR-0061); kept only when both are there and plausible."""

    item: int = Field(ge=0, le=100)
    set_no: int = Field(ge=1, le=50)
    left: int = Field(ge=0, le=3600)
    right: int | None = Field(default=None, ge=0, le=3600)
    started_at: AwareDatetime | None = None
    done_at: AwareDatetime | None = None
    load_kg: float | None = Field(default=None, gt=0, le=MAX_KG)  # a loaded step's weight


class ProgressView(BaseModel):
    template_id: int
    position: int
    first: list[int]
    sets: list[DoneView]
    saved: bool
    revision: int  # send it back with the next PUT


class TestDayDueView(BaseModel):
    day: int
    name: str
    tests: list[str]


def test_day_view(found: retests.TestDayDue | None) -> TestDayDueView | None:
    if found is None:
        return None
    return TestDayDueView(day=found.day, name=found.name, tests=list(found.tests))


class QueuedView(BaseModel):
    template_id: int
    name: str


class TodayView(BaseModel):
    """``session`` is empty when nothing planned is left today (done or rested); ``progress``
    is where the person left off, to resume."""

    session: GuidedView | None
    # The queue's session, when today's is another one picked for today (ADR-0022): still next.
    planned: QueuedView | None = None
    progress: ProgressView | None = None
    test_day: TestDayDueView | None = None  # due today, in front of the session (ADR-0038)
    # On a hard day (HIIT or a test day): answer the readiness questions, or see a doctor first
    # (ADR-0046). Advice only.
    readiness_note: str | None = None
    # Today's daily check, once answered (ADR-0053): "Slept OK, ...: go lighter today".
    daily_check: str | None = None


class KeepBody(BaseModel):
    template_id: int  # the session the browser shows: a different one now is a conflict
    place: Place  # the version it shows (ADR-0071): another one now is too
    revision: int = Field(default=0, ge=0)  # the kept revision this browser saw; 0: none
    position: int = Field(ge=0, le=500)
    first: list[int] = Field(default_factory=list, max_length=10)
    sets: list[DoneView] = Field(default_factory=list, max_length=200)


class SaveBody(ClashReply):
    day: date | None = None  # empty: today; an earlier day saves one left unsaved


class StepDownView(BaseModel):
    """The bottom of the range out of reach twice (ADR-0084): a suggestion, nothing changes
    without a tap. ``below`` is the step to suggest; None at a ladder's first step (or with
    every step below locked by the kit), when ``easier`` names the catalogue's level 1-2
    exercises for the same muscles, if any."""

    step_id: int  # the step judged, sent back by Step down and Not yet
    below: str | None
    easier: list[str]


def step_down_view(found: feedback.Down | None) -> StepDownView | None:
    if found is None:
        return None
    return StepDownView(step_id=found.step_id, below=found.below, easier=list(found.easier))


class EarnedView(BaseModel):
    exercise: str
    unit: Literal["reps", "seconds", "minutes"]
    best_set: int | None
    total: int | None
    next_step: str | None  # ready to move up to this
    slug: str  # the exercise's, for the link to its ladder on /plan (ADR-0075)
    # The rule met with no step to move to, said once per step (ADR-0078); ``unlock`` then says
    # what opens the next one when the kit is what's missing (ADR-0071).
    at_top: bool
    unlock: str | None
    load_kg: float | None  # the session's weight, which its bests were counted at (ADR-0072)
    step_down: StepDownView | None  # the bottom of the range out of reach twice (ADR-0084)


class TimingView(BaseModel):
    """How long a timed session took, in whole minutes (ADR-0061): ``minutes`` is its sets and
    the rests between them; breaks (gaps over 10 minutes) are counted apart."""

    minutes: int
    on_sets: int
    resting: int
    breaks: int


def timing_view(found: Timing | None) -> TimingView | None:
    if found is None:
        return None
    return TimingView(
        minutes=minutes(found.total),
        on_sets=minutes(found.on_sets),
        resting=minutes(found.resting),
        breaks=found.breaks,
    )


class LevelDoneView(BaseModel):
    """An exercise whose level changed during the session, and the steps its sets were done
    at, in order (ADR-0080)."""

    exercise: str
    steps: list[str]


class SavedView(BaseModel):
    workout_id: int
    already_saved: bool
    next_session: str | None
    earned: list[EarnedView]
    stretching: bool  # offered after a resistance session (ADR-0032)
    timing: TimingView | None = None  # empty when the sets weren't timed
    levels: list[LevelDoneView] = Field(default_factory=list)


class PendingView(BaseModel):
    day: date
    session: str
    sets: int


@router.get("/today", response_model=TodayView)
def today(request: Request, user: Owner) -> TodayView:
    """Today's session in work order, with any pairs swapped as kept in the progress: a swap
    or un-swap is a PUT to /progress, so the server is the one place it lives."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        return today_view(session, on, settings)


def today_view(session: Session, on: date, settings: Settings) -> TodayView:
    """What GET /today answers, inside the caller's transaction (also after a change to today)."""
    kept = guided.kept(session, on)
    plan = guided.today(session, on, settings.tz)
    test_day = test_day_view(retests.due(session, on, settings.tz))
    current = readiness.current(session, datetime.now(UTC))
    if (
        plan is not None
        and kept is not None
        and (
            kept.template_id != plan.template_id
            or kept.place is not plan.place  # kept in the other version (ADR-0071)
            or kept.after_run != plan.after_run
            or (plan.after_run and kept.saved)  # a block saved short: what's left starts afresh
        )
    ):
        kept = None  # kept for a session that's no longer today's: its swaps don't apply
    if plan is not None and kept is not None and kept.first:
        plan = guided.today(session, on, settings.tz, set(kept.first))
    hard = test_day is not None or (plan is not None and plan.slug in HARD_SESSIONS)
    caution = readiness_note(current, hard)
    answers = daily_check.on(session, on)
    daily = daily_summary(answers) if answers is not None else None
    if plan is None:
        return TodayView(session=None, test_day=test_day, readiness_note=caution, daily_check=daily)
    ladders = session_levels.ladders(session, (i.slug for i in plan.items))
    today_only = session_levels.today_only(session, dict(kept.steps) if kept is not None else {})
    queue = position(session)
    planned = None
    if queue is not None and queue.pointer != plan.template_id:
        name = dict(queue_actions.choices(session)).get(queue.pointer)
        planned = QueuedView(template_id=queue.pointer, name=name) if name else None
    progress = None
    if kept is not None:
        progress = ProgressView(
            template_id=kept.template_id,
            position=kept.position,
            first=list(kept.first),
            sets=[DoneView(**vars(d)) for d in kept.sets],
            saved=kept.saved,
            revision=kept.revision,
        )
    return TodayView(
        planned=planned,
        progress=progress,
        test_day=test_day,
        readiness_note=caution,
        daily_check=daily,
        session=GuidedView(
            day=plan.day.isoformat(),
            template_id=plan.template_id,
            name=plan.name,
            focus=plan.focus,
            kind=plan.kind,
            warm_up=plan.warm_up,
            block=BlockView(kind=plan.block.kind.value, week=plan.block.week)
            if plan.block is not None
            else None,
            minutes=plan.minutes,
            usual_minutes=None  # the whole session's, not the block's (ADR-0066)
            if plan.after_run
            else session_times.usual_minutes(session, plan.template_id),
            rest_seconds=plan.rest_seconds,
            items=[
                ItemView(
                    slug=i.slug,
                    name=i.exercise,
                    step=i.step,
                    summary=i.summary,
                    cue=i.cue,
                    unit=UNITS[i.kind],
                    per_side=i.per_side,
                    pair=i.pair,
                    targets=list(i.targets),
                    baseline=i.baseline,
                    muscles=muscle_views(i),
                    parts=list(i.parts),
                    flow=flow_view(mobility_flow.flow_for(i.slug)),
                    load=load_view(i.load),
                    level=ItemLevelView(
                        step_id=i.step_id,
                        for_today=i.slug in today_only,
                        ladder=[
                            LevelView(id=r.id, name=r.name, cue=r.cue, missing=list(r.missing))
                            for r in ladders[i.slug]
                        ],
                    )
                    if i.slug in ladders
                    else None,
                )
                for i in plan.items
            ],
            order=[
                SetView(
                    item=s.item,
                    set_no=s.set_no,
                    target=s.target,
                    rest_seconds=s.rest.seconds,
                    switch=s.rest.switch,
                )
                for s in plan.order
            ],
            after_run=plan.after_run,
            place=plan.place,
            place_choice=plan.switch,
            length=length_view(plan),
        ),
    )


class KeptView(BaseModel):
    revision: int


@router.put("/progress", response_model=KeptView)
def keep(body: KeepBody, request: Request, user: Owner) -> KeptView:
    """Keep where the person is in today's session, so it resumes on any device. 409 when
    another device moved on since this browser's ``revision`` (reload and carry on)."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        plan = guided.today(session, on, settings.tz, set(body.first))
        if plan is None or plan.template_id != body.template_id or body.place is not plan.place:
            raise HTTPException(status.HTTP_409_CONFLICT, "today's session has changed")
        sets = [guided.Done(**d.model_dump()) for d in body.sets]
        result = guided.keep(
            session, plan, body.revision, body.position, body.first, sets, now=datetime.now(UTC)
        )
    if result == guided.STALE:
        raise HTTPException(status.HTTP_409_CONFLICT, result)
    if isinstance(result, str):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, result)
    return KeptView(revision=result)


class PlaceBody(BaseModel):
    place: Place
    confirm: bool = False  # drop the sets kept for the version shown


class PlaceAsk(BaseModel):
    """The answer to a switch with sets kept: ask first, then send it again with confirm."""

    kept_sets: int


@router.put(
    "/place",
    response_model=TodayView,
    responses={status.HTTP_409_CONFLICT: {"model": PlaceAsk}},
)
def choose_place(body: PlaceBody, request: Request, user: Owner) -> TodayView | JSONResponse:
    """Do today's session at home or at the gym (ADR-0071): the person's switch, never the
    app's. 409 with ``kept_sets`` at the top of the body (a PlaceAsk, as the API types say) when
    sets are kept for the version shown (ask, then confirm), or with a ``detail`` message when
    today has no choice to make."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        plan = guided.today(session, on, settings.tz)
        if plan is None or not plan.switch:
            raise HTTPException(status.HTTP_409_CONFLICT, "today's session has one place")
        kept = guided.switch(session, plan, body.place, body.confirm)
        if kept is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT, content=PlaceAsk(kept_sets=kept).model_dump()
            )
        return today_view(session, on, settings)


class LengthBody(BaseModel):
    """Short on time today (ADR-0082): as planned (empty) or 40, 30 or 20 minutes, never
    dropping the exercises pinned with ``keep`` (slugs)."""

    template_id: int  # the session the browser shows: a different one now is a conflict
    place: Place  # the version it shows (ADR-0071): another one now is too
    revision: int = Field(default=0, ge=0)  # the kept revision this browser saw; 0: none
    first: list[int] = Field(default_factory=list, max_length=10)
    minutes: Literal[40, 30, 20] | None = None
    keep: list[Annotated[str, Field(max_length=64)]] = Field(default_factory=list, max_length=30)


@router.put("/length", response_model=TodayView)
def choose_length(body: LengthBody, request: Request, user: Owner) -> TodayView:
    """Run today's session shorter, or as planned again (ADR-0082): the session at that
    length. 409 when the session changed, another device moved on since ``revision``
    (reload), or a set is kept already (the length is fixed then); 422 for a session that
    always runs as planned, or a Keep for an exercise it doesn't have."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        plan = guided.today(session, on, settings.tz, set(body.first))
        if plan is None or plan.template_id != body.template_id or body.place is not plan.place:
            raise HTTPException(status.HTTP_409_CONFLICT, "today's session has changed")
        result = guided.choose_length(session, plan, body.revision, body.minutes, body.keep)
        if isinstance(result, int):
            return today_view(session, on, settings)
        # Raised inside the scope, so it rolls back: a refused choice writes nothing.
        if result in (guided.STALE, guided.STARTED, guided.SAVED):
            raise HTTPException(status.HTTP_409_CONFLICT, result)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, result)


@router.post("/save", response_model=SavedView, responses=CLASH)
def save(body: SaveBody, request: Request, user: Owner) -> SavedView:
    """Save the guided session as a workout: today's, or an earlier day's left unsaved. 409
    with what is saved already when that day has its session (ADR-0060)."""
    settings, today = _settings_and_day(request)
    day = body.day or today
    if day > today:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "that day hasn't happened yet")
    with session_scope(_bound(request, user)) as session:
        result = guided.save(session, day, today, settings.tz, resolution(body))
        if isinstance(result, Clash | Refused):
            raise conflict(result)
        if isinstance(result, str):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, result)
        if isinstance(result, workout_log.Stale):
            raise HTTPException(status.HTTP_409_CONFLICT, "today's session has changed")
        earned = (
            []
            if result.already_saved
            else feedback.feedback(session, result.workout_id, settings.tz)
        )
        return SavedView(
            workout_id=result.workout_id,
            already_saved=result.already_saved,
            next_session=workout_log.next_session_name(session),
            earned=[
                EarnedView(
                    exercise=e.exercise,
                    unit=UNITS[e.kind],
                    best_set=e.bests.best_set,
                    total=e.bests.total,
                    next_step=e.next_step,
                    slug=e.slug,
                    at_top=e.note_top,
                    unlock=e.unlock if e.note_top else None,
                    load_kg=e.load_kg,
                    step_down=step_down_view(e.down),
                )
                for e in earned
                if e.bests or e.next_step or e.note_top or e.down
            ],
            stretching=day == today and stretching.offered(session, result.workout_id),
            timing=timing_view(session_times.of_workout(session, result.workout_id)),
            levels=[
                LevelDoneView(exercise=name, steps=list(steps))
                for name, steps in session_levels.done_at(session, day, result.workout_id)
            ],
        )


@router.get("/pending", response_model=list[PendingView])
def pending(request: Request, user: Owner) -> list[PendingView]:
    """Earlier days' guided sessions with sets but never saved, to offer saving them."""
    _, today = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        return [
            PendingView(day=p.day, session=p.session, sets=p.sets)
            for p in guided.pending(session, today)
        ]


class LevelBody(BaseModel):
    """A level chosen on the set screen (ADR-0080): for today only, or from now on."""

    template_id: int  # the session the browser shows: a different one now is a conflict
    revision: int = Field(default=0, ge=0)  # the kept revision this browser saw; 0: none
    first: list[int] = Field(default_factory=list, max_length=10)
    slug: str = Field(max_length=64)
    step_id: int
    scope: session_levels.Scope


class LevelChangedView(BaseModel):
    today: TodayView  # the session with the new step's targets, and the new revision
    # The step needs kit that isn't listed: chosen anyway, the person decides (ADR-0071).
    warning: str | None


@router.put("/level", response_model=LevelChangedView)
def change_level(body: LevelBody, request: Request, user: Owner) -> LevelChangedView:
    """Change an exercise's level during today's session, for today or from now on. 409 when
    the session changed or another device moved on (reload); 422 for a step not on its ladder."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        plan = guided.today(session, on, settings.tz, set(body.first))
        if plan is None or plan.template_id != body.template_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "today's session has changed")
        result = session_levels.change(
            session, plan, body.revision, body.slug, body.step_id, body.scope
        )
        if isinstance(result, session_levels.Changed):
            return LevelChangedView(today=today_view(session, on, settings), warning=result.warning)
        # Raised inside the scope, so it rolls back: a refused change writes nothing, not even
        # the progress it may have started.
        if result == guided.STALE:
            raise HTTPException(status.HTTP_409_CONFLICT, result)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, result)


# ------------------------------------------------------------------ stretching (#135)


class StretchView(BaseModel):
    slug: str  # also names its picture, when there is one
    name: str
    rounds: int  # on each side when per_side
    per_side: bool
    cue: str


class RoutineView(BaseModel):
    """The routine and its timing: each side starts with getting into position, then the
    holds with a release between them; all of it fits in ``minutes`` (ADR-0032 addendum)."""

    session: str
    minutes: int
    hold_seconds: int
    position_seconds: int
    release_seconds: int
    steps: list[StretchView]


class StretchBody(BaseModel):
    minutes: int


class StretchedView(BaseModel):
    logged: bool  # false: this workout already had its stretching


NOT_OFFERED = "no stretching for that workout"


@router.get("/stretching/{workout_id}", response_model=RoutineView)
def stretching_routine(workout_id: int, minutes: int, request: Request, user: Owner) -> RoutineView:
    """The stretches after a saved resistance workout, filling ``minutes`` (ADR-0032)."""
    with session_scope(_bound(request, user)) as session:
        routine = stretching.for_workout(session, workout_id, minutes)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_OFFERED)
    return RoutineView(
        session=routine.session,
        minutes=routine.minutes,
        hold_seconds=HOLD_SECONDS,
        position_seconds=POSITION_SECONDS,
        release_seconds=RELEASE_SECONDS,
        steps=[
            StretchView(
                slug=s.stretch.slug,
                name=s.stretch.name,
                rounds=s.rounds,
                per_side=s.stretch.per_side,
                cue=s.stretch.cue,
            )
            for s in routine.steps
        ],
    )


@router.post("/stretching/{workout_id}", response_model=StretchedView)
def stretching_done(
    workout_id: int, body: StretchBody, request: Request, user: Owner
) -> StretchedView:
    """Log the stretching minutes on the workout, once: the minutes actually done, 1 up to
    the longest choice."""
    with session_scope(_bound(request, user)) as session:
        logged = stretching.log(session, workout_id, body.minutes)
    if logged is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_OFFERED)
    return StretchedView(logged=logged)
