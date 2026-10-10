"""The /share progress image (ADR-0050)."""

import io
from datetime import date

from PIL import Image
from sqlalchemy.orm import Session

from training_coach.db.models import Workout
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import share_card
from training_coach.services.seed import apply_seed, load_plan

TODAY = date(2026, 10, 11)


def test_facts_count_the_last_four_weeks_only(session: Session) -> None:
    apply_seed(session, load_plan())
    session.flush()
    for day, status in [
        (date(2026, 10, 10), WorkoutStatus.DONE),
        (date(2026, 9, 14), WorkoutStatus.DONE),  # the first of the 28 days
        (date(2026, 9, 13), WorkoutStatus.DONE),  # one day too early
        (date(2026, 10, 9), WorkoutStatus.SKIPPED),
    ]:
        session.add(Workout(local_date=day, status=status, template_id=1))
    session.add(Workout(local_date=TODAY, status=WorkoutStatus.DONE, template_id=None))
    session.flush()
    card = share_card.facts(session, TODAY)
    assert (card.start, card.end) == (date(2026, 9, 14), TODAY)
    assert (card.sessions, card.extras) == (2, 1)
    assert card.rungs  # the plan's exercises, each on its ladder
    assert all(1 <= r.number <= r.of for r in card.rungs)
    assert len(card.rungs) <= share_card.MAX_EXERCISES


def _png(card: share_card.Card) -> Image.Image:
    data = share_card.render(card)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return Image.open(io.BytesIO(data))


def test_render_draws_a_phone_sized_png() -> None:
    card = share_card.Card(
        date(2026, 9, 14),
        TODAY,
        sessions=19,
        extras=2,
        zone2=310,
        moderate=95,
        rungs=[
            share_card.Rung("Pull-up", "Strict pull-up", 3, 5),
            share_card.Rung("A very long exercise name " * 4, "A long step name " * 4, 1, 1),
        ],
    )
    assert _png(card).size == share_card.SIZE


def test_render_with_nothing_logged() -> None:
    empty = share_card.Card(date(2026, 9, 14), TODAY, 0, 0, 0, 0, [])
    assert _png(empty).size == share_card.SIZE
