"""The OAuth 2.1 authorization server for "Connect my AI" (ADR-0047 C): registering AI apps,
the authorization request, and the consent page behind it. Tokens are ``mcp_tokens``.

The spec is docs/security/mcp-threat-model.md. In short:

- **Registration (RFC 7591) is open but bounded.** At most 20 registrations wait for approval
  overall and 3 per client address; each waits 15 minutes. When the 20 are full the oldest one
  without an open consent page makes room, so a few addresses can't lock the real AI app out;
  only if every one has an open consent page is the new one refused. Approved apps don't count.
- **Redirect addresses are https only and must match a registered one byte for byte.** An
  unknown app or address gets an error page, never a redirect.
- **The authorization request becomes a consent handle**, bound to everything it asked for. The
  consent page binds it to the browser once the person proves their passkey there, and approval
  checks both bindings before it issues a code.
"""

import re
import secrets
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from ipaddress import ip_address
from typing import cast
from urllib.parse import parse_qsl, urlencode, urlsplit

import structlog
from sqlalchemy import CursorResult, and_, delete, exists, func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import Exists

from training_coach.db.models import OAuthClient, OAuthConsent
from training_coach.db.session import bound_user
from training_coach.domain import connections
from training_coach.domain.connections import LABELS, OPT_IN, Scope
from training_coach.services import mcp_tokens
from training_coach.services.mcp_tokens import hash_token

log = structlog.get_logger(__name__)

REGISTRATION_TTL = timedelta(minutes=15)
CONSENT_TTL = timedelta(minutes=10)
MAX_PENDING = 20
MAX_PENDING_PER_ADDRESS = 3
MAX_OPEN_CONSENTS = 40  # open consent pages, overall: rows on the SD card
MAX_OPEN_PER_CLIENT = 3  # per app: a new one replaces its oldest page nobody has opened yet
MAX_OPEN_PER_ADDRESS = 3  # per caller address: more are refused
NAME_LENGTH = 60
MAX_REDIRECT_URIS = 5
URI_LENGTH = 200
STATE_LENGTH = 500
UNNAMED = "Unnamed app"
CHALLENGE = re.compile(r"[A-Za-z0-9_-]{43}")  # base64url of a SHA-256, unpadded
GRANT_TYPES = frozenset({"authorization_code", "refresh_token"})


def plain(text: str) -> bool:
    """No control, formatting (bidi overrides) or line-breaking characters: a name shows as
    what it is on the consent page and in the Telegram alert."""
    return not any(
        unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp") for c in text
    )


def _strings(value: object) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return None
    return value


# ------------------------------------------------------------------ registration


@dataclass(frozen=True)
class Registered:
    client_id: str
    name: str
    redirect_uris: list[str]
    issued_at: datetime


@dataclass(frozen=True)
class Invalid:
    error: str  # RFC 7591 section 3.2.2
    description: str


@dataclass(frozen=True)
class Busy:
    retry_after: int  # seconds


def redirect_uri_ok(uri: str) -> bool:
    """An https address with a real host: no ``http``, no loopback, no fragment, no user."""
    if len(uri) > URI_LENGTH or not plain(uri) or " " in uri:
        return False
    try:
        url = urlsplit(uri)
        host = url.hostname
        url.port  # noqa: B018 - raises on a malformed port
    except ValueError:
        return False
    if url.scheme != "https" or not host or url.fragment or "#" in uri or url.username:
        return False
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        address = ip_address(host)
    except ValueError:
        return True
    return not (address.is_loopback or address.is_unspecified or address.is_private)


def _metadata(body: object) -> tuple[str, list[str]] | Invalid:
    if not isinstance(body, dict):
        return Invalid("invalid_client_metadata", "send a JSON object")
    uris = _strings(body.get("redirect_uris"))
    if not uris:
        return Invalid("invalid_redirect_uri", "redirect_uris must list at least one address")
    if len(uris) > MAX_REDIRECT_URIS:
        return Invalid("invalid_redirect_uri", f"at most {MAX_REDIRECT_URIS} redirect_uris")
    if not all(redirect_uri_ok(u) for u in uris):
        return Invalid(
            "invalid_redirect_uri",
            f"redirect_uris must be https, not loopback, up to {URI_LENGTH} characters",
        )
    name = body.get("client_name", UNNAMED)
    if not isinstance(name, str) or len(name) > NAME_LENGTH or not plain(name):
        return Invalid("invalid_client_metadata", f"client_name: up to {NAME_LENGTH} characters")
    grants = _strings(body.get("grant_types", ["authorization_code"]))
    responses = _strings(body.get("response_types", ["code"]))
    if grants is None or not set(grants) <= GRANT_TYPES:
        return Invalid("invalid_client_metadata", "grant_types: authorization_code, refresh_token")
    if responses is None or not set(responses) <= {"code"}:
        return Invalid("invalid_client_metadata", "response_types: code")
    return name.strip() or UNNAMED, list(dict.fromkeys(uris))


