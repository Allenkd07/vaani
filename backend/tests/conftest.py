import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Required settings, set before importing the app. Env vars take precedence over backend/.env.
os.environ.update(
    DATABASE_URL="sqlite://",
    STT_PROVIDER="gemini",
    GEMINI_API_KEY="test-key",
    GEMINI_MODEL="test-model",
    STT_MODE="VERBATIM",
)

from app.api.deps import get_daily_quota, get_session_limiter
from app.core.rate_limit import Limit, SessionLimiter
from app.db.session import Base, get_db
from app.services.daily_quota import DailyQuota
from app.main import app
from app.stt.base import SpeechToTextProvider, SpeechToTextSession, TranscriptEvent
from app.stt.factory import get_stt_provider


class FakeSession(SpeechToTextSession):
    """Emits one interim and one final event per audio chunk."""

    def __init__(self) -> None:
        self.chunks: list[bytes] = []
        self._ended = False

    async def send_audio(self, pcm: bytes) -> None:
        self.chunks.append(pcm)

    async def end_audio(self) -> None:
        self._ended = True

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        while not self._ended:
            await asyncio.sleep(0.01)
        for i, _ in enumerate(self.chunks):
            yield TranscriptEvent(type="interim", text="namaste", language="hi-IN")
            yield TranscriptEvent(type="final", text=f"namaste world {i}", language="hi-IN")


class FakeProvider(SpeechToTextProvider):
    @asynccontextmanager
    async def open_session(self) -> AsyncIterator[FakeSession]:
        yield FakeSession()


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_stt_provider] = FakeProvider
    limiter = SessionLimiter(
        limits={"owner": Limit(concurrent=1, per_hour=2), "ip": Limit(concurrent=3, per_hour=60)}, global_concurrent=10
    )
    app.dependency_overrides[get_session_limiter] = lambda: limiter
    app.dependency_overrides[get_daily_quota] = lambda: DailyQuota(session_factory, limit=None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
