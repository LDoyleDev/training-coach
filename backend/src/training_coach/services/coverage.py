"""The body map's numbers for one person: their plan's week, counted per muscle at the
ladder step each exercise is trained at (program-builder.md F, step 3). Read-only.

The step matters for the spine warning only: a squat or lunge loads the spine once its step
holds a weight (``muscles.step_stress``). An exercise nobody has started is counted at the
plan's starting step.

A session's home or gym version is counted (ADR-0071): the map shows one place at a time, and a
session with no gym version counts its one version at both.

The map counts per cycle, its rest places included (ADR-0093, Decided 15), and what will run: each
version trimmed to the person's minutes and exercises a session, as the walk-through's preview
does (Decided 16). Empty settings count every version as planned.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, ExerciseState, LadderStep
from training_coach.domain import coverage as domain
from training_coach.domain import cycle as cycle_rules
from training_coach.domain.enums import Place, Places
from training_coach.domain.muscles import step_stress
from training_coach.domain.places import day_place
from training_coach.services import guided, user_settings
from training_coach.services.plan_edit import NEW, Added, Kept, places_for
from training_coach.services.plan_rows import (
    PlannedItem,
    PlannedSession,
    planned_sessions,
    with_draft,
)
from training_coach.services.seed import ExerciseSeed, bundled_plan
from training_coach.services.today import ItemPlan


def trained_steps(session: Session) -> dict[str, str]:
    """Exercise slug -> the name of the step this person is on, for exercises they've started."""
    return dict(
        session.execute(
            select(Exercise.slug, LadderStep.name)
            .join(ExerciseState, ExerciseState.exercise_id == Exercise.id)
            .join(LadderStep, LadderStep.id == ExerciseState.ladder_step_id)
        ).all()
    )


def map_place(session: Session) -> tuple[Places, Place]:
    """Where the person trains, and the place the map starts at: the day's place, so someone at
    both sees the one last chosen on Today's switch."""
    prefs = user_settings.load(session)
    return prefs.places, day_place(prefs.places, prefs.place)


ADDS = 4  # exercises named under a muscle on the map


def would_add(found: domain.Coverage, place: Place) -> dict[str, list[str]]:
    """Per muscle, exercises that would add to it (program-builder.md F): ones that can be done at
    ``place`` and train it most, not already counted for it this week; a lengthened-position pick
    first (Decided 5), then by name."""
    catalogue = [e for e in bundled_plan().exercises if not e.retired and place in places_for(e)]
    out: dict[str, list[str]] = {}
    for m in found.muscles:
        counted = {s.exercise for s in m.sources}
        picks = [e for e in catalogue if e.muscles.get(m.muscle) == 1 and e.name not in counted]
        picks.sort(key=lambda e: (not e.lengthened, e.name))
        out[m.muscle] = [e.name for e in picks[:ADDS]]
    return out


@dataclass(frozen=True)
class CountedAt:
    """What a session is trimmed to on the map: the person's settings (ADR-0082)."""

    minutes: int | None = None  # a session; None: as planned
    exercises: int | None = None  # a session; None: as planned


def counted_at(session: Session) -> CountedAt:
    prefs = user_settings.load(session)
    return CountedAt(prefs.session_minutes, prefs.session_exercises)


def _run(
    items: Sequence[PlannedItem], exercises: Mapping[str, ExerciseSeed], kind: str, at: CountedAt
) -> tuple[tuple[PlannedItem, ...], int]:
    """The sets that will run and about how long, at the bottom of each range (where a new step
    starts): trimmed to ``at`` as ``guided.fitted`` previews a session, else as planned."""
    plans = tuple(
        ItemPlan(
            exercise=exercises[i.exercise].name,
            kind=exercises[i.exercise].kind,
            step="",
            cue=None,
            per_side=i.per_side,
            targets=(i.rep_min,) * i.sets,
            pair=i.pair,
            slug=i.exercise,
        )
        for i in items
    )
    trimmed = None
    if at.minutes is not None or at.exercises is not None:
        trimmed = guided.fitted(plans, kind, at.minutes, at.exercises)
    if trimmed is None:
        return tuple(items), guided.planned_minutes(plans, warm_up=kind == "strength")
    kept = (replace(i, sets=n) for i, n in zip(items, trimmed.sets, strict=True))
    return tuple(i for i in kept if i.sets), trimmed.minutes


