from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import Limit, SessionLimiter
from app.db.session import SessionLocal, get_db
from app.repositories.transcription_repository import TranscriptionRepository
from app.services.daily_quota import DailyQuota
from app.services.transcription_service import TranscriptionService
from app.stt.base import SpeechToTextProvider
from app.stt.factory import get_stt_provider


def get_owner_id(request: Request) -> str:
    return request.state.owner_id  # set by the ensure_owner_cookie middleware


def get_transcription_service(
    db: Annotated[Session, Depends(get_db)], owner_id: Annotated[str, Depends(get_owner_id)]
) -> TranscriptionService:
    return TranscriptionService(TranscriptionRepository(db), owner_id)


@lru_cache
def get_session_limiter() -> SessionLimiter:
    # An IP may be shared (offices, NAT), so it gets more room than a single browser.
    return SessionLimiter(
        limits={"owner": Limit(concurrent=1, per_hour=20), "ip": Limit(concurrent=3, per_hour=60)},
        global_concurrent=10,
    )


@lru_cache
def get_daily_quota() -> DailyQuota:
    return DailyQuota(SessionLocal, get_settings().stt_daily_session_limit)


TranscriptionServiceDep = Annotated[TranscriptionService, Depends(get_transcription_service)]
SpeechToTextProviderDep = Annotated[SpeechToTextProvider, Depends(get_stt_provider)]
SessionLimiterDep = Annotated[SessionLimiter, Depends(get_session_limiter)]
DailyQuotaDep = Annotated[DailyQuota, Depends(get_daily_quota)]
