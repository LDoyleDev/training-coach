from datetime import date

import pytest
from sqlalchemy import Engine

from tests.api.test_photos import CLEAN
from training_coach.db.models import ProgressPhoto
from training_coach.db.session import make_session_factory
from training_coach.domain.photos import Pose
from training_coach.services import photos
from training_coach.services.users import OWNER

TODAY = date(2026, 10, 10)


def test_an_upload_racing_another_for_the_same_day_and_pose_replaces_it(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both uploads miss the lookup; the second loses on the unique day and pose and updates."""
    sessions = make_session_factory(engine, user_id=OWNER)
    with sessions() as first:
        first_id = photos.save(first, TODAY, TODAY, Pose.FRONT, CLEAN)
        first.commit()
    real = photos._row
    calls: list[int] = []

    def late(*args: object) -> ProgressPhoto | None:
        calls.append(1)
        return None if len(calls) == 1 else real(*args)  # type: ignore[arg-type]  # passthrough

    monkeypatch.setattr(photos, "_row", late)
    with sessions() as second:
        assert photos.save(second, TODAY, TODAY, Pose.FRONT, CLEAN) == first_id
        second.commit()
    assert len(calls) == 2
    with sessions() as check:
        assert len(photos.listing(check)) == 1


def test_a_lost_race_with_no_row_to_update_says_try_again(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    sessions = make_session_factory(engine, user_id=OWNER)
    with sessions() as first:
        photos.save(first, TODAY, TODAY, Pose.BACK, CLEAN)
        first.commit()
    monkeypatch.setattr(photos, "_row", lambda *args: None)
    with sessions() as second:
        assert photos.save(second, TODAY, TODAY, Pose.BACK, CLEAN) == (
            "that photo couldn't be saved; try again"
        )