def _open_consent(now: datetime) -> Exists:
    """SQL: the client has a consent page open (a live, unused handle)."""
    return exists().where(
        OAuthConsent.client_id == OAuthClient.id,
        OAuthConsent.expires_at > now,
        OAuthConsent.used_at.is_(None),
    )


def register(
    session: Session, body: object, client: str, now: datetime
) -> Registered | Invalid | Busy:
    """Register an AI app (RFC 7591) from its JSON metadata. ``client`` is the caller's address,
    stored hashed. ``session`` is unbound: a registration belongs to nobody yet."""
    checked = _metadata(body)
    if isinstance(checked, Invalid):
        return checked
    name, uris = checked
    pending = OAuthClient.approved_at.is_(None)
    # Registrations that expired unapproved go, unless their consent page is still open.
    session.execute(
        delete(OAuthClient)
        .where(pending, OAuthClient.expires_at <= now, ~_open_consent(now))
        .execution_options(synchronize_session=False)
    )
    mine = hash_token(client)
    waiting = list(
        session.scalars(
            select(OAuthClient.expires_at).where(pending, OAuthClient.client_hash == mine)
        )
    )
    if len(waiting) >= MAX_PENDING_PER_ADDRESS:
        log.warning("oauth.registrations_capped", scope="address")
        return Busy(_seconds(min(waiting) - now))
    if (session.scalar(select(func.count()).select_from(OAuthClient).where(pending)) or 0) >= (
        MAX_PENDING
    ):
        oldest = session.scalar(
            select(OAuthClient.id)
            .where(pending, ~_open_consent(now))
            .order_by(OAuthClient.created_at, OAuthClient.id)
            .limit(1)
        )
        if oldest is None:  # every waiting app has its consent page open: wait for one
            log.warning("oauth.registrations_capped", scope="everyone")
            first_end = session.scalar(
                select(func.min(OAuthConsent.expires_at)).where(
                    OAuthConsent.expires_at > now, OAuthConsent.used_at.is_(None)
                )
            )
            return Busy(_seconds((first_end or now) - now))
        session.execute(delete(OAuthClient).where(OAuthClient.id == oldest))
        log.info("oauth.registration_evicted")
    client_id = secrets.token_urlsafe(24)
    session.add(
        OAuthClient(
            client_id=client_id,
            name=name,
            redirect_uris=uris,
            client_hash=mine,
            created_at=now,
            expires_at=now + REGISTRATION_TTL,
        )
    )
    session.flush()
    log.info("oauth.registered")
    return Registered(client_id, name, uris, now)


def _seconds(delta: timedelta) -> int:
    return max(1, int(delta.total_seconds() + 0.999))


def find_client(session: Session, client_id: str, now: datetime) -> OAuthClient | None:
    """A registered app that may still be used: approved, or still waiting for approval."""
    row = session.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))
    if row is None or (row.approved_at is None and row.expires_at <= now):
        return None
    return row


# --------------------------------------------------------- the authorization request


@dataclass(frozen=True)
class ErrorPage:
    """Shown on our own page, with no redirect: the app or its address can't be trusted."""

    message: str
    status: int = 400


@dataclass(frozen=True)
class ErrorRedirect:
    """Sent back to the app's own, registered address."""

    url: str


@dataclass(frozen=True)
class Server:
    issuer: str  # https://coach.example.com
    resource: str  # https://coach.example.com/mcp


def with_query(uri: str, params: Mapping[str, str | None]) -> str:
    """``uri`` with ``params`` appended to its query (None values left out)."""
    query = urlencode({k: v for k, v in params.items() if v is not None})
    return f"{uri}{'&' if urlsplit(uri).query else '?'}{query}"


def error_redirect(uri: str, error: str, state: str | None, issuer: str) -> ErrorRedirect:
    return ErrorRedirect(with_query(uri, {"error": error, "state": state, "iss": issuer}))


