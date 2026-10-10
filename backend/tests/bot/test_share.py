"""/share sends the progress image (ADR-0050), to the owner only."""

import pytest
import respx
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import OWNER, STRANGER, TELEGRAM, command, run

App = Application  # type: ignore[type-arg]  # see build_bot


def _photo_route(router: respx.Router) -> None:
    sent = {
        "ok": True,
        "result": {"message_id": 9, "date": 0, "chat": {"id": OWNER, "type": "private"}},
    }
    router.post(url__regex=TELEGRAM + "sendPhoto$").respond(json=sent)


@pytest.mark.parametrize(("sender", "photos"), [(OWNER, 1), (STRANGER, 0)])
async def test_share_sends_the_picture_to_the_owner_only(
    application: App, seeded: sessionmaker[Session], sender: int, photos: int
) -> None:
    calls = await run(application, command("/share", sender), routes=_photo_route)
    assert len(calls.get("sendPhoto", [])) == photos
    if photos:
        body = calls["sendPhoto"][0]["multipart"]
        assert "never body data or photos" in body
        assert "PNG" in body
