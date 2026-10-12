"""Connections, authorization codes and tokens for "Connect my AI" (ADR-0047 C).

The spec is docs/security/mcp-threat-model.md. Every code and token is 32 random bytes,
handed out once and stored only as SHA-256 (like sign-in links); they are opaque, so revoking a
connection takes effect at once. Access tokens last an hour; refresh tokens 30 days, single
use, rotated on every refresh. A connection ends 90 days after the person approved it,
whatever the refreshes, or when revoked: on the Account page, by ``/recover``, by erasing
everything, or by removing the passkey that approved it. Revoking also discards the logs it
proposed that are still waiting (ADR-0058).

A refresh token presented twice, or by a client it wasn't issued to, can only be a stolen
copy (or a retry after a lost answer, which is accepted to cost a new approval): the whole
connection is revoked and the person alerted.

Which connection a token belongs to is the question being asked, so lookups run in an
unbound session with ``ALL_USERS`` (ADR-0029).
"""

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast
from urllib.parse import urlsplit

import structlog
from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.orm import Session

from training_coach.db.models import McpConnection, OAuthClient, OAuthCode, OAuthToken
from training_coach.db.session import ALL_USERS
from training_coach.domain import connections
from training_coach.services import proposals

log = structlog.get_logger(__name__)

ACCESS_TTL = timedelta(hours=1)
REFRESH_TTL = timedelta(days=30)
CODE_TTL = timedelta(seconds=60)
# A used code stays this long past its expiry, so a late replay still revokes and alerts.
CODE_KEPT = timedelta(minutes=10)
# However much it's used, a connection ends this long after its approval (like a session).
MAX_CONNECTION_AGE = timedelta(days=90)
ACCESS, REFRESH = "access", "refresh"
TOUCH_AFTER = timedelta(minutes=5)  # "last used" is written at most this often: an SD card
EVERYONE = {ALL_USERS: True}
VERIFIER = re.compile(r"[A-Za-z0-9._~-]{43,128}")  # RFC 7636 section 4.1

