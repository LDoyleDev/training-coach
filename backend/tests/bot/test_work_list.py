"""The work-order list (#97) reads back as a log: copy it, put in what you did, send it."""

from dataclasses import replace
from datetime import date
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.bot.messages import session_detail_text, work_list
from training_coach.db.models import SessionTemplate
from training_coach.domain.enums import Side
from training_coach.services import workout_log
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.today import ItemPlan, session_plan

BERLIN = ZoneInfo("Europe/Berlin")
NL = chr(10)


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
    assert set(by_slug) == {item.slug for item in plan.items}
    for item in plan.items:  # by name: a pair may start with its second exercise (ADR-0031)
        slug = item.slug
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


@pytest.mark.parametrize(
    "slug", ["legs", "recovery", "torso", "moderate-cardio", "hiit", "arms", "zone2"]
)
def test_every_sessions_list_reads_back_as_its_log(session: Session, slug: str) -> None:
    """Names with a bracketed note ("Moderate cardio (~75-80% effort)") must survive the
    parser dropping brackets (found catching up on a week, #104)."""
    apply_seed(session, load_plan())
    session.flush()
    template = session.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == slug))
    plan = session_plan(session, template.one())
    assert plan is not None
    draft = workout_log.draft(session, NL.join(work_list(plan.items)), date(2026, 10, 8), BERLIN)
    assert draft.problems == ()
    assert len(draft.entries) == len({item.exercise for item in plan.items})


def test_start_says_how_to_do_each_exercise(session: Session) -> None:
    plan = session_plan(session, _legs(session))
    assert plan is not None
    text = session_detail_text(plan)
    assert "How to do them:" in text
    assert "- Jump squat: Squat to about parallel" in text


def _marked(session: Session) -> tuple[ItemPlan, ...]:
    """Legs with the last-set option on (ADR-0084): tibialis and calf raises are marked."""
    plan = session_plan(session, _legs(session))
    assert plan is not None
    return tuple(
        replace(item, last_set_amrap=True)
        if item.slug in ("tibialis-raise", "calf-raise")
        else item
        for item in plan.items
    )


def test_the_last_set_of_as_many_as_you_can_is_marked(session: Session) -> None:
    lines = work_list(_marked(session))
    marked = [line for line in lines if line.endswith(" (last set: as many as you can)")]
    # The third of three tibialis raises and the fourth of four calf raises, nothing else.
    assert [line.split(". ", 1)[0] for line in marked] == ["6", "13"]
    assert marked[0].startswith("6. Tibialis raise (")
    assert marked[0].endswith("): 15 (last set: as many as you can)")
    assert marked[1].endswith("): 12 per side (last set: as many as you can)")


def test_the_marked_list_still_reads_back_as_a_log(session: Session) -> None:
    items = _marked(session)
    draft = workout_log.draft(session, NL.join(work_list(items)), date(2026, 10, 8), BERLIN)
    assert draft.problems == ()
    tibialis = next(e for e in draft.entries if e.slug == "tibialis-raise")
    assert [value for _, _, value in tibialis.sets] == [15, 15, 15]