def authorize(
    session: Session, params: Mapping[str, str], server: Server, address: str, now: datetime
) -> str | ErrorPage | ErrorRedirect:
    """Check an authorization request; the consent handle for its consent page, an error page,
    or an error to send back to the app. ``address`` is the caller's (stored hashed).
    ``session`` is unbound: nobody is signed in yet (the SameSite=Strict cookie doesn't come
    on the AI app's cross-site link)."""
    client = find_client(session, params.get("client_id", ""), now)
    if client is None:
        return ErrorPage("This app isn't registered, or its registration has expired.")
    redirect_uri = params.get("redirect_uri", "")
    if redirect_uri not in client.redirect_uris or not redirect_uri_ok(redirect_uri):
        return ErrorPage("This app asked to send you to an address it didn't register.")
    state = params.get("state")
    if state is not None and len(state) > STATE_LENGTH:
        return ErrorPage("This request is too long.")
    issuer = server.issuer
    if params.get("response_type") != "code":
        return error_redirect(redirect_uri, "unsupported_response_type", state, issuer)
    challenge = params.get("code_challenge", "")
    if params.get("code_challenge_method") != "S256" or not CHALLENGE.fullmatch(challenge):
        return error_redirect(redirect_uri, "invalid_request", state, issuer)
    if params.get("resource") != server.resource:
        return error_redirect(redirect_uri, "invalid_target", state, issuer)
    scopes = connections.parse(params.get("scope"))
    if scopes is None:
        return error_redirect(redirect_uri, "invalid_scope", state, issuer)
    session.execute(delete(OAuthConsent).where(OAuthConsent.expires_at <= now))
    busy = _consent_room(session, client.id, hash_token(address))
    if busy is not None:
        return busy
    handle = mcp_tokens.new_secret()
    session.add(
        OAuthConsent(
            handle_hash=hash_token(handle),
            client_id=client.id,
            client_hash=hash_token(address),
            redirect_uri=redirect_uri,
            scopes=[s.value for s in scopes],
            state=state,
            code_challenge=challenge,
            resource=server.resource,
            created_at=now,
            expires_at=now + CONSENT_TTL,
        )
    )
    session.flush()
    return handle


def _consent_room(session: Session, client: int, address: str) -> ErrorPage | None:
    """Make room for one more open consent page, or say why there is none (M11).

    - Per address (``address`` is hashed): at most 3 open, then refused. One caller can't fill
      the overall cap, nor keep more than 3 waiting registrations safe from eviction.
    - Per app: at most 3 open; a new one replaces the app's oldest page that no browser has
      bound yet (its person would start again from the AI app anyway). A page the person has
      already proved their passkey on is never replaced: if all 3 are, the new one is refused.
      Replacing rather than refusing means someone who knows an app's id can't block the
      person's own new attempt by filling that app's slots.
    - Overall: at most 40 open.
    """
    open_ = (OAuthConsent.used_at.is_(None),)
    count = select(func.count()).select_from(OAuthConsent).where(*open_)
    if (session.scalar(count.where(OAuthConsent.client_hash == address)) or 0) >= (
        MAX_OPEN_PER_ADDRESS
    ):
        log.warning("oauth.consents_capped", scope="address")
        return ErrorPage("Too many requests are waiting. Try again in a few minutes.", 429)
    if (session.scalar(count.where(OAuthConsent.client_id == client)) or 0) >= (
        MAX_OPEN_PER_CLIENT
    ):
        oldest = session.scalar(
            select(OAuthConsent.id)
            .where(*open_, OAuthConsent.client_id == client, OAuthConsent.web_session_id.is_(None))
            .order_by(OAuthConsent.created_at, OAuthConsent.id)
            .limit(1)
        )
        if oldest is None:
            log.warning("oauth.consents_capped", scope="client")
            return ErrorPage("Too many requests are waiting. Try again in a few minutes.", 429)
        session.execute(delete(OAuthConsent).where(OAuthConsent.id == oldest))
        log.info("oauth.consent_replaced")
    if (session.scalar(count) or 0) >= MAX_OPEN_CONSENTS:
        log.warning("oauth.consents_capped", scope="everyone")
        return ErrorPage("Too many requests are waiting. Try again in a few minutes.", 429)
    return None


# ------------------------------------------------------------------ the consent page


@dataclass(frozen=True)
class ScopeView:
    scope: str
    label: str
    opt_in: bool  # starts unticked: health data, and proposing logs


@dataclass(frozen=True)
class ConsentView:
    client_id: str
    client_name: str  # the app's own claim, shown as "calls itself ..."
    redirect_uri: str
    redirect_host: str
    scopes: list[ScopeView]


