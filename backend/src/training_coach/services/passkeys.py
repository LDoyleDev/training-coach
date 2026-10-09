"""Passkeys (ADR-0036): add a fingerprint or face key while signed in, then sign in with it.

The `webauthn` library checks the two ceremonies (registration and sign-in). Each ceremony uses
a fresh challenge kept here for 5 minutes and taken once; the browser holds only a random
handle to it. Sign-in requires user verification (the fingerprint or face, not just a tap).
Lookups by credential are cross-user by nature, so they run with ``ALL_USERS`` (ADR-0029).
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast
from urllib.parse import urlsplit

import structlog
from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import (
    base64url_to_bytes,
    bytes_to_base64url,
    parse_authentication_credential_json,
)
from webauthn.helpers.exceptions import (
    InvalidJSONStructure,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from training_coach.db.models import Passkey, PasskeyChallenge
from training_coach.db.session import ALL_USERS, bound_user
from training_coach.services import auth

log = structlog.get_logger(__name__)

RP_NAME = "Training Coach"
CHALLENGE_TTL = timedelta(minutes=5)
EVERYONE = {ALL_USERS: True}
REGISTER, SIGN_IN = "register", "sign_in"
# Sign-in options are public and each one is a row (review of #123). Capped per client, so a
# stranger can't use up everyone's sign-ins and lock the owner out, and overall, so nobody can
# flood the SD card. One person needs one or two at a time; /login always works regardless.
MAX_OPEN_PER_CLIENT = 5
MAX_OPEN_SIGN_INS = 200


class TooManySignInsError(Exception):
    """Too many sign-in ceremonies are open; try again in a few minutes."""


@dataclass(frozen=True)
class Party:
    """The relying party: the web app's origin and the domain passkeys are bound to."""

    origin: str  # https://coach.example.com
    rp_id: str  # coach.example.com

    @classmethod
    def from_url(cls, public_url: str) -> "Party":
        """From the parsed URL, never the text as written: the browser reports its origin as
        scheme://host[:port], and a stray slash or path would fail every ceremony."""
        url = urlsplit(public_url)
        if not url.hostname:
            raise ValueError("public_url has no host")
        if url.scheme != "https" and url.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("passkeys need https")
        return cls(origin=f"{url.scheme}://{url.netloc}", rp_id=url.hostname)


@dataclass(frozen=True)
class Ceremony:
    options: str  # JSON for the browser (navigator.credentials)
    handle: str  # the browser's cookie: which challenge to check the answer against


def _challenge(
    session: Session,
    challenge: bytes,
    purpose: str,
    user_id: int | None,
    now: datetime,
    client: str | None = None,
) -> str:
    # Clear challenges nobody answered; they would only pile up.
    session.execute(delete(PasskeyChallenge).where(PasskeyChallenge.expires_at <= now))
    handle = secrets.token_urlsafe(32)
    session.add(
        PasskeyChallenge(
            handle_hash=auth.hash_token(handle),
            challenge=challenge,
            purpose=purpose,
            user_id=user_id,
            client_hash=auth.hash_token(client) if client else None,
            expires_at=now + CHALLENGE_TTL,
        )
    )
    session.flush()
    return handle


def _take(
    session: Session, handle: str, purpose: str, user_id: int | None, now: datetime
) -> bytes | None:
    """The challenge behind ``handle``, removed so it can't be answered twice; None if it's
    unknown, expired, for another purpose or asked for by someone else."""
    found = session.scalar(
        select(PasskeyChallenge).where(PasskeyChallenge.handle_hash == auth.hash_token(handle))
    )
    if found is None:
        return None
    taken = cast(
        "CursorResult[object]",
        session.execute(delete(PasskeyChallenge).where(PasskeyChallenge.id == found.id)),
    )
    if taken.rowcount != 1 or found.expires_at <= now:
        return None
    if found.purpose != purpose or found.user_id != user_id:
        return None
    return found.challenge


