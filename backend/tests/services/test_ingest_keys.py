"""The band import secret (ADR-0055): made once, kept hashed, found in an unbound session;
and the syncs noted on it, which tell when band data stops arriving."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, select

from training_coach.db.models import BandFeed
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.band_watch import Feed, FeedNotices, Notice
from training_coach.services import ingest_keys
from training_coach.services.users import OWNER

NOW = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)


def _make(engine: Engine) -> str:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        return ingest_keys.make(mine, NOW)


def _owner(engine: Engine, secret: str) -> int | None:
    with session_scope(make_session_factory(engine)) as shared:
        return ingest_keys.owner_of(shared, secret)


def _received(engine: Engine, at: timedelta, took: bool = True) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        ingest_keys.received(mine, NOW + at, took)


def _status(engine: Engine) -> ingest_keys.Status:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        return ingest_keys.status(mine)


def _watch(engine: Engine, at: timedelta) -> Notice | None:
    """The bot's check at NOW + ``at``, noting what it sends as told."""
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        found = ingest_keys.watch(mine, NOW + at)
        if found is not None:
            ingest_keys.told(mine, found, NOW + at)
        return found


def test_a_secret_names_its_owner_and_nothing_else_does(engine: Engine) -> None:
    secret = _make(engine)
    assert _owner(engine, secret) == OWNER
    assert _owner(engine, secret + "x") is None
    assert _owner(engine, secret.removeprefix("tci_")) is None
    assert _owner(engine, "tci_" + "a" * 200) is None


def test_a_stored_sync_is_noted_at_most_hourly(engine: Engine) -> None:
    _make(engine)
    _received(engine, timedelta(0))
    _received(engine, timedelta(minutes=30))
    assert _status(engine).last_used_at == NOW
    assert _status(engine).last_taken_at == NOW
    _received(engine, timedelta(minutes=61))
    assert _status(engine).last_used_at == NOW + timedelta(minutes=61)
    assert _status(engine).last_taken_at == NOW + timedelta(minutes=61)


def test_an_empty_sync_noted_just_before_doesnt_hide_records(engine: Engine) -> None:
    # The two are throttled apart: an empty sync at 10:00 then records at 10:30 still count.
    _make(engine)
    _received(engine, timedelta(0), took=False)
    _received(engine, timedelta(minutes=30), took=True)
    assert _status(engine).last_used_at == NOW
    assert _status(engine).last_taken_at == NOW + timedelta(minutes=30)


def test_a_day_without_data_is_told_once_and_its_end_once(engine: Engine) -> None:
    _make(engine)
    _received(engine, timedelta(0))
    assert _watch(engine, timedelta(hours=23)) is None
    assert _watch(engine, timedelta(hours=25)) is Notice.QUIET
    assert _watch(engine, timedelta(hours=26)) is None
    assert _watch(engine, timedelta(days=3)) is None
    _received(engine, timedelta(days=3, hours=1))
    assert _watch(engine, timedelta(days=3, hours=2)) is Notice.BACK
    assert _watch(engine, timedelta(days=3, hours=3)) is None
    # Then a later gap is told again.
    assert _watch(engine, timedelta(days=4, hours=2)) is Notice.QUIET


def test_empty_syncs_are_their_own_message(engine: Engine) -> None:
    _make(engine)
    _received(engine, timedelta(0))
    for hours in range(2, 27, 2):
        _received(engine, timedelta(hours=hours), took=False)
    assert _watch(engine, timedelta(hours=25)) is Notice.EMPTY
    _received(engine, timedelta(hours=28), took=False)
    assert _watch(engine, timedelta(hours=29)) is None  # still syncing empty: same gap
    _received(engine, timedelta(hours=30), took=True)
    assert _watch(engine, timedelta(hours=31)) is Notice.BACK


def test_records_right_after_the_alert_count_despite_the_hourly_note(engine: Engine) -> None:
    # The alert went at 25 h; records 10 minutes later must end the gap, though a sync was
    # noted under an hour before.
    _make(engine)
    _received(engine, timedelta(0))
    _received(engine, timedelta(hours=24, minutes=50), took=False)
    assert _watch(engine, timedelta(hours=25)) is Notice.EMPTY
    _received(engine, timedelta(hours=25, minutes=10), took=True)
    assert _watch(engine, timedelta(hours=26)) is Notice.BACK


def test_no_secret_means_no_alert(engine: Engine) -> None:
    assert _watch(engine, timedelta(days=5)) is None
    _make(engine)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        ingest_keys.remove(mine)
    assert _watch(engine, timedelta(days=5)) is None


