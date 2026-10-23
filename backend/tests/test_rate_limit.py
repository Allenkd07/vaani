import pytest

from app.core.rate_limit import WINDOW_SEC, Limit, RateLimitExceeded, SessionLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_limiter(clock: FakeClock, global_concurrent: int = 10) -> SessionLimiter:
    return SessionLimiter(
        limits={"owner": Limit(concurrent=1, per_hour=2), "ip": Limit(concurrent=2, per_hour=10)},
        global_concurrent=global_concurrent,
        clock=clock,
    )


def test_one_concurrent_session_per_owner():
    limiter = make_limiter(FakeClock())
    with limiter.hold({"owner": "a"}):
        with pytest.raises(RateLimitExceeded, match="already running"):
            with limiter.hold({"owner": "a"}):
                pass
        with limiter.hold({"owner": "b"}):
            pass


def test_hourly_limit_resets_after_window():
    clock = FakeClock()
    limiter = make_limiter(clock)
    for _ in range(2):
        with limiter.hold({"owner": "a"}):
            pass
    with pytest.raises(RateLimitExceeded, match="2 recordings this hour"):
        with limiter.hold({"owner": "a"}):
            pass

    clock.now += WINDOW_SEC
    with limiter.hold({"owner": "a"}):
        pass


def test_shared_ip_limits_owners_together():
    limiter = make_limiter(FakeClock())
    with limiter.hold({"owner": "a", "ip": "1.2.3.4"}), limiter.hold({"owner": "b", "ip": "1.2.3.4"}):
        with pytest.raises(RateLimitExceeded):
            with limiter.hold({"owner": "c", "ip": "1.2.3.4"}):
                pass


def test_global_cap_and_release_on_error():
    limiter = make_limiter(FakeClock(), global_concurrent=1)
    with pytest.raises(ValueError):
        with limiter.hold({"owner": "a"}):
            raise ValueError
    with limiter.hold({"owner": "b"}):
        with pytest.raises(RateLimitExceeded, match="busy"):
            with limiter.hold({"owner": "c"}):
                pass
