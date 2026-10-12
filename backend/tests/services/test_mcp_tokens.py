"""Connections, codes and tokens for "Connect my AI" (ADR-0047 C, mcp-threat-model.md M1, M6,
M12; requirements 2, 3, 7 and 19)."""

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from structlog.testing import capture_logs

from training_coach.db.models import (
    McpConnection,
    OAuthClient,
    OAuthCode,
    OAuthToken,
    Passkey,
    User,
)
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.services import auth, mcp_tokens, passkeys
from training_coach.services.erase import erase
from training_coach.services.mcp_tokens import Refused, Tokens
from training_coach.services.seed import load_plan
from training_coach.services.users import OWNER

NOW = datetime(2026, 10, 11, 12, tzinfo=UTC)
MCP = "https://coach.example.com/mcp"
CALLBACK = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "ab" * 22
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=")
EVERYONE = {ALL_USERS: True}


@dataclass
class Connected:
    client_id: str
    connection_id: int
    code: str


def _client(engine: Engine, client_id: str = "client-one") -> int:
    with session_scope(make_session_factory(engine)) as shared:
        row = OAuthClient(
            client_id=client_id,
            name="Claude",
            redirect_uris=[CALLBACK],
            client_hash="0" * 64,
            created_at=NOW,
            expires_at=NOW + timedelta(minutes=15),
            approved_at=NOW,
        )
        shared.add(row)
        shared.flush()
        return row.id


def _connect(
    engine: Engine,
    scopes: tuple[str, ...] = ("training:read",),
    client_id: str = "client-one",
    passkey_id: int | None = None,
    user: int = OWNER,
) -> Connected:
    client = _client(engine, client_id)
    with session_scope(make_session_factory(engine, user_id=user)) as bound:
        if passkey_id is None:  # every connection is approved with a passkey
            key = Passkey(credential_id=f"key-{client_id}", public_key=b"k", name=client_id)
            bound.add(key)
            bound.flush()
            passkey_id = key.id
        connection = mcp_tokens.create_connection(
            bound, client, "Claude", CALLBACK, list(scopes), passkey_id, NOW
        )
        code = mcp_tokens.issue_code(bound, connection, CALLBACK, CHALLENGE.decode(), NOW)
    return Connected(client_id, connection, code)


def _exchange(engine: Engine, c: Connected, **changes: Any) -> Tokens | Refused:
    args: dict[str, Any] = {
        "code": c.code,
        "client_id": c.client_id,
        "redirect_uri": CALLBACK,
        "verifier": VERIFIER,
        "resource": MCP,
        "now": NOW + timedelta(seconds=5),
    } | changes
    with session_scope(make_session_factory(engine)) as shared:
        return mcp_tokens.exchange_code(shared, expected_resource=MCP, **args)


def _tokens(result: Tokens | Refused) -> Tokens:
    assert isinstance(result, Tokens), result
    return result


def _refresh(
    engine: Engine, token: str, client_id: str = "client-one", **changes: Any
) -> Tokens | Refused:
    args: dict[str, Any] = {"scope": None, "resource": MCP, "now": NOW + timedelta(minutes=50)}
    with session_scope(make_session_factory(engine)) as shared:
        return mcp_tokens.refresh(
            shared, token, client_id, expected_resource=MCP, **(args | changes)
        )


def _verify(
    engine: Engine, token: str, at: datetime = NOW, resource: str = MCP
) -> mcp_tokens.Access | None:
    with session_scope(make_session_factory(engine)) as shared:
        return mcp_tokens.verify(shared, token, resource, at)


def _connection(engine: Engine, connection_id: int) -> McpConnection:
    with make_session_factory(engine)() as shared:
        row = shared.get(McpConnection, connection_id, execution_options=EVERYONE)
        assert row is not None
        return row


def test_a_code_buys_an_hour_of_access_and_a_refresh_token(engine: Engine) -> None:
    c = _connect(engine)
    tokens = _tokens(_exchange(engine, c))
    assert tokens.expires_in == 3600
    assert tokens.scope == "training:read"
    access = _verify(engine, tokens.access_token, NOW + timedelta(minutes=59))
    assert access == mcp_tokens.Access(c.connection_id, OWNER, frozenset({"training:read"}))
    assert _verify(engine, tokens.access_token, NOW + timedelta(seconds=5, hours=1)) is None
    assert _verify(engine, tokens.refresh_token) is None  # a refresh token is not access


