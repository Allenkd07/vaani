from functools import lru_cache

from app.core.config import get_settings
from app.stt.base import SpeechToTextProvider


@lru_cache
def get_stt_provider() -> SpeechToTextProvider:
    """Builds the provider selected by STT_PROVIDER."""
    settings = get_settings()
    if settings.stt_provider == "gemini":
        from app.stt.gemini_live import GeminiLiveProvider

        return GeminiLiveProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            language_codes=settings.language_codes,
            mode=settings.stt_mode,
        )
    raise ValueError(f"Unknown STT provider: {settings.stt_provider}")
