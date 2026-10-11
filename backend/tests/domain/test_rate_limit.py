"""The in-memory rate limit behind /mcp and /oauth (mcp-threat-model.md M11)."""

from training_coach.domain.rate_limit import RateLimit


def test_hits_over_the_limit_are_refused_until_the_window_moves_on() -> None:
    limit = RateLimit(limit=2, window=60)
    assert limit.allow("a", 0)
    assert limit.allow("a", 10)
    assert not limit.allow("a", 20)
    assert limit.retry_after("a", 20) == 40
    assert limit.allow("b", 20)  # each key counts alone
    assert limit.allow("a", 60.5)  # the first hit has left the window


def test_a_refused_hit_is_not_counted() -> None:
    limit = RateLimit(limit=1, window=60)
    assert limit.allow("a", 0)
    for second in range(1, 59):
        assert not limit.allow("a", second)
    assert limit.allow("a", 60)


def test_retry_after_is_at_least_a_second() -> None:
    limit = RateLimit(limit=1, window=60)
    assert limit.retry_after("never", 0) == 1
    limit.allow("a", 0)
    assert limit.retry_after("a", 59.9) == 1


def test_many_keys_cannot_grow_memory_without_bound() -> None:
    limit = RateLimit(limit=1, window=60, max_keys=3)
    for key in "abc":
        limit.allow(key, 0)
    limit.allow("d", 1)  # nobody is idle yet: the oldest key goes
    assert len(limit._hits) == 3
    limit.allow("e", 100)  # everyone is idle now: all go
    assert set(limit._hits) == {"e"}
