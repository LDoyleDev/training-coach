"""Consent per category (ADR-0090): a record of every yes and withdrawal, a member's category open
only after a yes, and a withdrawal erasing that category's data, nobody else's."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import Engine, func, select

from training_coach.db.models import (
    Consent,
    DailyCheck,
    Event,
    HealthDay,
    IngestKey,
    LogProposal,
    McpConnection,
    Measurement,
    OAuthClient,
    User,
    UserSettings,
    Workout,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.consent import Answer, Category
from training_coach.services import consent, users

MEMBER = 2
NOW = datetime(2026, 11, 8, 9, tzinfo=UTC)
DAY = date(2026, 11, 7)


@pytest.fixture
def people(engine: Engine) -> Engine:
    """The owner and a member, each with data in every category."""
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=MEMBER, role=users.MEMBER))
    for person in (users.OWNER, MEMBER):
        with session_scope(make_session_factory(engine, user_id=person)) as theirs:
            theirs.add(Measurement(local_date=DAY, kind="waist", tenths=800))
            theirs.add(UserSettings(height_cm=180, max_hr=190))
            theirs.add(
                DailyCheck(
                    local_date=DAY, sleep="good", soreness="none", energy="high", answered_at=NOW
                )
            )
            theirs.add(HealthDay(local_date=DAY, steps=9000, resting_hr=55))
            theirs.add(IngestKey(key_hash=f"{person:064d}"))
            theirs.add(
                Workout(local_date=DAY, status="done", activity="run", avg_hr=140, max_hr=170)
            )
    return engine


def _count(engine: Engine, user: int, model: type) -> int:
    with session_scope(make_session_factory(engine, user_id=user)) as theirs:
        return theirs.scalar(select(func.count()).select_from(model)) or 0


def test_a_members_category_opens_with_a_yes_and_closes_with_a_withdrawal(people: Engine) -> None:
    with session_scope(make_session_factory(people, user_id=MEMBER)) as theirs:
        assert not consent.opened(theirs, MEMBER, Category.BODY)
        consent.give(theirs, Category.BODY, NOW)
        assert consent.opened(theirs, MEMBER, Category.BODY)
        assert not consent.opened(theirs, MEMBER, Category.BAND)
        consent.withdraw(theirs, Category.BODY, NOW)
        assert not consent.opened(theirs, MEMBER, Category.BODY)
        rows = theirs.scalars(select(Consent).order_by(Consent.id)).all()
        assert [(r.category, r.answer, r.version) for r in rows] == [
            ("body", Answer.GIVEN, 1),
            ("body", Answer.WITHDRAWN, 1),
        ]
        kinds = theirs.scalars(select(Event.kind).where(Event.kind.like("consent.%"))).all()
        assert kinds == ["consent.given", "consent.withdrawn"]


def test_the_owner_is_never_asked(people: Engine) -> None:
    with session_scope(make_session_factory(people, user_id=users.OWNER)) as theirs:
        assert all(consent.opened(theirs, users.OWNER, c) for c in Category)


def test_withdrawing_body_erases_measurements_and_body_settings_only(people: Engine) -> None:
    with session_scope(make_session_factory(people, user_id=MEMBER)) as theirs:
        consent.give(theirs, Category.BODY, NOW)
        consent.withdraw(theirs, Category.BODY, NOW)
    assert _count(people, MEMBER, Measurement) == 0
    assert _count(people, MEMBER, DailyCheck) == 1  # another category
    assert _count(people, users.OWNER, Measurement) == 1  # another person
    with session_scope(make_session_factory(people, user_id=MEMBER)) as theirs:
        found = theirs.scalars(select(UserSettings)).one()
        assert (found.height_cm, found.body_fat_estimate, found.max_hr) == (None, "off", 190)


def test_withdrawing_the_daily_check_erases_it(people: Engine) -> None:
    with session_scope(make_session_factory(people, user_id=MEMBER)) as theirs:
        consent.withdraw(theirs, Category.DAILY_CHECK, NOW)
    assert _count(people, MEMBER, DailyCheck) == 0
    assert _count(people, users.OWNER, DailyCheck) == 1


def test_withdrawing_band_erases_band_data_and_heart_rate_but_keeps_the_workout(
    people: Engine,
) -> None:
    with session_scope(make_session_factory(people, user_id=MEMBER)) as theirs:
        consent.withdraw(theirs, Category.BAND, NOW)
    assert _count(people, MEMBER, HealthDay) == 0
    assert _count(people, MEMBER, IngestKey) == 0
    assert _count(people, users.OWNER, HealthDay) == 1
    with session_scope(make_session_factory(people, user_id=MEMBER)) as theirs:
        workout = theirs.scalars(select(Workout)).one()
        assert (workout.avg_hr, workout.max_hr) == (None, None)
        assert theirs.scalars(select(UserSettings)).one().max_hr is None
    with session_scope(make_session_factory(people, user_id=users.OWNER)) as owners:
        assert owners.scalars(select(Workout)).one().avg_hr == 140


def test_a_withdrawal_counts_even_when_the_clock_stepped_back(people: Engine) -> None:
    with session_scope(make_session_factory(people, user_id=MEMBER)) as theirs:
        consent.give(theirs, Category.BODY, NOW + timedelta(hours=1))
        consent.withdraw(theirs, Category.BODY, NOW)  # written later, stamped earlier
        assert not consent.opened(theirs, MEMBER, Category.BODY)


def test_withdrawing_body_deletes_an_ai_apps_body_proposals_even_saved(people: Engine) -> None:
    with session_scope(make_session_factory(people)) as shared:
        app = OAuthClient(
            client_id="app", name="An app", redirect_uris=[], client_hash="h" * 64, expires_at=NOW
        )
        shared.add(app)
        shared.flush()
        app_id = app.id
    with session_scope(make_session_factory(people, user_id=MEMBER)) as theirs:
        connection = McpConnection(
            client_id=app_id, client_name="An app", redirect_uri="x", scopes=[], ends_at=NOW
        )
        theirs.add(connection)
        theirs.flush()
        for status, token in (("saved", "a" * 32), ("pending", "b" * 32)):
            theirs.add(
                LogProposal(
                    connection_id=connection.id,
                    token=token,
                    kind="body",
                    local_date=DAY,
                    payload={"waist": 80},
                    summary="Waist 80 cm",
                    status=status,
                    expires_at=NOW,
                )
            )
        theirs.add(
            LogProposal(
                connection_id=connection.id,
                token="c" * 32,
                kind="strength",
                local_date=DAY,
                payload={},
                summary="Squat",
                status="saved",
                expires_at=NOW,
            )
        )
    with session_scope(make_session_factory(people, user_id=MEMBER)) as theirs:
        consent.withdraw(theirs, Category.BODY, NOW)
        assert theirs.scalars(select(LogProposal.kind)).all() == ["strength"]
