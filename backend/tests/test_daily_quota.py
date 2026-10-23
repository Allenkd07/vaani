from datetime import datetime, timedelta

import pytest

from app.api.deps import get_daily_quota
from app.core.rate_limit import RateLimitExceeded
from app.main import app
from app.services.daily_quota import QUOTA_TIMEZONE, DailyQuota


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def test_counts_up_to_the_limit_then_rejects(session_factory):
    quota = DailyQuota(session_factory, limit=2, clock=FakeClock(datetime(2026, 10, 23, 9, tzinfo=QUOTA_TIMEZONE)))
    quota.consume()
    quota.consume()
    with pytest.raises(RateLimitExceeded, match="today's transcription limit. It resets in about 15 hours"):
        quota.consume()


def test_resets_at_pacific_midnight(session_factory):
    clock = FakeClock(datetime(2026, 10, 23, 23, 30, tzinfo=QUOTA_TIMEZONE))
    quota = DailyQuota(session_factory, limit=1, clock=clock)
    quota.consume()
    with pytest.raises(RateLimitExceeded, match=r"about 1 hour\."):
        quota.consume()

    clock.now += timedelta(hours=1)  # 00:30 the next Pacific day
    quota.consume()


def test_count_survives_a_new_quota_instance(session_factory):
    clock = FakeClock(datetime(2026, 10, 23, 9, tzinfo=QUOTA_TIMEZONE))
    DailyQuota(session_factory, limit=1, clock=clock).consume()
    with pytest.raises(RateLimitExceeded):
        DailyQuota(session_factory, limit=1, clock=clock).consume()  # e.g. after the app restarts


def test_no_limit_means_no_cap(session_factory):
    quota = DailyQuota(session_factory, limit=None)
    for _ in range(5):
        quota.consume()


def test_live_websocket_rejects_sessions_over_the_daily_limit(client, session_factory):
    app.dependency_overrides[get_daily_quota] = lambda: DailyQuota(session_factory, limit=1)
    with client.websocket_connect("/ws/transcribe") as ws:
        assert ws.receive_json() == {"type": "ready"}
        ws.send_json({"type": "stop"})
        assert ws.receive_json() == {"type": "done"}

    with client.websocket_connect("/ws/transcribe") as ws:
        message = ws.receive_json()
        assert message["type"] == "error" and "today's transcription limit" in message["message"]
