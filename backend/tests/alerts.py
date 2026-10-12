"""Catching the Telegram alerts a web test sets off (ADR-0040). Each goes to the chat of the
person it's about, so the person is linked to a Telegram chat first."""

from fastapi.testclient import TestClient

from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services.users import OWNER

CHAT = 4242  # the owner's Telegram chat in these tests


def capture(client: TestClient, user: int = OWNER, chat: int = CHAT) -> list[str]:
    """Link ``user`` to Telegram ``chat``; the texts of alerts sent there, in order. One sent
    to any other chat shows up as ``"to <chat>: <text>"`` so a wrong recipient fails a test."""
    app = client.app
    with session_scope(make_session_factory(app.state.engine)) as shared:  # type: ignore[attr-defined]  # a FastAPI app
        shared.get_one(User, user).telegram_user_id = chat
    sent: list[str] = []

    async def send(to: int, text: str) -> None:
        sent.append(text if to == chat else f"to {to}: {text}")

    app.state.send = send  # type: ignore[attr-defined]  # a FastAPI app
    return sent