def test_a_new_secret_starts_the_clock_again(engine: Engine) -> None:
    _make(engine)
    assert _watch(engine, timedelta(hours=25)) is Notice.QUIET
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        ingest_keys.make(mine, NOW + timedelta(days=2))
    assert _status(engine).last_taken_at is None
    assert _watch(engine, timedelta(days=2, hours=23)) is None
    assert _watch(engine, timedelta(days=3, hours=1)) is Notice.QUIET


def test_a_secret_made_while_the_alert_was_sent_keeps_its_clock(engine: Engine) -> None:
    _make(engine)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert ingest_keys.watch(mine, NOW + timedelta(hours=25)) is Notice.QUIET
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        ingest_keys.make(mine, NOW + timedelta(hours=25, seconds=1))
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        ingest_keys.told(mine, Notice.QUIET, NOW + timedelta(hours=25))
    assert _watch(engine, timedelta(hours=50)) is Notice.QUIET


def test_a_sync_after_the_secret_was_removed_is_ignored(engine: Engine) -> None:
    _received(engine, timedelta(0))  # no row: nothing to note, nothing fails
    assert _status(engine) == ingest_keys.Status(False, None, None, None)


def test_removing_when_there_is_none(engine: Engine) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert ingest_keys.remove(mine) is False
        assert ingest_keys.status(mine) == ingest_keys.Status(False, None, None, None)


# ------------------------------------------------------------- one kind stopping

STEPS_ONLY = ("steps", "weight")  # weight comes when it comes: never watched


def _sync(engine: Engine, at: timedelta, kinds: tuple[str, ...]) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        ingest_keys.received(mine, NOW + at, bool(kinds), kinds)


def _watch_feeds(engine: Engine, at: timedelta) -> FeedNotices:
    """The bot's check at NOW + ``at`` once all band data is flowing, noting what it sends."""
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        found = ingest_keys.watch_feeds(mine, NOW + at)
        if found:
            ingest_keys.told_feeds(mine, found, NOW + at)
        return found


def _feeds(engine: Engine) -> dict[str, tuple[datetime | None, datetime | None]]:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        rows = mine.scalars(select(BandFeed))
        return {row.feed: (row.last_taken_at, row.alerted_at) for row in rows}


def test_each_kind_is_noted_at_most_hourly_and_only_the_daily_ones(engine: Engine) -> None:
    _make(engine)
    _sync(engine, timedelta(0), STEPS_ONLY)
    _sync(engine, timedelta(minutes=30), ("steps", "sleep"))
    assert _feeds(engine) == {
        "steps": (NOW, None),
        "sleep": (NOW + timedelta(minutes=30), None),
    }
    _sync(engine, timedelta(minutes=61), ("steps", "steps"))
    assert _feeds(engine)["steps"] == (NOW + timedelta(minutes=61), None)


def test_a_kind_that_stops_is_told_once_and_its_return_once(engine: Engine) -> None:
    _make(engine)
    for hours in range(0, 50, 12):  # steps keep coming; sleep came once, heart rate never
        _sync(engine, timedelta(hours=hours), ("steps", "sleep") if hours == 0 else STEPS_ONLY)
    assert not _watch_feeds(engine, timedelta(hours=47))
    assert _watch_feeds(engine, timedelta(hours=49)) == FeedNotices((Feed.SLEEP, Feed.HEART_RATE))
    assert not _watch_feeds(engine, timedelta(hours=50))
    _sync(engine, timedelta(hours=51), ("steps", "sleep"))
    assert _watch_feeds(engine, timedelta(hours=52)) == FeedNotices(back=(Feed.SLEEP,))
    assert not _watch_feeds(engine, timedelta(hours=53))
    assert _feeds(engine)["heart_rate"] == (None, NOW + timedelta(hours=49))


def test_a_new_or_removed_secret_forgets_the_kinds(engine: Engine) -> None:
    _make(engine)
    _sync(engine, timedelta(0), ("steps",))
    _watch_feeds(engine, timedelta(hours=49))
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        ingest_keys.make(mine, NOW + timedelta(days=3))
    assert _feeds(engine) == {}
    _sync(engine, timedelta(days=3), ("steps",))
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        ingest_keys.remove(mine)
    assert _feeds(engine) == {}
    assert not _watch_feeds(engine, timedelta(days=9))


def test_a_secret_made_while_a_kind_was_told_keeps_its_clock(engine: Engine) -> None:
    _make(engine)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        ingest_keys.make(mine, NOW + timedelta(hours=49, seconds=1))
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        ingest_keys.told_feeds(mine, FeedNotices((Feed.SLEEP,)), NOW + timedelta(hours=49))
    assert _feeds(engine) == {}
