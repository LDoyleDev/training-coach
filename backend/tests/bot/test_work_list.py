"""The work-order list (#97) reads back as a log: copy it, put in what you did, send it."""

from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.bot.messages import session_detail_text, work_list
from training_coach.db.models import SessionTemplate
from training_coach.domain.enums import Side
from training_coach.services import workout_log
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.today import session_plan

BERLIN = ZoneInfo("Europe/Berlin")


def _legs(session: Session) -> int:
    apply_seed(session, load_plan())
    session.flush()
    return session.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == "legs")).one()


def test_legs_starts_with_the_first_pair_alternating(session: Session) -> None:
    plan = session_plan(session, _legs(session))
    assert plan is not None
    lines = work_list(plan.items)
    names = [line.split(". ", 1)[1].split(" (")[0] for line in lines[:6]]
    assert names == ["Jump squat", "Tibialis raise"] * 3
    assert lines[6] == ""  # a gap before the next pair


def test_the_list_pasted_back_logs_every_set_in_order(session: Session) -> None:
    plan = session_plan(session, _legs(session))
    assert plan is not None
    pasted = "\n".join(work_list(plan.items))  # the targets, as if every one was hit
    draft = workout_log.draft(session, pasted, date(2026, 10, 8), BERLIN)
    assert draft.problems == ()
    by_slug = {entry.slug: entry.sets for entry in draft.entries}
    assert len(by_slug) == 8
    for item, slug in zip(plan.items, by_slug, strict=True):
        sides = (Side.LEFT, Side.RIGHT) if item.per_side else (Side.BOTH,)
        expected = tuple(
            (n, side, value) for n, value in enumerate(item.targets, start=1) for side in sides
        )
        assert by_slug[slug] == expected, slug


def test_the_whole_start_message_names_the_list_as_the_thing_to_send(session: Session) -> None:
    plan = session_plan(session, _legs(session))
    assert plan is not None
    text = session_detail_text(plan)
    assert text.endswith("Copy the list, put in what you did and send it back to log it.")
    assert "Work down the list, alternating the two exercises of each pair." in text