def registration(session: Session, party: Party, now: datetime) -> Ceremony:
    """Options for adding a passkey for the user ``session`` is bound to. Their existing
    passkeys are excluded, so the same device isn't registered twice."""
    user = bound_user(session)
    if user is None:
        raise PermissionError("adding a passkey needs a signed-in user")
    existing = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(credential))
        for credential in session.scalars(select(Passkey.credential_id))
    ]
    options = generate_registration_options(
        rp_id=party.rp_id,
        rp_name=RP_NAME,
        user_id=str(user).encode(),
        user_name=RP_NAME,
        user_display_name=RP_NAME,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=existing,
    )
    handle = _challenge(session, options.challenge, REGISTER, user, now)
    return Ceremony(options_to_json(options), handle)


def register(
    session: Session,
    party: Party,
    handle: str,
    credential: dict[str, Any],
    name: str,
    now: datetime,
) -> bool:
    """Check the browser's new credential against the challenge and keep its public key."""
    user = bound_user(session)
    challenge = _take(session, handle, REGISTER, user, now)
    if user is None or challenge is None:
        return False
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=party.rp_id,
            expected_origin=party.origin,
            require_user_verification=True,
        )
    except (InvalidRegistrationResponse, InvalidJSONStructure):
        return False
    credential_id = bytes_to_base64url(verified.credential_id)
    taken = session.scalar(
        select(Passkey.id).where(Passkey.credential_id == credential_id),
        execution_options=EVERYONE,
    )
    if taken is not None:  # registered already, by this person or anyone
        return False
    session.add(
        Passkey(
            credential_id=credential_id,
            public_key=verified.credential_public_key,
            sign_count=verified.sign_count,
            name=name[: auth.LABEL_LENGTH] or "Passkey",
            created_at=now,
        )
    )
    session.flush()
    return True


def sign_in_options(session: Session, party: Party, now: datetime, client: str) -> Ceremony:
    """Options for signing in with any passkey on the device (no username: discoverable).
    ``client`` is the caller's address (stored hashed). Raises ``TooManySignInsError`` when
    that client, or everyone together, has too many open."""
    session.execute(delete(PasskeyChallenge).where(PasskeyChallenge.expires_at <= now))
    open_sign_ins = (
        select(func.count())
        .select_from(PasskeyChallenge)
        .where(PasskeyChallenge.purpose == SIGN_IN)
    )
    mine = session.scalar(
        open_sign_ins.where(PasskeyChallenge.client_hash == auth.hash_token(client))
    )
    everyone = session.scalar(open_sign_ins)
    if (mine or 0) >= MAX_OPEN_PER_CLIENT or (everyone or 0) >= MAX_OPEN_SIGN_INS:
        log.warning("auth.passkey_sign_ins_capped", mine=mine, everyone=everyone)
        raise TooManySignInsError
    options = generate_authentication_options(
        rp_id=party.rp_id, user_verification=UserVerificationRequirement.REQUIRED
    )
    handle = _challenge(session, options.challenge, SIGN_IN, None, now, client)
    return Ceremony(options_to_json(options), handle)


def sign_in(
    session: Session,
    party: Party,
    handle: str,
    credential: dict[str, Any],
    now: datetime,
    label: str,
) -> str | None:
    """A session cookie token if the device proved it holds a registered passkey, else None.
    ``session`` is unbound: the passkey says whose it is."""
    challenge = _take(session, handle, SIGN_IN, None, now)
    if challenge is None:
        return None
    try:
        parsed = parse_authentication_credential_json(credential)
    # Anyone can call this: whatever a malformed answer makes the library raise is a refusal,
    # never a 500 (review of #123).
    except Exception:
        return None
    passkey = session.scalar(
        select(Passkey).where(Passkey.credential_id == bytes_to_base64url(parsed.raw_id)),
        execution_options=EVERYONE,
    )
    if passkey is None:
        return None
    try:
        verified = verify_authentication_response(
            credential=parsed,
            expected_challenge=challenge,
            expected_rp_id=party.rp_id,
            expected_origin=party.origin,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except Exception:  # as above: a bad answer is a refusal
        return None
    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = now
    return auth.start_session(session, passkey.user_id, now, label)