# Why a token request was refused, as RFC 6749 error codes.
INVALID_GRANT = "invalid_grant"
INVALID_SCOPE = "invalid_scope"
INVALID_TARGET = "invalid_target"


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256, as ``services.auth`` stores its tokens (which imports this module)."""
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str
    expires_in: int  # seconds
    scope: str


@dataclass(frozen=True)
class Refused:
    error: str
    # Set when the refusal revoked a connection (a stolen refresh token): alert the person.
    revoked: bool = False


@dataclass(frozen=True)
class Access:
    """A live access token: whose it is and what it may read."""

    connection_id: int
    user_id: int
    scopes: frozenset[str]


def live(connection: McpConnection, now: datetime) -> bool:
    return connection.revoked_at is None and connection.ends_at > now


def create_connection(
    session: Session,
    client: int,
    client_name: str,
    redirect_uri: str,
    scopes: list[str],
    passkey_id: int,
    now: datetime,
) -> int:
    """A new connection for the user ``session`` is bound to; its id. ``passkey_id`` is the
    passkey that approved it, so removing that passkey revokes it (required: a connection
    without one would outlive its passkey)."""
    row = McpConnection(
        client_id=client,
        client_name=client_name,
        redirect_uri=redirect_uri,
        scopes=scopes,
        passkey_id=passkey_id,
        created_at=now,
        ends_at=now + MAX_CONNECTION_AGE,
    )
    session.add(row)
    session.flush()
    return row.id


def issue_code(
    session: Session, connection_id: int, redirect_uri: str, code_challenge: str, now: datetime
) -> str:
    """A one-time authorization code for a just-approved connection."""
    session.execute(delete(OAuthCode).where(OAuthCode.expires_at <= now - CODE_KEPT))
    code = new_secret()
    session.add(
        OAuthCode(
            code_hash=hash_token(code),
            connection_id=connection_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            expires_at=now + CODE_TTL,
        )
    )
    session.flush()
    return code


def pkce_matches(verifier: str, challenge: str) -> bool:
    """S256 only (RFC 7636): ``plain`` is never accepted."""
    if not VERIFIER.fullmatch(verifier):
        return False
    digest = hashlib.sha256(verifier.encode()).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return hmac.compare_digest(expected, challenge)


def _issue(
    session: Session, connection: McpConnection, scopes: list[str], resource: str, now: datetime
) -> Tokens:
    session.execute(delete(OAuthToken).where(OAuthToken.expires_at <= now))
    access, refresh = new_secret(), new_secret()
    access_until = min(now + ACCESS_TTL, connection.ends_at)
    for token, kind, until in (
        (access, ACCESS, access_until),
        (refresh, REFRESH, min(now + REFRESH_TTL, connection.ends_at)),
    ):
        session.add(
            OAuthToken(
                token_hash=hash_token(token),
                kind=kind,
                connection_id=connection.id,
                resource=resource,
                scopes=scopes,
                expires_at=until,
            )
        )
    session.flush()
    return Tokens(access, refresh, int((access_until - now).total_seconds()), " ".join(scopes))


def exchange_code(
    session: Session,
    code: str,
    client_id: str,
    redirect_uri: str,
    verifier: str,
    resource: str | None,
    expected_resource: str,
    now: datetime,
) -> Tokens | Refused:
    """Tokens for a code, once. The code is used up by any attempt, right or wrong, so a
    stolen one gets one guess; a code presented again revokes what it was exchanged for."""
    digest = hash_token(code)
    found = session.execute(
        select(OAuthCode, McpConnection, OAuthClient.client_id)
        .join(McpConnection, OAuthCode.connection_id == McpConnection.id)
        .join(OAuthClient, McpConnection.client_id == OAuthClient.id)
        .where(OAuthCode.code_hash == digest),
        execution_options=EVERYONE,
    ).one_or_none()
    if found is None:
        return Refused(INVALID_GRANT)
    row, connection, owner = found
    if row.used_at is not None:
        log.warning("mcp.code_reused", connection_id=connection.id)
        _revoke(session, connection, now)
        return Refused(INVALID_GRANT, revoked=True)
    # Claimed in one conditional statement: of two racing exchanges, only one changes the row.
    claimed = cast(
        "CursorResult[object]",
        session.execute(
            update(OAuthCode)
            .where(OAuthCode.id == row.id, OAuthCode.used_at.is_(None), OAuthCode.expires_at > now)
            .values(used_at=now),
            execution_options=EVERYONE,
        ),
    )
    if claimed.rowcount != 1:
        return Refused(INVALID_GRANT)
    if resource is not None and resource != expected_resource:
        return Refused(INVALID_TARGET)
    if (
        owner != client_id
        or row.redirect_uri != redirect_uri
        or not pkce_matches(verifier, row.code_challenge)
        or not live(connection, now)
    ):
        return Refused(INVALID_GRANT)
    return _issue(session, connection, list(connection.scopes), expected_resource, now)


def refresh(
    session: Session,
    token: str,
    client_id: str,
    scope: str | None,
    resource: str | None,
    expected_resource: str,
    now: datetime,
) -> Tokens | Refused:
    """A new pair for a refresh token, which is used up. ``scope`` may narrow what the old
    token had, never widen it."""
    found = session.execute(
        select(OAuthToken, McpConnection, OAuthClient.client_id)
        .join(McpConnection, OAuthToken.connection_id == McpConnection.id)
        .join(OAuthClient, McpConnection.client_id == OAuthClient.id)
        .where(OAuthToken.token_hash == hash_token(token), OAuthToken.kind == REFRESH),
        execution_options=EVERYONE,
    ).one_or_none()
    if found is None:
        return Refused(INVALID_GRANT)
    row, connection, owner = found
    if not live(connection, now) or row.expires_at <= now:
        return Refused(INVALID_GRANT)
    if owner != client_id:  # only a stolen token is presented by another client
        log.warning("mcp.refresh_wrong_client", connection_id=connection.id)
        _revoke(session, connection, now)
        return Refused(INVALID_GRANT, revoked=True)
    if row.used_at is not None:
        return _reused(session, connection, now)
    # A request this token can't satisfy is refused before it is used up: a client's mistake
    # shouldn't cost a new approval.
    if resource is not None and resource != expected_resource:
        return Refused(INVALID_TARGET)
    scopes = list(row.scopes)
    if scope is not None:
        asked = connections.parse(scope)
        if asked is None or not set(asked) <= set(scopes):
            return Refused(INVALID_SCOPE)
        scopes = [s.value for s in asked]
    claimed = cast(
        "CursorResult[object]",
        session.execute(
            update(OAuthToken)
            .where(OAuthToken.id == row.id, OAuthToken.used_at.is_(None))
            .values(used_at=now),
            execution_options=EVERYONE,
        ),
    )
    if claimed.rowcount != 1:  # two presenting it at once: one of them is a copy
        return _reused(session, connection, now)
    return _issue(session, connection, scopes, expected_resource, now)


def _reused(session: Session, connection: McpConnection, now: datetime) -> Refused:
    """A used refresh token presented again: a copy, or a retry after a lost answer."""
    log.warning("mcp.refresh_reused", connection_id=connection.id)
    _revoke(session, connection, now)
    return Refused(INVALID_GRANT, revoked=True)


def verify(session: Session, token: str, resource: str, now: datetime) -> Access | None:
    """The connection behind a live access token for ``resource``, or None. Notes when it was
    last used, at most every few minutes."""
    found = session.execute(
        select(OAuthToken, McpConnection)
        .join(McpConnection, OAuthToken.connection_id == McpConnection.id)
        .where(OAuthToken.token_hash == hash_token(token), OAuthToken.kind == ACCESS),
        execution_options=EVERYONE,
    ).one_or_none()
    if found is None:
        return None
    row, connection = found
    if row.expires_at <= now or row.resource != resource or not live(connection, now):
        return None
    if connection.last_used_at is None or now - connection.last_used_at >= TOUCH_AFTER:
        connection.last_used_at = now
    granted = frozenset(row.scopes) & frozenset(connection.scopes)
    return Access(connection.id, connection.user_id, granted)


def _revoke(session: Session, connection: McpConnection, now: datetime) -> None:
    """End a connection: its tokens go, and logs it proposed that wait are discarded."""
    if connection.revoked_at is None:
        connection.revoked_at = now
    proposals.discard_for(session, connection.id, now)
    session.execute(
        delete(OAuthToken).where(OAuthToken.connection_id == connection.id),
        execution_options=EVERYONE,
    )


@dataclass(frozen=True)
class Connection:
    id: int
    client_name: str  # as the app called itself when it was approved
    redirect_host: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    ends_at: datetime


def live_connections(session: Session, now: datetime) -> list[Connection]:
    """The bound user's live connections, newest first."""
    rows = session.scalars(
        select(McpConnection)
        .where(McpConnection.revoked_at.is_(None), McpConnection.ends_at > now)
        .order_by(McpConnection.created_at.desc(), McpConnection.id.desc())
    )
    return [
        Connection(
            row.id,
            row.client_name,
            urlsplit(row.redirect_uri).hostname or "",
            list(row.scopes),
            row.created_at,
            row.last_used_at,
            row.ends_at,
        )
        for row in rows
    ]


def revoke(session: Session, connection_id: int, now: datetime) -> bool:
    """Revoke one of the bound user's live connections; False if there is no such one."""
    row = session.scalar(
        select(McpConnection).where(
            McpConnection.id == connection_id, McpConnection.revoked_at.is_(None)
        )
    )
    if row is None:
        return False
    _revoke(session, row, now)
    return True


def revoke_all(session: Session, user_id: int, now: datetime) -> None:
    """Revoke every connection of ``user_id`` (``/recover``). ``session`` may be unbound."""
    for row in session.scalars(
        select(McpConnection).where(
            McpConnection.user_id == user_id, McpConnection.revoked_at.is_(None)
        ),
        execution_options=EVERYONE,
    ):
        _revoke(session, row, now)


def revoke_approved_with(session: Session, passkey_id: int, now: datetime) -> None:
    """Revoke the bound user's connections approved with a passkey that is being removed."""
    for row in session.scalars(
        select(McpConnection).where(
            McpConnection.passkey_id == passkey_id, McpConnection.revoked_at.is_(None)
        )
    ):
        _revoke(session, row, now)
