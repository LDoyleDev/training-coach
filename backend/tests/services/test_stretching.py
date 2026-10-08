"""The stretching routine after a session (#98), against the bundled plan."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import SessionTemplate
from training_coach.services import stretching
from training_coach.services.seed import apply_seed, load_plan


def _template(session: Session, slug: str) -> int:
    apply_seed(session, load_plan())
    session.flush()
    return session.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == slug)).one()


def test_legs_works_quads_and_glutes_most(session: Session) -> None:
    worked = stretching.worked(session, _template(session, "legs"))
    assert worked is not None
    assert worked["glutes"] == 16  # jump squat 3, swing 3, split squat 4, pistol 3, RDL 3
    assert worked.most_common(1)[0][0] == "glutes"


def test_legs_stretching_starts_with_the_legs(session: Session) -> None:
    steps = stretching.for_session(session, _template(session, "legs"), 10)
    assert steps is not None
    muscles = set().union(*(s.stretch.muscles for s in steps))
    assert {"glutes", "quads", "hamstrings"} <= muscles
    assert sum(s.seconds for s in steps) <= 600


def test_torso_stretching_starts_with_the_upper_body(session: Session) -> None:
    steps = stretching.for_session(session, _template(session, "torso"), 10)
    assert steps is not None
    assert steps[0].stretch.muscles & {"lats", "upper back", "chest", "triceps"}


def test_every_choice_fits_and_longer_choices_cover_more(session: Session) -> None:
    arms = _template(session, "arms")
    sizes = []
    for minutes in (10, 20, 30):
        steps = stretching.for_session(session, arms, minutes)
        assert steps is not None
        assert sum(s.seconds for s in steps) <= minutes * 60
        sizes.append(len(steps))
    assert sizes == sorted(sizes)
    assert sizes[0] < sizes[-1]


def test_an_unknown_session_has_no_routine(session: Session) -> None:
    assert stretching.for_session(session, 999_999, 10) is None
