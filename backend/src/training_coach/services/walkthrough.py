"""The walk-through (ADR-0092): the one save that makes a new person's plan from what they chose
(``apply``), and its answers, kept only with ``walkthrough`` consent (ADR-0090), one row per
person, replaced by a re-run, and deleted when the consent is withdrawn (``consent.withdraw``).
Callers pass a session bound to the person (ADR-0029), whose consent is the one checked. Health
data: the answers are never logged, and no event holds one."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    PlanVersion,
    WalkthroughAnswers,
    Workout,
)
from training_coach.db.session import bound_user
from training_coach.domain import kit as kit_rules
from training_coach.domain import locks
from training_coach.domain.consent import VERSIONS, Category
from training_coach.domain.enums import Places
from training_coach.domain.kit import Item
from training_coach.domain.step_levels import Mark
from training_coach.domain.walkthrough import (
    AgeBand,
    Answers,
    Effort,
    HowLong,
    Often,
    placement_from_json,
    placement_json,
    placement_problem,
)
from training_coach.services import (
    consent,
    equipment,
    gym_version,
    plan_edit,
    step_locks,
    user_settings,
    users,
)
from training_coach.services.plan_rows import session_in_progress
from training_coach.services.seed import (
    ItemSeed,
    PlanSeed,
    SeedResult,
    StarterSeed,
    sync_sessions,
)

log = structlog.get_logger(__name__)


def kept(session: Session) -> Answers | None:
    """The person's answers, or None when none are kept or the category isn't open to them now
    (a yes to older wording no longer counts, though only a withdrawal erases)."""
    row = session.scalar(select(WalkthroughAnswers))
    if row is None or not _open(session):
        return None
    return Answers(
        age_band=AgeBand(row.age_band) if row.age_band else None,
        often=Often(row.often) if row.often else None,
        effort=Effort(row.effort) if row.effort else None,
        how_long=HowLong(row.how_long) if row.how_long else None,
        chair=row.chair,
        stairs=row.stairs,
        walk=row.walk,
        floor=row.floor,
        weekdays=tuple(row.weekdays),
        placement=placement_from_json(row.placement),
    )


def keep(session: Session, answers: Answers, now: datetime) -> bool:
    """Keep ``answers`` in place of any kept before, if the person has the category open; False,
    keeping nothing, if not."""
    if not _open(session):
        return False
    row = session.scalar(select(WalkthroughAnswers))
    if row is None:
        row = WalkthroughAnswers()
        session.add(row)
    row.version = VERSIONS[Category.WALKTHROUGH]
    row.answered_at = now
    row.age_band = answers.age_band.value if answers.age_band else None
    row.often = answers.often.value if answers.often else None
    row.effort = answers.effort.value if answers.effort else None
    row.how_long = answers.how_long.value if answers.how_long else None
    row.chair, row.stairs, row.walk, row.floor = (
        answers.chair,
        answers.stairs,
        answers.walk,
        answers.floor,
    )
    row.weekdays = sorted(answers.weekdays)
    row.placement = placement_json(answers.placement)
    session.flush()
    log.info("walkthrough.answers_kept")  # never the answers themselves
    return True


def _open(session: Session) -> bool:
    """Whether the person the session is bound to has ``walkthrough`` open: by the session, so
    the consent checked is always the person whose row is read or written (security review)."""
    user_id = bound_user(session)
    if user_id is None:
        raise PermissionError("the walk-through's answers need a session bound to the person")
    return consent.opened(session, user_id, Category.WALKTHROUGH)


# ------------------------------------------------------------------------------- the save

NOTE = "Set up with the walk-through"  # the plan version it makes
PLACED = "level.placed"  # one event per exercise moved; its payload holds no answer
APPLIED = "walkthrough.applied"
CLOSED = "closed"  # a workout is logged: the starter can't be swapped any more (Decided 13)
STALE, IN_PROGRESS = plan_edit.STALE, plan_edit.IN_PROGRESS
MINUTES = (40, 30, 20)  # as Short on time today's (ADR-0082); None: as planned
EXERCISES = (4, 6, 8)  # the ADR-0082 addendum's; None: as planned
START_WITHIN = 6  # days after today: the next week's tapped days (``domain.walkthrough``)


@dataclass(frozen=True)
class Setup:
    """What the person chose, as Save sends it: outcomes, and the answers only with consent."""

    starter: str  # its slug
    steps: Mapping[str, int]  # exercise slug -> the ladder step id it starts on
    starts_on: date
    places: Places = Places.HOME
    kit: Sequence[Item] | None = None  # None: the home kit stays as it is (gym only skips it)
    avoid: frozenset[Mark] = frozenset()
    minutes: int | None = None  # per session; None: as planned
    exercises: int | None = None  # per session; None: as planned
    left_out: frozenset[str] = frozenset()  # exercise slugs taken out of the sessions
    answers: Answers | None = None  # kept only if the category is still open


@dataclass(frozen=True)
class Applied:
    revision: str
    kept: bool  # the answers were kept: sent, and the category still open
    moved: tuple[str, ...] = field(default=())  # exercises placed off the step they were on


def ladders(plan: PlanSeed) -> list[str]:
    """The walk-through's 13 ladders: every exercise of the starters, in the order they first
    come (the tibialis raise is the 4-day's)."""
    found: dict[str, None] = {}
    for starter in plan.starters:
        for planned in starter.sessions:
            found.update((item.exercise, None) for item in planned.items)
    return list(found)


def closed(session: Session) -> bool:
    """A workout is logged: it holds its session, so the starter can't be swapped (Decided 13)."""
    return session.scalar(select(Workout.id).limit(1)) is not None


def apply(
    session: Session, plan: PlanSeed, setup: Setup, draft_of: str, today: date, now: datetime
) -> Applied | str:
    """Make the person's plan from ``setup``, in the caller's one transaction: the starter's
    sessions in place of theirs less the leave-outs, each exercise on its step, the settings and
    kit, the gym version at a gym, the start day, one plan version dated today and, if consent
    is still open, the answers. Returns ``CLOSED``, ``IN_PROGRESS``, ``STALE`` or why it is
    refused, in words, having changed nothing. Never the owner's plan: his session raises."""
    if bound_user(session) in (None, users.OWNER):
        raise PermissionError("the walk-through makes a member's plan, through their session")
    if closed(session):
        return CLOSED
    if session_in_progress(session, today):
        return IN_PROGRESS
    if plan_edit.revision(session) != draft_of:
        return STALE
    starter = next((s for s in plan.starters if s.slug == setup.starter), None)
    if starter is None:
        return f"{setup.starter} isn't a starter."
    if (problem := _problem(session, plan, starter, setup, today)) is not None:
        return problem
    user_settings.update(
        session,
        places=setup.places,
        avoid_floor=Mark.FLOOR in setup.avoid,
        avoid_kneeling=Mark.KNEELING in setup.avoid,
        avoid_impact=Mark.IMPACT in setup.avoid,
        avoid_hanging=Mark.HANGING in setup.avoid,
        avoid_knees=Mark.KNEES in setup.avoid,
        session_minutes=setup.minutes,
        clear_session_minutes=setup.minutes is None,
        session_exercises=setup.exercises,
        clear_session_exercises=setup.exercises is None,
    )
    if setup.kit is not None:
        equipment.save(session, setup.kit, now)
    moved = _place(session, setup.steps)
    _swap(session, starter, setup.left_out)
    if setup.places is not Places.HOME:
        gym_version.write(session, plan, today)  # can't refuse: checked above, from the seed
    state, found = users.plan_state(session), users.settings_row(session)
    assert state is not None  # noqa: S101 - everyone gets one on joining
    assert found is not None  # noqa: S101 - and this
    state.next_template_id = plan_edit.templates(session)[0].id
    state.starts_on, found.set_up_on = setup.starts_on, today
    version = session.scalar(select(PlanVersion).where(PlanVersion.since == today))
    if version is None:
        session.add(PlanVersion(since=today, name=NOTE))
    else:  # "Starting plan" from today, an earlier run or edit today, or the gym version's
        version.name = NOTE
    session.add(Event(kind=APPLIED, payload={"starter": starter.slug}))
    session.flush()
    # Last, after the writes: consent is read again inside this transaction (the security review
    # of #673), so a withdrawal since the route's check keeps nothing.
    kept = setup.answers is not None and keep(session, setup.answers, now)
    session.expire_all()
    log.info("walkthrough.applied", starter=starter.slug, moved=len(moved), kept=kept)
    return Applied(plan_edit.revision(session), kept, moved)


def _problem(
    session: Session, plan: PlanSeed, starter: StarterSeed, setup: Setup, today: date
) -> str | None:
    """Why ``setup`` can't be saved, in words; None when it can."""
    if setup.minutes not in (None, *MINUTES):
        return "Minutes per session are 40, 30 or 20, or as planned."
    if setup.exercises not in (None, *EXERCISES):
        return "Exercises per session are 4, 6 or 8, or as planned."
    if not today <= setup.starts_on <= today + timedelta(days=START_WITHIN):
        return "The plan starts within the next week."
    if setup.kit is not None and (found := kit_rules.problems(setup.kit)) is not None:
        return found
    mine = ladders(plan)
    if not setup.left_out <= set(mine):
        return "Only the starters' exercises can be left out."
    for planned in starter.sessions:
        if all(i.exercise in setup.left_out for i in planned.items):
            return f"{planned.name} needs at least one exercise."
    exercises = {
        e.slug: e for e in session.scalars(select(Exercise).where(Exercise.slug.in_(mine)))
    }
    if setup.answers is not None:
        steps = {slug: [s.id for s in e.ladder] for slug, e in exercises.items()}
        if (found := placement_problem(setup.answers.placement, steps)) is not None:
            return found
    # The locks as they will be once saved: the kit and the avoid switches sent with it; a gym
    # has every kit (ADR-0071), and someone at home or both is judged by their home kit.
    home = setup.kit if setup.kit is not None else equipment.kit(session)
    limits = locks.Limits(None if setup.places is Places.GYM else home, setup.avoid)
    for slug, step_id in setup.steps.items():
        exercise = exercises.get(slug)
        step = next((s for s in exercise.ladder if s.id == step_id), None) if exercise else None
        if exercise is None or step is None:
            return f"{slug}: not a step of the walk-through's ladders."
        asks = step_locks.ladder(exercise)[step.position]
        if step.position and not locks.lock(asks, limits).open:  # the bottom is everyone's
            return f"{exercise.name}: {step.name} is locked, so it can't be where you start."
    return None


def _place(session: Session, steps: Mapping[str, int]) -> tuple[str, ...]:
    """Each exercise on its step, with an event for each one moved; the names of those moved."""
    moved = []
    rows = session.execute(
        select(Exercise, ExerciseState)
        .join(ExerciseState, ExerciseState.exercise_id == Exercise.id)
        .where(Exercise.slug.in_(list(steps)))
        .order_by(Exercise.id)
    ).all()
    for exercise, state in rows:
        to = steps[exercise.slug]
        if state.ladder_step_id == to:
            continue
        payload = {"exercise_id": exercise.id, "from_step_id": state.ladder_step_id}
        session.add(Event(kind=PLACED, payload={**payload, "to_step_id": to}))
        state.ladder_step_id = to
        moved.append(exercise.name)
    return tuple(moved)


def _without(items: Sequence[ItemSeed], left_out: frozenset[str]) -> list[ItemSeed]:
    """The items but the left-out ones; a pair that loses one of its two is no pair (#97)."""
    kept = [i for i in items if i.exercise not in left_out]
    pairs = [i.pair for i in kept]
    return [
        i if i.pair is None or pairs.count(i.pair) == 2 else i.model_copy(update={"pair": None})
        for i in kept
    ]


def _swap(session: Session, starter: StarterSeed, left_out: frozenset[str]) -> None:
    """The person's sessions made the starter's, as the seed starts someone (ADR-0073), less the
    left-out exercises: a session not the starter's goes, so no workout may hold one (``closed``).
    Always from the starter itself, so the plan saved is the one previewed."""
    user, state = bound_user(session), users.plan_state(session)
    assert user is not None  # noqa: S101 - checked by apply
    assert state is not None  # noqa: S101 - everyone gets one on joining
    state.next_template_id, state.queued = None, []
    session.flush()  # before the sessions it pointed at go
    wanted = {s.slug for s in starter.sessions}
    for template in plan_edit.templates(session):
        if template.slug not in wanted:
            session.delete(template)
    session.flush()
    exercises = {e.slug: e for e in session.scalars(select(Exercise))}
    sessions = [
        s.model_copy(
            update={"items": _without(s.items, left_out), "away": _without(s.away, left_out)}
        )
        for s in starter.sessions
    ]
    sync_sessions(session, sessions, user, exercises, SeedResult())
