"""Progress photos (2-B, #143, ADR-0039): saving, listing and fetching. A photo is cleaned of
its metadata before it is stored. Personal: never log one or anything about its content."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from training_coach.db.models import ProgressPhoto
from training_coach.domain.dates import MAX_DAYS_BACK
from training_coach.domain.photos import Pose, clean_jpeg


@dataclass(frozen=True)
class Photo:
    id: int
    on: date
    pose: Pose
    size: int


def _row(session: Session, on: date, pose: Pose) -> ProgressPhoto | None:
    return session.scalar(
        select(ProgressPhoto).where(ProgressPhoto.local_date == on, ProgressPhoto.pose == pose)
    )


def save(session: Session, on: date, today: date, pose: Pose, data: bytes) -> int | str:
    """Store the photo for ``on`` and ``pose``, replacing one already there. Its id, or why
    it can't be stored."""
    if on > today:
        return "that day hasn't happened yet"
    if (today - on).days > MAX_DAYS_BACK:
        return f"photos more than {MAX_DAYS_BACK} days ago can't be added"
    cleaned = clean_jpeg(data)
    if isinstance(cleaned, str):
        return cleaned
    row = _row(session, on, pose)
    if row is None:
        try:  # another upload of the same day and pose at the same moment wins the insert
            with session.begin_nested():
                row = ProgressPhoto(local_date=on, pose=pose.value, jpeg=cleaned, size=len(cleaned))
                session.add(row)
                session.flush()
            return row.id
        except IntegrityError:
            row = _row(session, on, pose)
            if row is None:
                return "that photo couldn't be saved; try again"
    row.jpeg, row.size = cleaned, len(cleaned)
    session.flush()
    return row.id


def listing(session: Session) -> list[Photo]:
    """Every photo, newest day first and front, side, back within a day. No pictures loaded."""
    order = list(Pose)
    rows = session.execute(
        select(ProgressPhoto.id, ProgressPhoto.local_date, ProgressPhoto.pose, ProgressPhoto.size)
    )
    photos = [Photo(i, on, Pose(pose), size) for i, on, pose, size in rows]
    return sorted(photos, key=lambda p: (-p.on.toordinal(), order.index(p.pose)))


def picture(session: Session, photo_id: int) -> bytes | None:
    return session.scalar(select(ProgressPhoto.jpeg).where(ProgressPhoto.id == photo_id))


def delete(session: Session, photo_id: int) -> bool:
    row = session.scalar(select(ProgressPhoto).where(ProgressPhoto.id == photo_id))
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True
