"""The /share progress image (ADR-0050)."""

import io
from dataclasses import fields
from datetime import UTC, date, datetime

from PIL import Image
from sqlalchemy.orm import Session

from training_coach.db.models import AiComment, Workout
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import share_card
from training_coach.services.seed import apply_seed, load_plan

TODAY = date(2026, 10, 11)
NOW = datetime(2026, 10, 11, 18, 0, tzinfo=UTC)


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


def test_the_ai_comment_never_reaches_the_card(session: Session) -> None:
    """The weekly AI comment is kept for the web review (ADR-0056), never shared."""
    apply_seed(session, load_plan())
    session.flush()
    session.add(AiComment(week=date(2026, 10, 5), text="Sleep more.", created_at=NOW))
    session.flush()
    card = share_card.facts(session, TODAY)
    assert "Sleep more" not in repr(card)
    assert all(not isinstance(getattr(card, f.name), str) for f in fields(card))


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


def test_the_most_rows_end_above_the_footer() -> None:
    last_row_bottom = share_card.ROWS_TOP + share_card.MAX_EXERCISES * share_card.ROW
    assert last_row_bottom <= share_card.FOOTER_Y - 20
    full = share_card.Card(
        date(2026, 9, 14),
        TODAY,
        1,
        0,
        0,
        0,
        [share_card.Rung(f"Exercise {n}", "Step", 1, 4) for n in range(share_card.MAX_EXERCISES)],
    )
    image = _png(full).convert("RGB")
    # The strip between the last row and the footer is only background.
    band = image.crop((0, last_row_bottom, share_card.SIZE[0], share_card.FOOTER_Y - 5))
    assert band.getcolors() == [(band.width * band.height, (0x1B, 0x20, 0x24))]