def _consent(
    session: Session, handle: str, now: datetime
) -> tuple[OAuthConsent, OAuthClient] | None:
    found = session.execute(
        select(OAuthConsent, OAuthClient)
        .join(OAuthClient, OAuthConsent.client_id == OAuthClient.id)
        .where(
            OAuthConsent.handle_hash == hash_token(handle),
            OAuthConsent.expires_at > now,
            OAuthConsent.used_at.is_(None),
        )
    ).one_or_none()
    return None if found is None else (found[0], found[1])


def details(session: Session, handle: str, now: datetime) -> ConsentView | None:
    """What an open consent page asks for, or None if the handle is unknown, used or expired."""
    found = _consent(session, handle, now)
    if found is None:
        return None
    consent, client = found
    return ConsentView(
        client.client_id,
        client.name,
        consent.redirect_uri,
        urlsplit(consent.redirect_uri).hostname or "",
        [ScopeView(s, LABELS[Scope(s)], Scope(s) in OPT_IN) for s in consent.scopes],
    )


def bind(session: Session, handle: str, user_id: int, web_session_id: int, now: datetime) -> bool:
    """Bind an open consent page to the browser that just proved its passkey on it. False if
    the handle is gone or already bound to another browser."""
    found = _consent(session, handle, now)
    if found is None:
        return False
    consent = found[0]
    if consent.web_session_id is None:
        consent.web_session_id, consent.user_id = web_session_id, user_id
        return True
    return consent.web_session_id == web_session_id and consent.user_id == user_id


@dataclass(frozen=True)
class Approved:
    redirect: str  # where the page sends the person: the app, with the code
    connection_id: int
    client_name: str
    redirect_host: str
    scopes: list[str]


@dataclass(frozen=True)
class Refusal:
    reason: str


def approve(
    session: Session,
    handle: str,
    web_session_id: int,
    passkey_id: int,
    client_id: str,
    redirect_uri: str,
    ticked: list[str],
    issuer: str,
    now: datetime,
) -> Approved | Refusal:
    """Approve a consent page: a connection with the scopes asked for and ticked, and a code
    for the app. ``session`` is bound to the person; the handle must be bound to them and to
    this browser, and ``client_id`` and ``redirect_uri`` must be what it was made for."""
    user = bound_user(session)
    found = _consent(session, handle, now)
    if user is None or found is None:
        return Refusal("This request has expired. Start again from your AI app.")
    consent, client = found
    if consent.web_session_id != web_session_id or consent.user_id != user:
        return Refusal("Confirm it's you on this page first.")
    if (
        client.client_id != client_id
        or consent.redirect_uri != redirect_uri
        or redirect_uri not in client.redirect_uris
    ):
        return Refusal("This request changed. Start again from your AI app.")
    scopes = [s.value for s in connections.grant(consent.scopes, ticked)]
    if not scopes:
        return Refusal("Tick at least one thing to share.")
    claimed = cast(
        "CursorResult[object]",
        session.execute(
            update(OAuthConsent)
            .where(and_(OAuthConsent.id == consent.id, OAuthConsent.used_at.is_(None)))
            .values(used_at=now)
        ),
    )
    if claimed.rowcount != 1:
        return Refusal("This request has expired. Start again from your AI app.")
    if client.approved_at is None:
        client.approved_at = now
    connection = mcp_tokens.create_connection(
        session, client.id, client.name, redirect_uri, scopes, passkey_id, now
    )
    code = mcp_tokens.issue_code(session, connection, redirect_uri, consent.code_challenge, now)
    log.info("oauth.approved", connection_id=connection)
    return Approved(
        with_query(redirect_uri, {"code": code, "state": consent.state, "iss": issuer}),
        connection,
        client.name,
        urlsplit(redirect_uri).hostname or "",
        scopes,
    )


def deny(session: Session, handle: str, issuer: str, now: datetime) -> str | None:
    """Turn a consent page down: where to send the person back, with ``access_denied``."""
    found = _consent(session, handle, now)
    if found is None:
        return None
    consent = found[0]
    consent.used_at = now
    return error_redirect(consent.redirect_uri, "access_denied", consent.state, issuer).url


# ------------------------------------------------------------------ the token request


FORM = "application/x-www-form-urlencoded"
MAX_FIELDS = 20


def form(body: bytes) -> dict[str, str] | None:
    """A token request's form fields; None if it isn't a form, or names a field twice (RFC
    6749 section 3.2)."""
    try:
        pairs = parse_qsl(
            body.decode("utf-8"),
            keep_blank_values=True,
            strict_parsing=bool(body),
            max_num_fields=MAX_FIELDS,
        )
    except (UnicodeDecodeError, ValueError):
        return None
    fields = dict(pairs)
    return fields if len(fields) == len(pairs) else None