def test_only_hashes_are_stored(engine: Engine) -> None:
    c = _connect(engine)
    tokens = _tokens(_exchange(engine, c))
    with make_session_factory(engine)() as shared:
        stored = [
            *shared.scalars(select(OAuthCode.code_hash)),
            *shared.scalars(select(OAuthToken.token_hash)),
        ]
    assert len(stored) == 3
    assert all(len(h) == 64 for h in stored)
    for secret in (c.code, tokens.access_token, tokens.refresh_token):
        assert secret not in stored
        assert len(base64.urlsafe_b64decode(secret + "=")) == 32  # 32 random bytes


def test_a_token_works_only_for_its_resource(engine: Engine) -> None:
    tokens = _tokens(_exchange(engine, _connect(engine)))
    assert _verify(engine, tokens.access_token, resource="https://other.example.com/mcp") is None
    assert _exchange(engine, _connect(engine, client_id="c2"), resource="https://x.example") == (
        Refused("invalid_target")
    )


@pytest.mark.parametrize(
    "change",
    [
        {"client_id": "someone-else"},
        {"redirect_uri": CALLBACK + "?x=1"},
        {"verifier": "cd" * 22},
        {"verifier": CHALLENGE.decode()},  # "plain": the challenge itself is no verifier
        {"verifier": "short"},
        {"now": NOW + timedelta(seconds=61)},
    ],
)
def test_a_code_needs_its_client_address_verifier_and_a_minute(
    engine: Engine, change: dict[str, Any]
) -> None:
    c = _connect(engine)
    assert _exchange(engine, c, **change) == Refused("invalid_grant")
    with make_session_factory(engine)() as shared:
        assert shared.scalars(select(OAuthToken)).all() == []


def test_a_wrong_attempt_uses_the_code_up(engine: Engine) -> None:
    c = _connect(engine)
    assert _exchange(engine, c, verifier="cd" * 22) == Refused("invalid_grant")
    assert isinstance(_exchange(engine, c), Refused)


def test_a_code_presented_again_revokes_what_it_bought(engine: Engine) -> None:
    c = _connect(engine)
    tokens = _tokens(_exchange(engine, c))
    assert _exchange(engine, c) == Refused("invalid_grant", revoked=True, user_id=OWNER)
    assert _verify(engine, tokens.access_token) is None
    assert _connection(engine, c.connection_id).revoked_at is not None


