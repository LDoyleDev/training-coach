"""The guided session (D1, #117): today's session for the web app, one set at a time.

Which session today is follows the same rule as a typed log (``workout_log.target``): the one
picked today, else the one at the queue's pointer; once a planned session is done or rested
today there is none. Sets come in work order (ADR-0031), with any pair swapped to start with
its second exercise.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from training_coach.domain.blocks import Block
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.work_order import work_order
from training_coach.services import blocks, workout_log
from training_coach.services.today import ItemPlan, session_plan

REST_SECONDS = 60  # after each set, adjustable during the rest (D1)
WARM_UP_MINUTES = 10
SET_SECONDS = 45  # a rough working set, for the time estimate only


@dataclass(frozen=True)
class GuidedSet:
    item: int  # index into items
    set_no: int  # from 1
    target: int


@dataclass(frozen=True)
class Guided:
    day: date
    template_id: int
    name: str
    focus: str
    kind: str  # strength | conditioning | recovery
    warm_up: bool
    block: Block | None
    minutes: int  # about how long, warm-up included
    rest_seconds: int
    items: tuple[ItemPlan, ...]
    order: tuple[GuidedSet, ...]


def _minutes(items: tuple[ItemPlan, ...], warm_up: bool) -> int:
    seconds = 0
    for item in items:
        sides = 2 if item.per_side else 1
        for target in item.targets:
            if item.kind is ExerciseKind.DURATION_MIN:
                seconds += target * 60
            elif item.kind is ExerciseKind.SECONDS:
                seconds += target * sides + REST_SECONDS
            else:
                seconds += SET_SECONDS * sides + REST_SECONDS
    return round(seconds / 60) + (WARM_UP_MINUTES if warm_up else 0)


def today(session: Session, on: date, tz: ZoneInfo, first: Collection[int] = ()) -> Guided | None:
    """Today's session to guide, or None when there is nothing planned left today. ``first``
    holds the pair numbers to start with their second exercise."""
    template = workout_log.target(session, on, tz)
    if template is None:
        return None
    block = blocks.current(session, on, tz)
    plan = session_plan(session, template.id, block)
    assert plan is not None  # noqa: S101 - target() returned this template a moment ago
    groups = work_order([len(i.targets) for i in plan.items], [i.pair for i in plan.items], first)
    order = tuple(
        GuidedSet(item, set_no, plan.items[item].targets[set_no - 1])
        for group in groups
        for item, set_no in group
    )
    warm_up = plan.kind == "strength"
    return Guided(
        day=on,
        template_id=plan.template_id,
        name=plan.name,
        focus=plan.focus,
        kind=plan.kind,
        warm_up=warm_up,
        block=block,
        minutes=_minutes(plan.items, warm_up),
        rest_seconds=REST_SECONDS,
        items=plan.items,
        order=order,
    )
