"""In-memory limits on live transcription sessions, protecting the speech-to-text quota.

State is per process, which matches the single-instance deploy. Client keys are best effort (cookies can be
dropped, forwarded IPs spoofed); the global cap is the hard bound.
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

WINDOW_SEC = 3600


@dataclass(frozen=True)
class Limit:
    concurrent: int
    per_hour: int


class RateLimitExceeded(Exception):
    pass


class SessionLimiter:
    def __init__(self, limits: dict[str, Limit], global_concurrent: int, clock: Callable[[], float] = time.monotonic):
        self.limits = limits
        self.global_concurrent = global_concurrent
        self.clock = clock
        self._active: dict[str, int] = defaultdict(int)
        self._starts: dict[str, deque[float]] = defaultdict(deque)
        self._global_active = 0

    @contextmanager
    def hold(self, keys: dict[str, str]) -> Iterator[None]:
        """Reserves a session for the given {kind: key} pairs, e.g. {"owner": "…", "ip": "…"}."""
        self._acquire(keys)
        try:
            yield
        finally:
            self._release(keys)

    def _acquire(self, keys: dict[str, str]) -> None:
        now = self.clock()
        if self._global_active >= self.global_concurrent:
            raise RateLimitExceeded("Vaani is busy right now. Try again in a minute.")

        for kind, key in keys.items():
            limit = self.limits[kind]
            starts = self._starts[key]
            while starts and now - starts[0] >= WINDOW_SEC:
                starts.popleft()
            if self._active[key] >= limit.concurrent:
                raise RateLimitExceeded("A recording is already running in another tab. Stop it first.")
            if len(starts) >= limit.per_hour:
                raise RateLimitExceeded(f"You've reached {limit.per_hour} recordings this hour. Try again later.")

        self._global_active += 1
        for key in keys.values():
            self._active[key] += 1
            self._starts[key].append(now)

    def _release(self, keys: dict[str, str]) -> None:
        self._global_active -= 1
        for key in keys.values():
            self._active[key] -= 1
            if not self._active[key]:
                del self._active[key]