def test_two_racing_exchanges_yield_one_token(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both read the code unused; only one conditional update claims it."""
    c = _connect(engine)
    sessions = make_session_factory(engine)
    with sessions() as first:
        row = first.execute(select(OAuthCode), execution_options=EVERYONE).scalar_one()
        first.expunge(row)  # what the racing request saw: not yet used
    _tokens(_exchange(engine, c))
    real = Session.execute

    class Seen:
        def __init__(self, found: tuple[Any, ...]) -> None:
            self.found = found

        def one_or_none(self) -> tuple[Any, ...]:
            return self.found

    def stale(self: Session, statement: Any, *args: Any, **kwargs: Any) -> Any:
        result = real(self, statement, *args, **kwargs)
        if str(statement).startswith("SELECT oauth_codes"):
            _, connection, owner = result.one()
            return Seen((row, connection, owner))  # the code as read before it was claimed
        return result

    monkeypatch.setattr(Session, "execute", stale)
    with sessions() as second:
        lost = mcp_tokens.exchange_code(
            second, c.code, c.client_id, CALLBACK, VERIFIER, MCP, MCP, NOW
        )
        second.rollback()
    monkeypatch.undo()
    assert lost == Refused("invalid_grant")
    with sessions() as shared:
        assert len(shared.scalars(select(OAuthToken)).all()) == 2  # one pair


def test_a_refresh_rotates_the_pair(engine: Engine) -> None:
    first = _tokens(_exchange(engine, _connect(engine)))
    second = _tokens(_refresh(engine, first.refresh_token))
    assert second.refresh_token != first.refresh_token
    assert _verify(engine, second.access_token, NOW + timedelta(minutes=55)) is not None


def test_a_used_refresh_token_revokes_the_connection(engine: Engine) -> None:
    """Even a retry after a lost answer: accepted, the person approves again."""
    c = _connect(engine)
    first = _tokens(_exchange(engine, c))
    second = _tokens(_refresh(engine, first.refresh_token))
    with capture_logs() as logs:
        assert _refresh(engine, first.refresh_token) == Refused(
            "invalid_grant", revoked=True, user_id=OWNER
        )
    assert _verify(engine, second.access_token, NOW + timedelta(minutes=55)) is None
    assert _refresh(engine, second.refresh_token) == Refused("invalid_grant")
    assert _connection(engine, c.connection_id).revoked_at is not None
    assert [entry["event"] for entry in logs] == ["mcp.refresh_reused"]
    assert first.refresh_token not in str(logs)


def test_a_refresh_by_another_client_revokes_and_issues_nothing(engine: Engine) -> None:
    c = _connect(engine)
    _connect(engine, client_id="client-two")
    first = _tokens(_exchange(engine, c))
    assert _refresh(engine, first.refresh_token, client_id="client-two") == Refused(
        "invalid_grant", revoked=True, user_id=OWNER
    )
    assert _verify(engine, first.access_token) is None
    with make_session_factory(engine)() as shared:
        assert shared.scalars(select(OAuthToken)).all() == []


def test_a_refresh_can_narrow_scopes_but_never_widen_them(engine: Engine) -> None:
    c = _connect(engine, scopes=("training:read", "body:read"))
    first = _tokens(_exchange(engine, c))
    assert first.scope == "training:read body:read"
    wider = _refresh(engine, first.refresh_token, scope="training:read readiness:read")
    assert wider == Refused("invalid_scope")

    c2 = _connect(engine, scopes=("training:read", "body:read"), client_id="c2")
    pair = _tokens(_exchange(engine, c2))
    narrow = _tokens(_refresh(engine, pair.refresh_token, client_id="c2", scope="training:read"))
    assert narrow.scope == "training:read"
    access = _verify(engine, narrow.access_token, NOW + timedelta(minutes=55))
    assert access is not None
    assert access.scopes == frozenset({"training:read"})
    assert _refresh(engine, narrow.refresh_token, client_id="c2", scope="bogus") == Refused(
        "invalid_scope"
    )
    # A refused scope leaves the token usable, so a client's mistake costs no new approval.
    assert isinstance(_refresh(engine, first.refresh_token), Tokens)


def test_a_refresh_token_lasts_thirty_days(engine: Engine) -> None:
    first = _tokens(_exchange(engine, _connect(engine)))
    late = NOW + timedelta(days=30, seconds=5)
    assert _refresh(engine, first.refresh_token, now=late) == Refused("invalid_grant")


def test_a_connection_ends_ninety_days_after_approval(engine: Engine) -> None:
    c = _connect(engine)
    tokens = _tokens(_exchange(engine, c))
    at = NOW
    for _ in range(3):  # refreshed every 25 days: still ends on day 90
        at += timedelta(days=25)
        tokens = _tokens(_refresh(engine, tokens.refresh_token, now=at))
    assert _verify(engine, tokens.access_token, at + timedelta(minutes=10)) is not None
    end = NOW + timedelta(days=90)
    assert _verify(engine, tokens.access_token, end) is None
    assert _refresh(engine, tokens.refresh_token, now=end) == Refused("invalid_grant")


def test_revoking_ends_every_token_at_once(engine: Engine) -> None:
    c = _connect(engine)
    tokens = _tokens(_exchange(engine, c))
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert mcp_tokens.revoke(mine, c.connection_id, NOW)
        assert not mcp_tokens.revoke(mine, c.connection_id, NOW)  # once
    assert _verify(engine, tokens.access_token) is None
    assert _refresh(engine, tokens.refresh_token) == Refused("invalid_grant")


def test_someone_else_cannot_revoke_my_connection(engine: Engine) -> None:
    c = _connect(engine)
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        assert not mcp_tokens.revoke(theirs, c.connection_id, NOW)


def test_a_recovery_link_revokes_every_connection(engine: Engine) -> None:
    c = _connect(engine)
    tokens = _tokens(_exchange(engine, c))
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        link = auth.create_link(mine, NOW, purpose=auth.RECOVER)
    with session_scope(make_session_factory(engine)) as shared:
        assert isinstance(auth.redeem_link(shared, link, NOW, "Firefox"), auth.Redeemed)
    assert _verify(engine, tokens.access_token) is None


def test_removing_a_passkey_revokes_the_connections_it_approved(engine: Engine) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        keys = [Passkey(credential_id=n, public_key=b"k", name=n) for n in ("one", "two")]
        mine.add_all(keys)
        mine.flush()
        one, two = (k.id for k in keys)
    approved = _connect(engine, passkey_id=one)
    other = _connect(engine, passkey_id=two, client_id="c2")
    kept = _tokens(_exchange(engine, other))
    gone = _tokens(_exchange(engine, approved))
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert passkeys.remove(mine, one, NOW)
    assert _verify(engine, gone.access_token) is None
    assert _verify(engine, kept.access_token) is not None


def test_a_used_up_access_token_is_noted_at_most_every_few_minutes(engine: Engine) -> None:
    c = _connect(engine)
    tokens = _tokens(_exchange(engine, c))
    _verify(engine, tokens.access_token, NOW)
    _verify(engine, tokens.access_token, NOW + timedelta(minutes=1))
    assert _connection(engine, c.connection_id).last_used_at == NOW
    _verify(engine, tokens.access_token, NOW + timedelta(minutes=6))
    assert _connection(engine, c.connection_id).last_used_at == NOW + timedelta(minutes=6)


def test_a_passkey_proof_is_a_passkey_within_ten_minutes(engine: Engine) -> None:
    """Sessions from a bot link or /recover don't count until a passkey confirms them."""
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        key = Passkey(credential_id="one", public_key=b"k", name="Pixel")
        mine.add(key)
        mine.flush()
        by_link = auth.start_session(mine, OWNER, NOW, "Firefox")
        by_key = auth.start_session(mine, OWNER, NOW, "Firefox", passkey_id=key.id)
        key_id = key.id
    with session_scope(make_session_factory(engine)) as shared:
        assert auth.passkey_proof(shared, by_link, NOW) is None
        proof = auth.passkey_proof(shared, by_key, NOW + timedelta(minutes=10))
        assert proof is not None
        assert proof.passkey_id == key_id
        assert auth.passkey_proof(shared, by_key, NOW + timedelta(minutes=11)) is None
        later = NOW + timedelta(hours=1)
        assert auth.confirm(shared, by_link, OWNER, later, key_id)
        confirmed = auth.passkey_proof(shared, by_link, later + timedelta(minutes=5))
        assert confirmed is not None
        assert confirmed.passkey_id == key_id
        assert auth.fresh(shared, by_link, later)


def test_erasing_everything_removes_every_connection(engine: Engine) -> None:
    tokens = _tokens(_exchange(engine, _connect(engine)))
    with session_scope(make_session_factory(engine)) as shared:
        assert erase(shared, OWNER, load_plan())
    assert _verify(engine, tokens.access_token) is None
    with make_session_factory(engine)() as shared:
        assert shared.scalars(select(OAuthToken)).all() == []
        assert shared.scalars(select(McpConnection), execution_options=EVERYONE).all() == []


def test_a_used_code_replayed_after_it_expired_still_revokes(engine: Engine) -> None:
    c = _connect(engine)
    tokens = _tokens(_exchange(engine, c))
    late = NOW + mcp_tokens.CODE_TTL + timedelta(minutes=5)
    other = _connect(engine, client_id="c2")  # issuing a code sweeps old ones
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        mcp_tokens.issue_code(bound, other.connection_id, CALLBACK, CHALLENGE.decode(), late)
    replayed = _exchange(engine, c, now=late)
    assert replayed == Refused(mcp_tokens.INVALID_GRANT, revoked=True, user_id=OWNER)
    assert _verify(engine, tokens.access_token, late) is None


def test_a_refresh_cannot_keep_proposing_without_training(engine: Engine) -> None:
    """Review of #234: narrowing to ``log:propose`` alone is refused, as consent would drop it."""
    c = _connect(engine, scopes=("training:read", "log:propose"))
    first = _tokens(_exchange(engine, c))
    assert _refresh(engine, first.refresh_token, scope="log:propose") == Refused("invalid_scope")
    narrow = _tokens(_refresh(engine, first.refresh_token, scope="training:read"))
    assert narrow.scope == "training:read"
