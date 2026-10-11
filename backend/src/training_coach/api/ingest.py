"""Band data from the phone (ADR-0055): the Health Connect Webhook app posts here, with the
person's ingest secret; and the Account routes that make and remove that secret.

The ingest route is public in the sense that no cookie signs it in: only the secret does. It
reads no cookies and sets none, reads the body up to a cap, limits callers per address, and
logs only how many records of each type came in.
"""

import json
import time
from collections import deque
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.alerts import alert
from training_coach.api.auth import Fresh, Owner
from training_coach.api.passkeys import _client
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import health_import, ingest_keys

router = APIRouter(prefix="/api/ingest", tags=["ingest"])
account_router = APIRouter(prefix="/api/account/ingest", tags=["account"])
log = structlog.get_logger(__name__)

PATH = "/api/ingest/health-connect"
MAX_BYTES = 5 * 1024 * 1024  # a first sync of 48 hours of per-minute heart rate is ~0.7 MB
WINDOW = 600.0  # seconds
MAX_CALLS = 60  # per address per window; the app syncs at most every 15 minutes
MAX_FAILURES = 10  # wrong secrets per address per window
MAX_ADDRESSES = 10_000  # then idle addresses are forgotten, so memory stays bounded


class Limiter:
    """Calls and failed secrets per client address over the last ``WINDOW`` seconds, in
    memory: one process serves the app (ADR-0002)."""

    def __init__(self) -> None:
        self.calls: dict[str, deque[float]] = {}
        self.failures: dict[str, deque[float]] = {}

    @staticmethod
    def _recent(seen: dict[str, deque[float]], address: str, now: float) -> deque[float]:
        if address not in seen and len(seen) >= MAX_ADDRESSES:
            # Forget idle addresses only: clearing everything would let a caller with many
            # addresses wipe its own wrong-secret count (review of #224).
            for idle in [a for a, times in seen.items() if not times or now - times[-1] > WINDOW]:
                del seen[idle]
            if len(seen) >= MAX_ADDRESSES:
                del seen[next(iter(seen))]
        times = seen.setdefault(address, deque())
        while times and now - times[0] > WINDOW:
            times.popleft()
        return times

    def allow(self, address: str, now: float) -> bool:
        calls = self._recent(self.calls, address, now)
        # Only addresses that sent a wrong secret are tracked as failures, so a flood of
        # well-behaved addresses can't push a guesser's count out.
        failed = address in self.failures and self._recent(self.failures, address, now)
        if len(calls) >= MAX_CALLS or (failed and len(failed) >= MAX_FAILURES):
            return False
        calls.append(now)
        return True

    def failed(self, address: str, now: float) -> None:
        self._recent(self.failures, address, now).append(now)


def _limiter(request: Request) -> Limiter:
    found = getattr(request.app.state, "ingest_limiter", None)
    if not isinstance(found, Limiter):
        found = Limiter()
        request.app.state.ingest_limiter = found
    return found


class IngestReceived(BaseModel):
    """How many records of each type were stored, and skipped as not fitting."""

    taken: dict[str, int]
    skipped: dict[str, int]


def _secret(request: Request) -> str | None:
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


async def _body(request: Request) -> bytes:
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "payload too large")
    return bytes(data)


@router.post("/health-connect", response_model=IngestReceived)
async def health_connect(request: Request) -> IngestReceived:
    """Store a Health Connect Webhook payload for the person whose secret it carries."""
    address, clock = _client(request), time.monotonic()
    limiter = _limiter(request)
    if not limiter.allow(address, clock):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many requests")
    secret = _secret(request)
    now = datetime.now(UTC)
    shared: sessionmaker[Session] = request.app.state.shared_sessions
    with session_scope(shared) as session:
        user = ingest_keys.owner_of(session, secret, now) if secret is not None else None
    if user is None:
        limiter.failed(address, clock)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown ingest secret")
    raw = await _body(request)
    settings: Settings = request.app.state.settings
    bound = make_session_factory(request.app.state.engine, user_id=user)

    def parse_and_store() -> health_import.Batch:
        """Parsing up to 5 MB and the SQLite writes block: off the event loop, so a first sync
        can't stall the bot and the web app."""
        try:
            body = json.loads(raw)
        except (ValueError, RecursionError) as exc:  # bad UTF-8 or JSON, or nested too deep
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "not JSON") from exc
        if not isinstance(body, dict):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "not a JSON object")
        batch = health_import.parse(body, now)
        with session_scope(bound) as session:
            health_import.store(session, batch, settings.tz, now)
        return batch

    batch = await run_in_threadpool(parse_and_store)
    log.info("ingest.stored", **health_import.counts(batch))
    return IngestReceived(taken=dict(batch.taken), skipped=dict(batch.skipped))


# --------------------------------------------------------------------- the secret


class IngestView(BaseModel):
    exists: bool
    created_at: datetime | None
    last_used_at: datetime | None
    url: str | None  # where the phone posts; None until the server has TC_PUBLIC_URL


class NewSecret(IngestView):
    secret: str  # shown once, never again


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _url(request: Request) -> str | None:
    settings: Settings = request.app.state.settings
    return f"{settings.public_url}{PATH}" if settings.public_url else None


def _view(request: Request, found: ingest_keys.Status) -> IngestView:
    return IngestView(**vars(found), url=_url(request))


@account_router.get("", response_model=IngestView)
def get_ingest(request: Request, user: Owner) -> IngestView:
    with session_scope(_bound(request, user)) as session:
        found = ingest_keys.status(session)
    return _view(request, found)


@account_router.post("", response_model=NewSecret)
def make_secret(
    request: Request, background: BackgroundTasks, user: Owner, _fresh: Fresh
) -> NewSecret:
    """A new secret for the phone, replacing any earlier one. Needs a recent sign-in and is
    alerted: whoever holds it can add health data."""
    with session_scope(_bound(request, user)) as session:
        secret = ingest_keys.make(session, datetime.now(UTC))
        found = ingest_keys.status(session)
    alert(request, background, "ingest_key_made", "A new band import secret was made.")
    return NewSecret(**_view(request, found).model_dump(), secret=secret)


@account_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def remove_secret(request: Request, background: BackgroundTasks, user: Owner) -> None:
    with session_scope(_bound(request, user)) as session:
        removed = ingest_keys.remove(session)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no band import secret")
    alert(request, background, "ingest_key_removed", "The band import secret was removed.")
