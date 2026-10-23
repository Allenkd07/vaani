import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.rate_limit import RateLimitExceeded
from app.repositories.usage_repository import UsageRepository

# The Gemini API's daily quotas reset at midnight Pacific time.
QUOTA_TIMEZONE = ZoneInfo("America/Los_Angeles")


class DailyQuota:
    """App-wide cap on live sessions per quota day, stored in the database so restarts don't reset it.

    Set below the provider's requests-per-day limit, it rejects sessions with a clear message
    before the provider starts refusing them.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        limit: int | None,
        clock: Callable[[], datetime] = lambda: datetime.now(QUOTA_TIMEZONE),
    ) -> None:
        self.session_factory = session_factory
        self.limit = limit
        self.clock = clock

    def consume(self) -> None:
        """Counts one session, or raises RateLimitExceeded once today's limit is reached. No-op without a limit."""
        if self.limit is None:
            return
        now = self.clock()
        with self.session_factory() as db:
            if UsageRepository(db).try_increment(now.date(), self.limit):
                return
        hours = _hours_until_reset(now)
        raise RateLimitExceeded(
            f"Vaani has reached today's transcription limit. It resets in about {hours} hour{'' if hours == 1 else 's'}."
        )


def _hours_until_reset(now: datetime) -> int:
    next_midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=now.tzinfo)
    # Compared in UTC: same-zone subtraction uses wall-clock time and is off by an hour across DST changes.
    seconds = (next_midnight.astimezone(UTC) - now.astimezone(UTC)).total_seconds()
    return max(1, math.ceil(seconds / 3600))
