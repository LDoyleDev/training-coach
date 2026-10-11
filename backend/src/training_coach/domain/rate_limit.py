"""A sliding-window rate limit kept in memory (mcp-threat-model.md M11, requirement 16).

One process serves everything (ADR-0002), so a counter in memory is enough, and it writes
nothing to the SD card. A restart forgets the counts, which only ever lets a little more
through; Cloudflare's limit stays in front of it.
"""

from collections import deque


class RateLimit:
    """At most ``limit`` hits in any ``window`` seconds for each key."""

    def __init__(self, limit: int, window: float, max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window = window
        self.max_keys = max_keys  # a flood of new keys can't grow memory without bound
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float) -> bool:
        """Count a hit for ``key`` at ``now`` (seconds); False when it is over the limit, in
        which case it isn't counted."""
        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= self.max_keys:
                self._forget(now)
            hits = self._hits[key] = deque()
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def retry_after(self, key: str, now: float) -> int:
        """Whole seconds until ``key`` may try again (at least 1)."""
        hits = self._hits.get(key)
        if not hits:
            return 1
        return max(1, int(hits[0] + self.window - now + 0.999))

    def _forget(self, now: float) -> None:
        """Drop keys with no recent hits; if none are idle, the oldest key."""
        idle = [k for k, hits in self._hits.items() if not hits or hits[-1] <= now - self.window]
        for key in idle:
            del self._hits[key]
        if len(self._hits) >= self.max_keys:
            del self._hits[next(iter(self._hits))]
