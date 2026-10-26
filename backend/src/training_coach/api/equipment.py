"""My equipment (ADR-0071, builder step 4): the home kit, saved as a whole list, and what an
item would unlock. Owner-only. Until a kit is saved nothing locks, so the list starts empty
and the page asks the person to add their kit."""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain import kit as domain
from training_coach.domain.kit import Item, Resistance
from training_coach.domain.muscles import Kit
from training_coach.services import equipment

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/equipment", tags=["equipment"])


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


class KitItemBody(BaseModel):
    kit: Kit
    kg: float | None = None  # a kettlebell's or dumbbell pair's weight; a vest's "up to"
    min_kg: float | None = None  # adjustable dumbbells: the bottom of the range, kg the top
    resistance: Resistance | None = None  # a band's
    note: str = Field(default="", max_length=domain.NOTE_MAX)  # "two stools"


class KitItemView(KitItemBody):
    label: str  # "16 kg kettlebell"


class KitKindView(BaseModel):
    kit: Kit
    name: str  # "dip bars or two chairs"


class EquipmentView(BaseModel):
    listed: bool  # false until a kit is saved: no step locks until then
    saved_at: datetime | None
    items: list[KitItemView]
    kinds: list[KitKindView]  # everything that can be listed, for "tap to add"


class EquipmentBody(BaseModel):
    items: list[KitItemBody] = Field(max_length=domain.MAX_ITEMS)


class KitUnlockedView(BaseModel):
    exercise: str
    slug: str  # links to its ladder on /plan
    step: str


class KitUnlocksView(BaseModel):
    item: str  # "16 kg kettlebell"
    summary: str  # "16 kg kettlebell: 4 new steps"
    steps: list[KitUnlockedView]


def _item(body: KitItemBody) -> Item:
    return Item(body.kit, body.kg, body.min_kg, body.resistance, body.note.strip())


def _view(session: Session) -> EquipmentView:
    saved = equipment.saved_at(session)
    return EquipmentView(
        listed=saved is not None,
        saved_at=saved,
        items=[
            KitItemView(
                kit=i.kit,
                kg=i.kg,
                min_kg=i.min_kg,
                resistance=i.resistance,
                note=i.note,
                label=domain.label(i),
            )
            for i in equipment.items(session)
        ],
        kinds=[KitKindView(kit=k, name=name) for k, name in domain.NAMES.items()],
    )


@router.get("", response_model=EquipmentView)
def get_equipment(request: Request, user: Owner) -> EquipmentView:
    """The kit as listed; ``listed`` is false until it has been saved once."""
    with session_scope(_bound(request, user)) as session:
        return _view(session)


@router.put("", response_model=EquipmentView)
def put_equipment(body: EquipmentBody, request: Request, user: Owner) -> EquipmentView:
    """Replace the whole kit. An empty list is a kit too: bodyweight only, so every step that
    needs kit locks. Refused whole, with the reason, if any item doesn't fit."""
    with session_scope(_bound(request, user)) as session:
        problem = equipment.save(session, [_item(i) for i in body.items], datetime.now(UTC))
        if problem is not None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
        session.flush()
        view = _view(session)
    log.info("api.equipment_saved", items=len(body.items))
    return view


@router.get("/unlocks", response_model=KitUnlocksView)
def get_unlocks(
    request: Request, user: Owner, add: str = Query(max_length=40, examples=["kettlebell:16"])
) -> KitUnlocksView:
    """What adding one item would open, against the kit as listed: ``kettlebell:16``,
    ``dumbbells:12``, ``dumbbells:2-24``, ``backpack:10``, ``band:light``, ``pull-up bar``."""
    try:
        adding = domain.parse_item(add)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    with session_scope(_bound(request, user)) as session:
        found = equipment.unlocks(session, adding)
    name = domain.label(adding)
    count = f"{len(found)} new step{'' if len(found) == 1 else 's'}" if found else "no new steps"
    return KitUnlocksView(
        item=name,
        summary=f"{name}: {count}",
        steps=[KitUnlockedView(exercise=u.exercise, slug=u.slug, step=u.step) for u in found],
    )