def drafted_cycle(session: Session, cycle: Sequence[Kept | Added]) -> list[PlannedSession]:
    """The person's sessions as a cycle draft would make them (ADR-0093): in its order, with its
    names, kinds and rest places, a session it leaves out gone and a new one named ``new:<key>``
    (as its draft versions name it), empty or with its copy's versions. The map draws what it
    can: an entry naming no session of theirs, or one already drawn, is left out; Save refuses
    it."""
    mine = {s.slug: s for s in planned_sessions(session)}
    found: list[PlannedSession] = []
    for entry in cycle:
        slug = entry.slug if isinstance(entry, Kept) else NEW + entry.key
        source = mine.get(entry.slug if isinstance(entry, Kept) else entry.copy_of or "")
        if any(s.slug == slug for s in found) or (isinstance(entry, Kept) and source is None):
            continue
        if source is None:
            source = PlannedSession(0, slug, entry.name, "", entry.kind, False, (), ())
        found.append(
            replace(
                source,
                position=len(found),
                slug=slug,
                name=entry.name,
                kind=entry.kind,
                rest_after=entry.rest_after,
            )
        )
    return found


def plan_coverage(
    session: Session,
    place: Place = Place.HOME,
    draft: Mapping[tuple[str, Place], Sequence[PlannedItem]] | None = None,
    *,
    sessions: Sequence[PlannedSession] | None = None,
    steps: Mapping[str, str] | None = None,
    cycle_days: int | None = None,
    counted: CountedAt | None = None,
) -> domain.Coverage:
    """The cycle with each session's version at ``place``, and with ``draft``'s versions in place
    of the saved ones, for the map as a plan is edited (program-builder.md F). ``sessions`` in
    place of the whole plan and ``steps`` (slug -> step name) over the person's own: a plan not
    saved yet, as the walk-through previews it (ADR-0092). Each version is trimmed to
    ``counted`` (None: as planned). The bands are stretched to ``cycle_days``, by default the
    cycle's own days (ADR-0093, Decided 15). Nothing is saved."""
    exercises = {e.slug: e for e in bundled_plan().exercises}
    steps = {**trained_steps(session), **(steps or {})}
    week = []
    mine = planned_sessions(session) if sessions is None else list(sessions)
    drafted = with_draft(mine, draft or {})
    for planned in drafted:
        at = Place.GYM if place is Place.GYM and planned.gym else Place.HOME
        items = []
        planned_version = planned.gym if at is Place.GYM else planned.items
        version, minutes = _run(planned_version, exercises, planned.kind, counted or CountedAt())
        for item in version:
            ex = exercises[item.exercise]
            step = steps.get(ex.slug, ex.ladder[min(ex.start, len(ex.ladder) - 1)])
            items.append(
                domain.Item(
                    exercise=ex.name,
                    sets=item.sets,
                    muscles=dict(ex.muscles),
                    parts=frozenset(ex.parts),
                    stress=frozenset(step_stress(ex.stress, ex.pattern, ex.needs.get(step, []))),
                    pattern=ex.pattern,
                )
            )
        week.append(
            domain.Day(
                planned.name,
                items,
                slug=planned.slug,
                place=at,
                minutes=minutes,
                rest_after=planned.rest_after,
            )
        )
    if cycle_days is None:
        slots = [cycle_rules.Slot(s.slug, s.rest_after) for s in drafted]
        cycle_days = cycle_rules.days(slots) or domain.WEEK  # no sessions: a week of nothing
    return domain.coverage(week, cycle_days)
