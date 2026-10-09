"""Web sign-in (ADR-0036): links, sessions, expiry, single use and sign-out."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from training_coach.db.models import LoginLink, WebSession
from training_coach.db.session import ALL_USERS, make_session_factory
from training_coach.services import auth
from training_coach.services.users import OWNER

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def _shared(engine: Engine) -> Session:
    return make_session_factory(engine)()


def _link(engine: Engine, at: datetime = NOW) -> str:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, at)
        bound.commit()
    return token


def test_a_link_signs_in_once_and_the_session_names_its_user(engine: Engine) -> None:
    token = _link(engine)
    with _shared(engine) as shared:
        cookie = auth.redeem_link(shared, token, NOW + timedelta(minutes=9), "Firefox")
        assert cookie is not None
        assert auth.redeem_link(shared, token, NOW + timedelta(minutes=9), "Firefox") is None
        assert auth.session_user(shared, cookie, NOW) == OWNER


def test_a_link_expires_after_ten_minutes(engine: Engine) -> None:
    token = _link(engine)
    with _shared(engine) as shared:
        assert auth.redeem_link(shared, token, NOW + timedelta(minutes=10), "x") is None


def test_unknown_tokens_get_nothing(engine: Engine) -> None:
    with _shared(engine) as shared:
        assert auth.redeem_link(shared, "not-a-real-token-at-all", NOW, "x") is None
        assert auth.session_user(shared, "not-a-real-token-at-all", NOW) is None
        auth.end_session(shared, "not-a-real-token-at-all", NOW)  # harmless


def test_only_hashes_are_stored(engine: Engine) -> None:
    token = _link(engine)
    with _shared(engine) as shared:
        cookie = auth.redeem_link(shared, token, NOW, "x" * 500)
        shared.commit()
        everyone = {ALL_USERS: True}
        stored = [
            *shared.scalars(select(LoginLink.token_hash), execution_options=everyone),
            *shared.scalars(select(WebSession.token_hash), execution_options=everyone),
        ]
        assert token not in stored
        assert cookie not in stored
        assert all(len(h) == 64 for h in stored)
        label = shared.scalars(select(WebSession.label), execution_options=everyone).one()
        assert len(label) == auth.LABEL_LENGTH


def test_a_session_lasts_thirty_days_and_is_renewed_by_use(engine: Engine) -> None:
    with _shared(engine) as shared:
        cookie = auth.redeem_link(shared, _link(engine), NOW, "x")
        assert cookie is not None
        day_29 = NOW + timedelta(days=29)
        assert auth.session_user(shared, cookie, day_29) == OWNER  # renewed from here
        assert auth.session_user(shared, cookie, day_29 + timedelta(days=29)) == OWNER
        assert auth.session_user(shared, cookie, day_29 + timedelta(days=60)) is None


def test_signing_out_ends_the_session_at_once(engine: Engine) -> None:
    with _shared(engine) as shared:
        cookie = auth.redeem_link(shared, _link(engine), NOW, "x")
        assert cookie is not None
        auth.end_session(shared, cookie, NOW)
        assert auth.session_user(shared, cookie, NOW) is None
