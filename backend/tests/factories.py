"""Builders for model rows: sensible defaults, override only what a test cares about."""

from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, LadderStep, SessionTemplate, TemplateItem
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.load import LoadKit
from training_coach.services.seed import ItemSeed, PlanSeed, load_plan


def exercise(session: Session, slug: str = "pull-up") -> Exercise:
    row = Exercise(slug=slug, name="Pull-up", kind=ExerciseKind.REPS)
    row.ladder = [
        LadderStep(position=0, name="Negatives"),
        LadderStep(position=1, name="Strict"),
    ]
    session.add(row)
    session.flush()
    return row


def template(session: Session, of: Exercise, position: int = 0) -> SessionTemplate:
    row = SessionTemplate(position=position, slug=f"upper-{position}", name="Upper", focus="x")
    row.items = [TemplateItem(position=0, exercise_id=of.id, sets=4, rep_min=5, rep_max=12)]
    session.add(row)
    session.flush()
    return row


def loads(slug: str, kit: LoadKit) -> dict[tuple[str, str], LoadKit]:
    """Every step of one bundled exercise as if it took load with ``kit`` (ADR-0072): patch it
    over ``blocks._load_kits``."""
    ladder = next(e.ladder for e in load_plan().exercises if e.slug == slug)
    return {(slug, step): kit for step in ladder}


# A no-equipment Legs (ADR-0086): power, quads and hamstrings from steps that need no kit.
AWAY_LEGS = (
    ItemSeed(exercise="jump-squat", sets=3, rep_min=5, rep_max=8, pair=1),
    ItemSeed(exercise="tibialis-raise", sets=3, rep_min=15, rep_max=25, pair=1),
    ItemSeed(
        exercise="bulgarian-split-squat", sets=3, rep_min=8, rep_max=15, per_side=True, pair=2
    ),
    ItemSeed(exercise="hamstring-curl", sets=3, rep_min=6, rep_max=15, pair=2),
)


def plan_with_away(slug: str = "legs", items: tuple[ItemSeed, ...] = AWAY_LEGS) -> PlanSeed:
    """The bundled plan with ``items`` as session ``slug``'s away version (ADR-0086), and no
    away version on the others, so a test doesn't hang on the plan's own."""
    plan = load_plan()
    sessions = [
        s.model_copy(update={"away": list(items) if s.slug == slug else []}) for s in plan.sessions
    ]
    return plan.model_copy(update={"sessions": sessions})
